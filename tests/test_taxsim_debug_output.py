"""TAXSIM debug counters are not household records."""

import pandas as pd
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner


def test_known_debug_lines_are_removed(tmp_path):
    output = tmp_path / "taxsim.csv"
    output.write_text(
        "taxsimid,fiitax,siitax,cdate-test\n1,100,20,0\n d3        1257\n d4        1257           0\n2,200,40,0\n"
    )
    runner = TaxsimRunner.__new__(TaxsimRunner)
    result = runner._parse_taxsim_output(str(output))
    assert result.taxsimid.tolist() == [1, 2]
    assert result.fiitax.tolist() == [100, 200]
    assert runner.binary_build_date == "test"


def test_october_build_d1_lines_are_removed(tmp_path):
    """cd2026100817 prints " d1   <value>" before Minnesota 2024-2025 records."""
    output = tmp_path / "taxsim.csv"
    output.write_text(
        "taxsimid,fiitax,siitax\n"
        " d1   0.0000000000000000     \n"
        "1,100,20\n"
        " d1   80.661443071428039     \n"
        " d1   -3     \n"
        "2,200,40\n"
    )
    result = TaxsimRunner.__new__(TaxsimRunner)._parse_taxsim_output(str(output))
    assert result.taxsimid.tolist() == [1, 2]
    assert result.siitax.tolist() == [20, 40]


def test_october_27_build_d1_pairs_are_removed(tmp_path):
    """cd2026102718 prints " d1 <integer> <integer>" before Colorado 2021
    records."""
    output = tmp_path / "taxsim.csv"
    output.write_text(
        "taxsimid,fiitax,siitax\n"
        " d1           0           0\n"
        "1,100,20\n"
        " d1       14231       14231\n"
        "2,200,40\n"
    )
    result = TaxsimRunner.__new__(TaxsimRunner)._parse_taxsim_output(str(output))
    assert result.taxsimid.tolist() == [1, 2]
    assert result.siitax.tolist() == [20, 40]


def test_modern_build_stamp_is_reported(tmp_path):
    """Builds since August 2026 stamp "cd2026081819" instead of "cdate-..."."""
    output = tmp_path / "taxsim.csv"
    output.write_text('taxsimid,fiitax,siitax,"cd2026081819"\n1,100,20,0\n')
    runner = TaxsimRunner.__new__(TaxsimRunner)
    runner._parse_taxsim_output(str(output))
    assert runner.binary_build_date == "cd2026081819"


def test_invalid_records_are_not_silently_dropped(tmp_path):
    output = tmp_path / "taxsim.csv"
    output.write_text("taxsimid,fiitax,siitax\n1,100,20\nbroken,200,40\n")
    result = TaxsimRunner.__new__(TaxsimRunner)._parse_taxsim_output(str(output))
    assert len(result) == 2
    assert pd.isna(result.taxsimid.iloc[1])
