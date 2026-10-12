"""
The position of an output column must not depend on what else is in the batch.

PolicyEngineRunner simulates one tax year at a time. Each chunk's frame carries
only the columns its rows' idtl levels ask for, and the chunks are joined with
pd.concat, which keeps columns in order of first appearance. So the same two
records put frate in column 8 when the 2021 record had idtl=0 and the 2022
record idtl=2, and in column 40 the other way round (taxsim #1426).

run() now puts the joined frame in one canonical order: the identifiers, the
implemented columns in the order of the policyengine_to_taxsim mapping, then
the marginal rates. That is the order a batch with a single idtl level already
had, so those batches keep their layout.

The real-run tests take the frame before reordering from ``_run_once`` and
compare it with the reordered frame, so "unchanged" is checked against what
the runner produced before this ordering existed.
"""

import io

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

HEADER = "taxsimid,year,state,mstat,page,pwages,idtl\n"
IDENTIFIERS = ["taxsimid", "year", "state"]


def _records(rows: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(HEADER + rows))


@pytest.fixture(scope="module")
def runner():
    return PolicyEngineRunner(_records("1,2022,5,1,40,50000,2\n"), logs=False)


@pytest.fixture(scope="module")
def canonical(runner):
    return runner._canonical_output_columns()


# --- The canonical order itself ----------------------------------------------


def test_canonical_order_covers_the_implemented_columns_once(runner, canonical):
    implemented = [
        taxsim_var
        for taxsim_var, mapping in runner.mappings["policyengine_to_taxsim"].items()
        if mapping.get("implemented", False)
    ]
    assert sorted(canonical) == sorted(implemented)
    assert len(canonical) == len(set(canonical))


def test_canonical_order_starts_with_identifiers_and_ends_with_marginal_rates(
    canonical,
):
    """frate before srate is TAXSIM's order: the TAXSIM-35 binary's output,
    committed as output/taxsim35_joint_household_output.csv, has
    ...,fica,frate,srate,ficar,... . They come last because the runner
    computes them after every other column."""
    assert canonical[:3] == IDENTIFIERS
    assert canonical[-2:] == ["frate", "srate"]


# --- Ordering a frame --------------------------------------------------------


@given(data=st.data())
@settings(deadline=None)
def test_order_columns_properties(runner, canonical, data):
    """For any frame: the same columns come back, known ones in canonical
    order, unknown ones after them in the order they arrived, and every value
    stays under its own column name."""
    known = data.draw(st.lists(st.sampled_from(canonical), unique=True))
    unknown = data.draw(
        st.lists(st.sampled_from(["cd2026081819", "extra", "a"]), unique=True)
    )
    columns = data.draw(st.permutations(known + unknown))
    frame = pd.DataFrame([list(range(len(columns)))], columns=columns)

    ordered = runner._order_columns(frame)

    result = list(ordered.columns)
    assert sorted(result) == sorted(columns)
    assert result[: len(known)] == [c for c in canonical if c in known]
    assert result[len(known) :] == [c for c in columns if c in unknown]
    for column in columns:
        assert ordered[column].iloc[0] == frame[column].iloc[0]


@given(data=st.data())
@settings(deadline=None)
def test_layout_does_not_depend_on_chunk_order(runner, canonical, data):
    """Chunks that each carry some subset of the columns give one layout,
    whichever chunk comes first."""
    subsets = data.draw(
        st.lists(
            st.sets(st.sampled_from(canonical), min_size=1),
            min_size=1,
            max_size=4,
        )
    )
    order = data.draw(st.permutations(range(len(subsets))))

    def layout(chunk_subsets):
        chunks = [
            pd.DataFrame(
                [[1.0] * len(subset)], columns=[c for c in canonical if c in subset]
            )
            for subset in chunk_subsets
        ]
        return list(runner._order_columns(pd.concat(chunks)).columns)

    carried = set().union(*subsets)
    assert layout(subsets) == [c for c in canonical if c in carried]
    assert layout([subsets[i] for i in order]) == layout(subsets)


def test_run_returns_the_canonical_order(canonical):
    """run() applies the ordering to whatever the simulation pass returns."""
    runner = PolicyEngineRunner(_records("1,2022,5,1,40,50000,0\n"), logs=False)
    joined = pd.DataFrame(
        [[4.0, 3.0, 2.0, 1, 2022, 5]],
        columns=["v10", "srate", "frate", "taxsimid", "year", "state"],
    )
    runner._run_once = lambda show_progress, on_progress: joined

    result = runner.run(show_progress=False)

    assert list(result.columns) == [*IDENTIFIERS, "v10", "frate", "srate"]
    assert result.iloc[0].tolist() == [1, 2022, 5, 4.0, 2.0, 3.0]


# --- Real runs ---------------------------------------------------------------

BATCHES = {
    # The two batches from #1426: the same two records, with the idtl levels
    # swapped between the years.
    "idtl0_then_idtl2": "1,2021,5,1,40,50000,0\n2,2022,5,1,40,50000,2\n",
    "idtl2_then_idtl0": "1,2021,5,1,40,50000,2\n2,2022,5,1,40,50000,0\n",
    # Batches with a single idtl level.
    "idtl2": "1,2021,5,1,40,50000,2\n2,2022,5,1,40,50000,2\n",
    "idtl0": "1,2022,5,1,40,50000,0\n",
    "idtl5": "1,2022,5,1,40,50000,5\n",
}


@pytest.fixture(scope="module")
def frames():
    """Each batch's joined frame before and after ordering."""
    results = {}
    for name, rows in BATCHES.items():
        batch_runner = PolicyEngineRunner(_records(rows), logs=False)
        before = batch_runner._run_once(False, None)
        results[name] = (before, batch_runner._order_columns(before))
    return results


@pytest.mark.parametrize("batch", ["idtl2", "idtl0", "idtl5"])
def test_single_idtl_batch_keeps_its_layout(frames, batch):
    before, after = frames[batch]
    assert list(after.columns) == list(before.columns)


def test_mixed_batches_get_the_full_detail_layout(frames):
    full_layout = list(frames["idtl2"][1].columns)
    assert list(frames["idtl0_then_idtl2"][1].columns) == full_layout
    assert list(frames["idtl2_then_idtl0"][1].columns) == full_layout


@pytest.mark.parametrize(
    "batch, full_detail_id, standard_id",
    [("idtl0_then_idtl2", 2, 1), ("idtl2_then_idtl0", 1, 2)],
)
def test_mixed_batch_values_stay_with_their_columns(
    frames, batch, full_detail_id, standard_id
):
    """Each record's values in a mixed batch match its values in the full
    batch, column by column: all of them for the idtl=2 record, and the
    standard columns for the idtl=0 record, whose other columns are empty."""
    mixed = frames[batch][1].set_index("taxsimid")
    full = frames["idtl2"][1].set_index("taxsimid")
    standard_columns = [c for c in frames["idtl0"][1].columns if c != "taxsimid"]

    np.testing.assert_allclose(
        mixed.loc[full_detail_id].to_numpy(dtype=float),
        full.loc[full_detail_id, mixed.columns].to_numpy(dtype=float),
    )
    np.testing.assert_allclose(
        mixed.loc[standard_id, standard_columns].to_numpy(dtype=float),
        full.loc[standard_id, standard_columns].to_numpy(dtype=float),
    )
    other_columns = [c for c in mixed.columns if c not in standard_columns]
    assert mixed.loc[standard_id, other_columns].isna().all()
