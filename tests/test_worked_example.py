"""The worked example in docs/input-guide.md runs as documented.

Runs docs/examples/custom-dataset/crosswalk.py in a copy of that folder, then
repeats the Stata script's hand-off to the emulator (a .dta file through the
policyengine subcommand) on the same TAXSIM input and checks it gives the same
taxes. Stata itself is not available in CI. When Rscript is available, also
runs crosswalk.R and checks it agrees.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "docs" / "examples" / "custom-dataset"
TAXES = ["fiitax", "siitax", "fica", "v10"]


def _environment() -> dict:
    """Puts this Python's policyengine-taxsim command first on the PATH, as
    an activated environment would."""
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


@pytest.fixture(scope="module")
def python_run(tmp_path_factory):
    folder = tmp_path_factory.mktemp("example") / "custom-dataset"
    shutil.copytree(EXAMPLE, folder)
    result = subprocess.run(
        [sys.executable, "crosswalk.py"],
        cwd=folder,
        capture_output=True,
        text=True,
        env=_environment(),
    )
    assert result.returncode == 0, result.stderr[-3000:]
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
    taxsim.to_stata(python_run / "taxsim_input.dta", write_index=False)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "policyengine_taxsim.cli",
            "policyengine",
            "taxsim_input.dta",
            "-o",
            "taxsim_results.dta",
        ],
        cwd=python_run,
        capture_output=True,
        text=True,
        env=_environment(),
    )
    assert result.returncode == 0, result.stderr[-3000:]
    from_stata = pd.read_stata(python_run / "taxsim_results.dta").set_index("taxsimid")
    from_python = pd.read_csv(python_run / "survey_with_taxes.csv").set_index("hh_id")
    for household in from_python.index:
        for column in TAXES:
            assert (
                abs(
                    from_stata.loc[household, column]
                    - from_python.loc[household, column]
                )
                < 0.01
            )


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
def test_r_example_gives_the_same_taxes(python_run, tmp_path):
    folder = tmp_path / "custom-dataset"
    shutil.copytree(EXAMPLE, folder)
    result = subprocess.run(
        ["Rscript", "crosswalk.R"],
        cwd=folder,
        capture_output=True,
        text=True,
        env=_environment(),
    )
    assert result.returncode == 0, result.stderr[-3000:]
    from_r = pd.read_csv(folder / "survey_with_taxes.csv").set_index("hh_id")
    from_python = pd.read_csv(python_run / "survey_with_taxes.csv").set_index("hh_id")
    pd.testing.assert_frame_equal(from_r[TAXES], from_python[TAXES], atol=0.01)
