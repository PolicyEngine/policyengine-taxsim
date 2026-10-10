"""What the R package (r-package/policyenginetaxsim) relies on from Python.

The R wrapper calls StitchedRunner through reticulate, so R matches the
command line, and setup_policyengine() installs one released
policyengine-taxsim by default. These tests pin, from the Python side:

- the release the R package installs by default is this package's version,
  and the release step (.github/bump_version.py) moves the two together;
- StitchedRunner sends each record to exactly one engine by its year, and
  ``pe_min_year=0``, which the R package passes for ``engine =
  "policyengine"``, sends every record to PolicyEngine and still returns the
  rows in input order.

The R package's own tests are in r-package/policyenginetaxsim/tests.
"""

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import policyengine_taxsim
from policyengine_taxsim.runners import PolicyEngineRunner, StitchedRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
BUMP_SCRIPT = REPO_ROOT / ".github" / "bump_version.py"
R_SETUP = REPO_ROOT / "r-package" / "policyenginetaxsim" / "R" / "setup.R"
R_PIN = re.compile(r'^\.PE_TAXSIM_VERSION <- "([^"]*)"$', re.MULTILINE)


def _r_pin(text):
    """The policyengine-taxsim release named in the R package's setup.R."""
    pins = R_PIN.findall(text)
    assert len(pins) == 1, f"expected one .PE_TAXSIM_VERSION line, found {pins}"
    return pins[0]


def _pyproject_version(text):
    return re.search(r'^version = "(.+?)"$', text, re.MULTILINE).group(1)


def _load_bump_script():
    spec = importlib.util.spec_from_file_location("bump_version", BUMP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# The default release
# ---------------------------------------------------------------------------


def test_r_package_installs_this_release_by_default():
    """setup_policyengine() pins policyengine-taxsim to the version in
    pyproject.toml, so a copy of the R package installs the release made
    from the same code."""
    pin = _r_pin(R_SETUP.read_text())
    assert pin == _pyproject_version((REPO_ROOT / "pyproject.toml").read_text())
    assert pin == policyengine_taxsim.__version__


@pytest.mark.parametrize(
    "fragments, expected",
    [
        (["a.fixed.md"], "3.1.2"),
        (["a.changed.md", "b.fixed.md"], "3.1.2"),
        (["a.added.md", "b.fixed.md"], "3.2.0"),
        (["a.removed.md"], "3.2.0"),
        (["a.breaking.md", "b.added.md"], "4.0.0"),
    ],
)
def test_release_step_moves_the_r_pin_with_the_version(tmp_path, fragments, expected):
    """After the release step, pyproject.toml, the Python package and the R
    package all name the new version."""
    (tmp_path / ".github").mkdir()
    shutil.copy(BUMP_SCRIPT, tmp_path / ".github" / "bump_version.py")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "policyengine-taxsim"\nversion = "3.1.1"\n'
    )
    (tmp_path / "policyengine_taxsim").mkdir()
    init_file = tmp_path / "policyengine_taxsim" / "__init__.py"
    init_file.write_text('__version__ = "3.1.1"\n')
    r_setup = tmp_path / "r-package" / "policyenginetaxsim" / "R" / "setup.R"
    r_setup.parent.mkdir(parents=True)
    # The real file, at an older pin: the step sets the pin whatever it was.
    r_source = R_PIN.sub('.PE_TAXSIM_VERSION <- "3.0.0"', R_SETUP.read_text())
    r_setup.write_text(r_source)
    (tmp_path / "changelog.d").mkdir()
    for name in fragments:
        (tmp_path / "changelog.d" / name).write_text("A change.\n")

    subprocess.run(
        [sys.executable, str(tmp_path / ".github" / "bump_version.py")],
        check=True,
        capture_output=True,
    )

    assert _pyproject_version((tmp_path / "pyproject.toml").read_text()) == expected
    assert init_file.read_text() == f'__version__ = "{expected}"\n'
    assert _r_pin(r_setup.read_text()) == expected
    # Nothing else in the R file changes: its documentation examples name
    # versions too.
    assert R_PIN.sub("", r_setup.read_text()) == R_PIN.sub("", r_source)


def test_release_step_fails_without_the_r_pin_line(tmp_path):
    """A release must not leave the R package naming an older version, so the
    step stops when it cannot find the line."""
    r_setup = tmp_path / "setup.R"
    r_setup.write_text('.PE_PYTHON_VERSION <- ">=3.10,<3.14"\n')
    bump = _load_bump_script()
    with pytest.raises(SystemExit) as stopped:
        bump.update_r_pin(r_setup, "3.1.2")
    assert stopped.value.code == 1
    assert r_setup.read_text() == '.PE_PYTHON_VERSION <- ">=3.10,<3.14"\n'


