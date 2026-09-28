import pandas as pd

from policyengine_taxsim.runners.remote_taxsim_runner import RemoteTaxsimRunner
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner


def _taxsim_input(**overrides):
    row = {
        "taxsimid": 1,
        "year": 2020,
        "state": 6,
        "mstat": 1,
        "page": 40,
        "sage": 0,
        "depx": 0,
        "pwages": 50_000,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_local_taxsim_input_preserves_option_columns():
    df = _taxsim_input(opt1=30, opt1v=1)
    runner = TaxsimRunner.__new__(TaxsimRunner)

    formatted = runner._format_input_for_taxsim(df)

    assert formatted["opt1"].tolist() == [30]
    assert formatted["opt1v"].tolist() == [1]
    assert runner._dynamic_columns[-2:] == ["opt1", "opt1v"]


def test_remote_taxsim_input_preserves_option_columns():
    df = _taxsim_input(opt1=30, opt1v=1)
    runner = RemoteTaxsimRunner(df)

    csv_text = runner._format_input(runner.input_df)
    lines = csv_text.strip().splitlines()
    header = lines[0].split(",")
    values = lines[1].split(",")

    assert header[-2:] == ["opt1", "opt1v"]
    assert values[header.index("opt1")] == "30"
    assert values[header.index("opt1v")] == "1"


def test_remote_taxsim_option_columns_default_to_zero():
    df = _taxsim_input()
    runner = RemoteTaxsimRunner(df)

    csv_text = runner._format_input(runner.input_df)
    lines = csv_text.strip().splitlines()
    header = lines[0].split(",")
    values = lines[1].split(",")

    assert header[-2:] == ["opt1", "opt1v"]
    assert values[header.index("opt1")] == "0"
    assert values[header.index("opt1v")] == "0"
