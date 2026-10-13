"""
Output order must depend on the input alone: not on the process's string-hash
seed, and not on the order a set happens to iterate in.

PolicyEngineRunner used to append its marginal-rate columns by iterating
``{"frate", "srate"}``, a set of strings. Python randomizes string hashing per
process (PYTHONHASHSEED), so the last two columns came out as either
``[..., "srate", "frate"]`` or ``[..., "frate", "srate"]`` depending on the
process. ``pytest tests/`` rewrote the committed
``output/policyengine_taxsim_*_output.csv`` files with a flipped header on some
runs, and anything reading the last two columns by position got the two rates
swapped from one run to the next. #1239 replaced the set with an ordered
tuple. A single-process test cannot reliably catch a regression to a set,
because the order is stable within a process and right in about half of them;
the runner test here runs the same records in two processes whose seeds
iterate that set in opposite orders.

The other tests cover three places where a set's iteration order reached
user-visible output: the API's non-numeric-column error,
``validate_required_columns``, and the row order of ``compare``'s
consolidated CSV.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import policyengine_taxsim
from policyengine_taxsim.comparison.comparator import (
    ComparisonConfig,
    TaxComparator,
)
from policyengine_taxsim.runners.base_runner import BaseTaxRunner

# idtl=2 requests frate and srate. Two years and both filing statuses so the
# per-year frames and their concatenation are exercised as well.
RECORDS = textwrap.dedent(
    """\
    taxsimid,year,state,mstat,page,sage,depx,pwages,swages,idtl
    1,2023,5,2,45,43,0,60000,40000,2
    2,2024,33,1,30,0,0,50000,0,2
    3,2024,5,1,67,0,0,20000,0,2
    """
)

# TAXSIM's header order for these columns. The TAXSIM-35 binary's own output,
# committed as output/taxsim35_joint_household_output.csv, begins
# taxsimid,year,state,fiitax,siitax,fica,frate,srate,ficar,tfica,...
TAXSIM_MARGINAL_RATE_ORDER = ["frate", "srate"]

# The child processes must import the same package this process is testing,
# whether or not it is installed.
PACKAGE_ROOT = str(Path(policyengine_taxsim.__file__).resolve().parents[1])
RUNNER_TIMEOUT_SECONDS = 1800

RUN_RUNNER = textwrap.dedent(
    """\
    import sys

    import pandas as pd

    from policyengine_taxsim.runners.policyengine_runner import (
        PolicyEngineRunner,
    )

    input_path, out_path = sys.argv[1], sys.argv[2]
    df = pd.read_csv(input_path)
    result = PolicyEngineRunner(df).run(show_progress=False)
    with open(out_path, "w") as f:
        f.write(result.to_json(orient="split"))
    """
)


def _child_env(seed: int) -> dict:
    python_path = [PACKAGE_ROOT, os.environ.get("PYTHONPATH", "")]
    return {
        **os.environ,
        "PYTHONHASHSEED": str(seed),
        "PYTHONPATH": os.pathsep.join(path for path in python_path if path),
    }


def _set_orders(seed: int) -> list:
    """How a fresh process with this hash seed iterates the old set, written
    both ways round. When two strings hash to the same slot, the one inserted
    first comes out first, so the two spellings can iterate differently."""
    code = (
        "import json; print(json.dumps("
        "[list({'frate', 'srate'}), list({'srate', 'frate'})]))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env=_child_env(seed),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _seeds_with_opposite_set_order():
    """Two hash seeds under which ``{"frate", "srate"}`` iterates in
    opposite orders on this interpreter, whichever way round it is written.
    Searching (rather than hardcoding seeds) keeps the test meaningful across
    Python versions, whose string hash functions differ."""
    first_orders = _set_orders(0)
    for seed in range(1, 64):
        orders = _set_orders(seed)
        if all(order != first for order, first in zip(orders, first_orders)):
            return 0, seed
    raise AssertionError("No hash seed in 1..63 reversed the set's order")


def test_runner_output_is_independent_of_hash_seed(tmp_path):
    seeds = _seeds_with_opposite_set_order()
    input_path = tmp_path / "input.csv"
    input_path.write_text(RECORDS)
    script_path = tmp_path / "run_runner.py"
    script_path.write_text(RUN_RUNNER)

    # Launch both runs before waiting on either; each spends most of its
    # time importing PolicyEngine-US. Their output goes to files so neither
    # can stall on a full pipe while the other is being waited on.
    processes = {}
    results = {}
    try:
        for seed in seeds:
            with open(tmp_path / f"seed_{seed}.log", "w") as log:
                processes[seed] = subprocess.Popen(
                    [
                        sys.executable,
                        str(script_path),
                        str(input_path),
                        str(tmp_path / f"seed_{seed}.json"),
                    ],
                    env=_child_env(seed),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )

        deadline = time.monotonic() + RUNNER_TIMEOUT_SECONDS
        for seed, process in processes.items():
            process.wait(timeout=max(deadline - time.monotonic(), 1))
            log_text = (tmp_path / f"seed_{seed}.log").read_text()
            assert process.returncode == 0, (
                f"PolicyEngineRunner failed with PYTHONHASHSEED={seed}:\n{log_text}"
            )
            results[seed] = pd.read_json(tmp_path / f"seed_{seed}.json", orient="split")
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.kill()
                process.wait()

    first, second = (results[seed] for seed in seeds)
    assert list(first.columns) == list(second.columns), (
        f"Column order differs between PYTHONHASHSEED={seeds[0]} and "
        f"{seeds[1]}:\n{list(first.columns)}\n{list(second.columns)}"
    )
    pd.testing.assert_frame_equal(first, second)

    columns = list(first.columns)
    assert [c for c in columns if c in TAXSIM_MARGINAL_RATE_ORDER] == (
        TAXSIM_MARGINAL_RATE_ORDER
    )


# --- API: which column the non-numeric error names ---------------------------


@pytest.fixture(scope="module")
def api():
    """policyengine_taxsim.api, imported without Modal installed. The module
    builds its Modal image and app at import time; a stub stands in for
    Modal, and the module is kept out of sys.modules. Only the ``modal``
    entry is put back afterwards, so anything else the import loaded stays
    loaded once."""
    missing = object()
    original = sys.modules.get("modal", missing)
    sys.modules["modal"] = MagicMock()
    try:
        spec = importlib.util.find_spec("policyengine_taxsim.api")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if original is missing:
            del sys.modules["modal"]
        else:
            sys.modules["modal"] = original
    return module


def _csv_with_bad_values(header, bad_columns):
    row = ["abc" if col in bad_columns else "2024" for col in header]
    return ",".join(header) + "\n" + ",".join(row) + "\n"


@pytest.mark.parametrize(
    "header",
    [["year", "pwages", "swages"], ["year", "swages", "pwages"]],
)
def test_api_names_first_non_numeric_column_in_input_order(api, header):
    """With two bad numeric columns, the error names the first one in the
    upload. A set named whichever came first in hash order: the same column
    for both headers within a process, so one of these two cases failed."""
    csv_text = _csv_with_bad_values(header, bad_columns=header[1:])
    with pytest.raises(ValueError, match=f"^Column '{header[1]}'"):
        api._validate_csv(csv_text)


NUMERIC_INPUTS = ["taxsimid", "mstat", "depx", "pwages", "swages", "page", "sage"]


@given(
    header=st.permutations(["year", *NUMERIC_INPUTS]),
    bad_columns=st.sets(st.sampled_from(NUMERIC_INPUTS), min_size=1),
)
@settings(deadline=None)
def test_api_error_names_first_bad_column_for_any_header(api, header, bad_columns):
    first_bad = next(col for col in header if col in bad_columns)
    with pytest.raises(ValueError, match=f"^Column '{first_bad}'"):
        api._validate_csv(_csv_with_bad_values(header, bad_columns))


# --- validate_required_columns: order of the returned lists ------------------


class _Runner(BaseTaxRunner):
    def run(self, show_progress: bool = True) -> pd.DataFrame:
        return self.input_df


# Inputs carry taxsimid because BaseTaxRunner adds it when it is missing.
@pytest.mark.parametrize(
    "required, input_columns, missing, extra",
    [
        (
            ["zeta", "year", "taxsimid", "alpha"],
            ["state", "taxsimid", "year", "mstat"],
            ["zeta", "alpha"],
            ["state", "mstat"],
        ),
        (
            ["alpha", "year", "taxsimid", "zeta"],
            ["mstat", "taxsimid", "year", "state"],
            ["alpha", "zeta"],
            ["mstat", "state"],
        ),
    ],
)
def test_validate_required_columns_keeps_order(required, input_columns, missing, extra):
    df = pd.DataFrame({col: [1] for col in input_columns})
    assert _Runner(df).validate_required_columns(required) == (missing, extra)


def test_validate_required_columns_lists_a_repeated_column_once():
    """A frame built in code can repeat a column name; the set-based version
    reported it once, and so does this one."""
    df = pd.DataFrame([[1, 2, 2024, 7]], columns=["wages", "wages", "year", "taxsimid"])
    missing, extra = _Runner(df).validate_required_columns(["year", "year", "zeta"])
    assert (missing, extra) == (["zeta"], ["wages", "taxsimid"])


COLUMN_NAMES = ["taxsimid", "state", "mstat", "pwages", "swages", "zeta", "alpha"]


def _in_order_of(items, reference):
    """True if items appear in the order they first appear in reference."""
    positions = [list(reference).index(item) for item in items]
    return positions == sorted(positions)


@given(
    required=st.lists(st.sampled_from(["year", *COLUMN_NAMES])),
    other_columns=st.lists(st.sampled_from(COLUMN_NAMES), max_size=10),
    year_position=st.integers(min_value=0, max_value=10),
)
@settings(deadline=None)
def test_validate_required_columns_properties(required, other_columns, year_position):
    # other_columns may repeat a name, as a frame built in code can.
    input_columns = list(other_columns)
    input_columns.insert(min(year_position, len(input_columns)), "year")
    runner = _Runner(pd.DataFrame([[1] * len(input_columns)], columns=input_columns))
    actual_columns = runner.get_columns()

    missing, extra = runner.validate_required_columns(required)

    assert set(missing) == set(required) - set(actual_columns)
    assert set(extra) == set(actual_columns) - set(required)
    assert len(missing) == len(set(missing))
    assert len(extra) == len(set(extra))
    assert _in_order_of(missing, required)
    assert _in_order_of(extra, actual_columns)


# --- compare: row order of the consolidated CSV ------------------------------


def _consolidated_rows(ids):
    taxsim = pd.DataFrame({"taxsimid": ids, "fiitax": 100.0, "siitax": 50.0})
    results = TaxComparator(taxsim, taxsim.copy(), ComparisonConfig()).compare()
    with tempfile.TemporaryDirectory() as output_dir:
        results.save_consolidated_results(Path(output_dir))
        return pd.read_csv(Path(output_dir) / "comparison_results.csv")


def test_consolidated_results_rows_follow_taxsimid():
    """compare's consolidated CSV lists records in taxsimid order, the order
    TaxComparator sorts its frames into. A set of these four IDs iterates as
    1000, 5, 30, 7."""
    written = _consolidated_rows([30, 5, 1000, 7])
    assert written["taxsimid"].tolist() == [5, 5, 7, 7, 30, 30, 1000, 1000]


@given(
    ids=st.lists(
        st.integers(min_value=1, max_value=10**7),
        min_size=1,
        max_size=8,
        unique=True,
    )
)
@settings(max_examples=30, deadline=None)
def test_consolidated_results_rows_are_sorted_pairs(ids):
    """For any IDs in any input order: records ascend by taxsimid, and each
    record's TAXSIM row comes directly before its PolicyEngine row."""
    written = _consolidated_rows(ids)
    assert written["taxsimid"].tolist() == [i for i in sorted(ids) for _ in range(2)]
    assert written["source"].tolist() == ["taxsim", "policyengine"] * len(ids)