@settings(max_examples=50, deadline=None)
@given(
    version=st.tuples(*[st.integers(min_value=0, max_value=999)] * 3).map(
        lambda parts: ".".join(str(part) for part in parts)
    )
)
def test_update_r_pin_round_trips_and_changes_only_the_pin(tmp_path_factory, version):
    """For any version: the pin reads back as that version, every other line
    of the file is unchanged, and a second update changes nothing."""
    bump = _load_bump_script()
    original = R_SETUP.read_text()
    r_setup = tmp_path_factory.mktemp("r") / "setup.R"
    r_setup.write_text(original)

    bump.update_r_pin(r_setup, version)
    updated = r_setup.read_text()

    assert _r_pin(updated) == version
    assert R_PIN.sub("", updated) == R_PIN.sub("", original)
    bump.update_r_pin(r_setup, version)
    assert r_setup.read_text() == updated


# ---------------------------------------------------------------------------
# The runner the R package calls
# ---------------------------------------------------------------------------


def _records(years):
    return pd.DataFrame(
        {
            "taxsimid": range(1, len(years) + 1),
            "year": years,
            "state": 5,
            "mstat": 1,
            "pwages": 50_000,
        }
    )


class _RecordingRunner:
    """Stands in for an engine: records the rows it is given and returns one
    result row for each."""

    def __init__(self):
        self.received = []

    def __call__(self, input_df, *args, **kwargs):
        self.received.append(input_df)
        runner = type("Runner", (), {})()
        runner.run = lambda *a, **k: input_df[["taxsimid", "year"]].assign(fiitax=0.0)
        return runner

    @property
    def years(self):
        return [int(year) for df in self.received for year in df["year"]]


def test_cutoff_year_is_readable_from_the_class():
    """The R package reads the cutoff from StitchedRunner.PE_MIN_YEAR for its
    progress message; it is the cutoff a runner uses unless told otherwise."""
    assert isinstance(StitchedRunner.PE_MIN_YEAR, int)
    assert StitchedRunner(_records([2023])).pe_min_year == StitchedRunner.PE_MIN_YEAR


@settings(max_examples=100, deadline=None)
@given(
    years=st.lists(st.integers(min_value=1960, max_value=2030), min_size=1, max_size=30)
)
def test_each_record_goes_to_exactly_one_engine_by_its_year(years):
    """For any mix of years: PolicyEngine gets exactly the records from the
    cutoff year on, TAXSIM-35 the earlier ones, and no record is dropped or
    computed twice."""
    cutoff = StitchedRunner.PE_MIN_YEAR
    policyengine, taxsim = _RecordingRunner(), _RecordingRunner()
    with (
        patch(
            "policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner",
            policyengine,
        ),
        patch("policyengine_taxsim.runners.taxsim_runner.TaxsimRunner", taxsim),
    ):
        result = StitchedRunner(_records(years)).run(show_progress=False)

    assert sorted(policyengine.years) == sorted(y for y in years if y >= cutoff)
    assert sorted(taxsim.years) == sorted(y for y in years if y < cutoff)
    assert len(policyengine.years) + len(taxsim.years) == len(years) == len(result)


@settings(max_examples=100, deadline=None)
@given(
    years=st.lists(st.integers(min_value=1960, max_value=2030), min_size=1, max_size=30)
)
def test_first_policyengine_year_zero_sends_every_record_to_policyengine(years):
    """What the R package passes for engine = "policyengine": no record
    reaches TAXSIM-35, whatever its year."""
    policyengine, taxsim = _RecordingRunner(), _RecordingRunner()
    with (
        patch(
            "policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner",
            policyengine,
        ),
        patch("policyengine_taxsim.runners.taxsim_runner.TaxsimRunner", taxsim),
    ):
        result = StitchedRunner(_records(years), pe_min_year=0).run(show_progress=False)

    assert sorted(policyengine.years) == sorted(years)
    assert taxsim.received == []
    assert len(result) == len(years)


def test_policyengine_for_every_year_matches_policyengine_runner_in_input_order():
    """Differential: StitchedRunner(pe_min_year=0), which the R package uses
    for engine = "policyengine", returns what PolicyEngineRunner computes for
    the same records, including a year before the cutoff, in input order."""
    records = pd.DataFrame(
        {
            "taxsimid": [1, 2, 3, 4],
            "year": [2023, 2019, 2023, 2019],
            "state": [5, 44, 33, 5],
            "mstat": [1, 2, 1, 1],
            "page": [40, 45, 30, 35],
            "sage": [0, 43, 0, 0],
            "pwages": [50_000, 80_000, 120_000, 30_000],
            "swages": [0, 40_000, 0, 0],
            "depx": [0, 2, 0, 1],
            "age1": [0, 8, 0, 4],
            "age2": [0, 5, 0, 0],
        }
    )

    stitched = StitchedRunner(records.copy(), pe_min_year=0).run(show_progress=False)
    direct = PolicyEngineRunner(records.copy()).run(show_progress=False)

    assert stitched["taxsimid"].tolist() == [1, 2, 3, 4]
    assert stitched["year"].tolist() == [2023, 2019, 2023, 2019]
    # No column from TAXSIM-35, such as its build stamp.
    assert sorted(stitched.columns) == sorted(direct.columns)
    direct = direct.set_index("taxsimid").loc[stitched["taxsimid"]].reset_index()
    pd.testing.assert_frame_equal(stitched, direct[stitched.columns])
