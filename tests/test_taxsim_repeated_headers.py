"""Repeated TAXSIM CSV headers are not household records."""

import pandas as pd
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner


def test_repeated_header_rows_are_removed(tmp_path):
    output = tmp_path / "taxsim.csv"
    output.write_text(
        "taxsimid,fiitax,siitax,cdate-test\n1,100,20,0\ntaxsimid,fiitax,siitax,cdate-test\n2,200,40,0\n"
    )
    runner = TaxsimRunner.__new__(TaxsimRunner)
    result = runner._parse_taxsim_output(str(output))
    assert result.taxsimid.tolist() == [1, 2]
    assert result.fiitax.tolist() == [100, 200]
    assert runner.binary_build_date == "test"


def test_invalid_records_are_not_silently_dropped(tmp_path):
    output = tmp_path / "taxsim.csv"
    output.write_text("taxsimid,fiitax,siitax\n1,100,20\nbroken,200,40\n")
    result = TaxsimRunner.__new__(TaxsimRunner)._parse_taxsim_output(str(output))
    assert len(result) == 2
    assert pd.isna(result.taxsimid.iloc[1])
