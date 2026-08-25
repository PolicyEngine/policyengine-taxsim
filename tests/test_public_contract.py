"""Pin the public surfaces documented as stable (Maintenance & Roadmap docs).

Downstream pipelines import PolicyEngineRunner directly rather than calling
the CLI, so these names and shapes are a compatibility contract: the import
path, the class, its constructor taking a TAXSIM-format DataFrame, and run()
returning a TAXSIM-format DataFrame. Changing any of them is a breaking
change that needs a deprecation path. The CLI entry point has its own pin in
test_cli_entry_point.py.
"""

import pandas as pd


def test_runner_import_path_and_class():
    from policyengine_taxsim.runners import PolicyEngineRunner

    assert callable(PolicyEngineRunner)


def test_runner_accepts_and_returns_taxsim_format_dataframe():
    from policyengine_taxsim.runners import PolicyEngineRunner

    input_df = pd.DataFrame(
        [
            {
                "taxsimid": 1,
                "year": 2023,
                "state": 6,
                "mstat": 1,
                "page": 40,
                "pwages": 50_000,
            }
        ]
    )
    result = PolicyEngineRunner(input_df).run(show_progress=False)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    for column in ("taxsimid", "year", "fiitax"):
        assert column in result.columns
