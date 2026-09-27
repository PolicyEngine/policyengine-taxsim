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
