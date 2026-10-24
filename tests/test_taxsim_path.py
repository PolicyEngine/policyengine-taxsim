"""
Regression tests for the `taxsim` subcommand's --taxsim-path option.

click.Path hands the command a str, and TaxsimRunner called `.exists()` on
whatever it was given, so every --taxsim-path run failed with
"AttributeError: 'str' object has no attribute 'exists'". A bare relative
name ("taxsimtest-osx.exe") also failed once past that check: the runner
pipes input through the shell, which searches PATH for a name without a
directory and reports "command not found".

These run the bundled taxsimtest binary on a pre-2021 record, which needs no
PolicyEngine simulation, so they are fast on every CI OS.
"""

import platform
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from policyengine_taxsim.cli import cli
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

REPO_ROOT = Path(__file__).resolve().parent.parent
_EXE_NAMES = {
    "darwin": "taxsimtest-osx.exe",
    "linux": "taxsimtest-linux.exe",
    "windows": "taxsimtest-windows.exe",
}
EXE_NAME = _EXE_NAMES[platform.system().lower()]
BUNDLED = REPO_ROOT / "resources" / "taxsimtest" / EXE_NAME

RECORDS = pd.DataFrame(
    {
        "taxsimid": [1, 2],
        "year": [2019, 2020],
        "state": [5, 33],
        "mstat": [1, 2],
        "page": [40, 45],
        "sage": [0, 43],
        "depx": [0, 2],
        "age1": [0, 4],
        "age2": [0, 9],
        "pwages": [50_000, 70_000],
        "swages": [0, 30_000],
    }
)
OUTPUTS = ["fiitax", "siitax", "fica"]

# Each way a caller can name the executable: (path as passed, the directory
# to run from so the relative spellings resolve to BUNDLED).
PATH_SPELLINGS = {
    "absolute-str": (str(BUNDLED), REPO_ROOT),
    "absolute-path": (BUNDLED, REPO_ROOT),
    "relative-with-directory": (
        str(Path("resources") / "taxsimtest" / EXE_NAME),
        REPO_ROOT,
    ),
    "bare-name": (EXE_NAME, BUNDLED.parent),
}


def _by_id(df):
    df = df.copy()
    df["taxsimid"] = df["taxsimid"].astype(float).astype(int)
    return df.set_index("taxsimid").sort_index()


@pytest.fixture(scope="module")
def default_results():
    """Results from the binary TaxsimRunner finds on its own, run from the
    repo root as the rest of the suite does."""
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(REPO_ROOT)
        results = _by_id(TaxsimRunner(RECORDS.copy()).run(show_progress=False))
    # Every record has wages, so each owes payroll tax: guards the equality
    # checks below against passing on an empty or all-zero run.
    assert list(results.index) == [1, 2]
    assert (results["fica"] > 0).all()
    return results


@pytest.mark.parametrize("spelling", PATH_SPELLINGS.values(), ids=list(PATH_SPELLINGS))
def test_runner_accepts_every_path_spelling(
    spelling, default_results, tmp_path, monkeypatch
):
    path, run_from = spelling
    monkeypatch.chdir(run_from)
    runner = TaxsimRunner(RECORDS.copy(), taxsim_path=path)

    assert isinstance(runner.taxsim_path, Path)
    assert runner.taxsim_path.is_absolute()
    assert runner.taxsim_path.resolve() == BUNDLED.resolve()

    # The path is fixed when the runner is built: moving elsewhere before
    # run() must not change which binary runs.
    monkeypatch.chdir(tmp_path)
    results = _by_id(runner.run(show_progress=False))

    pd.testing.assert_frame_equal(
        results[OUTPUTS], default_results[OUTPUTS], check_exact=True
    )


def test_runner_reports_missing_str_path(tmp_path):
    missing = str(tmp_path / "no-such-taxsim")
    with pytest.raises(FileNotFoundError, match="no-such-taxsim"):
        TaxsimRunner(RECORDS.copy(), taxsim_path=missing)


@pytest.mark.parametrize(
    "spelling",
    [PATH_SPELLINGS["absolute-str"], PATH_SPELLINGS["bare-name"]],
    ids=["absolute", "bare-name"],
)
def test_cli_taxsim_path_option(spelling, default_results, tmp_path, monkeypatch):
    path, run_from = spelling
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "out.csv"
    RECORDS.to_csv(input_file, index=False)

    monkeypatch.chdir(run_from)
    result = CliRunner().invoke(
        cli,
        ["taxsim", str(input_file), "--taxsim-path", str(path), "-o", str(output_file)],
    )

    assert result.exit_code == 0, f"{result.output}\n{result.exception!r}"
    out = _by_id(pd.read_csv(output_file))
    assert list(out.index) == [1, 2]
    pd.testing.assert_frame_equal(
        out[OUTPUTS], default_results[OUTPUTS], check_exact=True
    )
