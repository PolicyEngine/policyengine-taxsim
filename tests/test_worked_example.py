"""The worked example in docs/input-guide.md runs as documented.

Runs docs/examples/custom-dataset/crosswalk.py in a copy of that folder, then
repeats the Stata script's hand-off to the emulator (a .dta file through the
policyengine subcommand) on the same TAXSIM input and checks it gives the same
taxes. Stata itself is not available in CI. When Rscript is available, also
checks that crosswalk.R builds the same input and merges the same way.
"""

import os
import runpy
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from policyengine_taxsim.cli import cli

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "docs" / "examples" / "custom-dataset"
TAXES = ["fiitax", "siitax", "fica", "v10"]


@pytest.fixture(scope="module")
def python_run(tmp_path_factory):
    """The example folder after `python crosswalk.py` has run in it."""
    folder = tmp_path_factory.mktemp("example") / "custom-dataset"
    shutil.copytree(EXAMPLE, folder)
    start = Path.cwd()
    os.chdir(folder)
    try:
        runpy.run_path("crosswalk.py", run_name="__main__")
    finally:
        os.chdir(start)
    return folder


def test_python_example_computes_every_household(python_run):
    survey = pd.read_csv(python_run / "survey_extract.csv")
    merged = pd.read_csv(python_run / "survey_with_taxes.csv")
    assert merged["hh_id"].tolist() == survey["hh_id"].tolist()
    assert merged[TAXES].notna().all().all()


def test_python_example_recodes_as_documented(python_run):
    taxsim = pd.read_csv(python_run / "taxsim_input.csv").set_index("taxsimid")
    assert taxsim.notna().all().all()
    # Household 102's newborn is coded as 1, and married is mstat 2.
    assert taxsim.loc[102, "age1"] == 1
    assert taxsim.loc[101, "mstat"] == 2 and taxsim.loc[102, "mstat"] == 1
    # Charity is added to mortgage interest.
    assert taxsim.loc[101, "mortgage"] == 12000 + 1500


def test_stata_hand_off_gives_the_same_taxes(python_run):
    """crosswalk.do saves the TAXSIM input as .dta and runs
    `policyengine-taxsim policyengine taxsim_input.dta -o taxsim_results.dta`."""
    taxsim = pd.read_csv(python_run / "taxsim_input.csv")
    source = python_run / "taxsim_input.dta"
    output = python_run / "taxsim_results.dta"
    taxsim.to_stata(source, write_index=False)
    result = CliRunner().invoke(cli, ["policyengine", str(source), "-o", str(output)])
    assert result.exit_code == 0, f"{result.output}\n{result.exception}"
    from_stata = pd.read_stata(output)
    from_stata["taxsimid"] = from_stata["taxsimid"].astype(int)
    from_stata = from_stata.set_index("taxsimid")[TAXES].astype(float)
    from_python = pd.read_csv(python_run / "survey_with_taxes.csv").set_index("hh_id")
    pd.testing.assert_frame_equal(
        from_stata.loc[from_python.index].round(2),
        from_python[TAXES],
        check_names=False,
        atol=0.01,
    )


STAND_IN = """#!/bin/sh
# Stand-in for policyengine-taxsim: records its arguments and writes the
# results the Python run computed to the path after -o.
echo "$@" > "$STAND_IN_LOG"
cp "$STAND_IN_RESULTS" "$4"
"""


@pytest.mark.skipif(
    shutil.which("Rscript") is None or os.name == "nt",
    reason="needs Rscript and a POSIX shell",
)
def test_r_example_recodes_and_merges_like_python(python_run, tmp_path):
    """crosswalk.R builds the same TAXSIM input as crosswalk.py, calls the
    documented command, and merges the results the same way.

    The emulator is replaced by a stand-in that returns the taxes the Python
    run computed, so this checks the R code in about a second; the real
    command on this input is exercised by the Stata hand-off test above. The
    whole R script was run against the real emulator when the guide was
    written."""
    folder = tmp_path / "custom-dataset"
    shutil.copytree(EXAMPLE, folder)
    from_python = pd.read_csv(python_run / "survey_with_taxes.csv")
    canned = tmp_path / "canned_results.csv"
    from_python.rename(columns={"hh_id": "taxsimid"})[["taxsimid", *TAXES]].to_csv(
        canned, index=False
    )
    bin_folder = tmp_path / "bin"
    bin_folder.mkdir()
    stand_in = bin_folder / "policyengine-taxsim"
    stand_in.write_text(STAND_IN)
    stand_in.chmod(0o755)
    log = tmp_path / "stand_in.log"
    environment = dict(os.environ)
    environment["PATH"] = str(bin_folder) + os.pathsep + environment.get("PATH", "")
    environment["STAND_IN_LOG"] = str(log)
    environment["STAND_IN_RESULTS"] = str(canned)
    result = subprocess.run(
        ["Rscript", "crosswalk.R"],
        cwd=folder,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert log.read_text().split() == [
        "policyengine",
        "taxsim_input.csv",
        "-o",
        "taxsim_results.csv",
    ]
    pd.testing.assert_frame_equal(
        pd.read_csv(folder / "taxsim_input.csv"),
        pd.read_csv(python_run / "taxsim_input.csv"),
        check_dtype=False,
    )
    from_r = pd.read_csv(folder / "survey_with_taxes.csv").set_index("hh_id")
    pd.testing.assert_frame_equal(
        from_r[TAXES], from_python.set_index("hh_id")[TAXES], atol=0.01
    )
