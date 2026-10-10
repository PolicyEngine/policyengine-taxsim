"""docs/input-guide.md's lists of rejected and unchecked inputs match the
emulator.

The guide's "What the emulator rejects" table quotes each error message, and
"Values the emulator does not check" says what happens instead. Each case here
feeds the input to the emulator and checks both that the guide still quotes the
message and that the emulator still behaves that way. The rejections all
happen before any simulation; the unchecked cases are read off the
PolicyEngine inputs the emulator builds, and one simulation covers the cases
that only show in the output. A property-based test checks that amount
columns are conserved on their way into PolicyEngine.
"""

import importlib.util
import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from policyengine_taxsim.runners import PolicyEngineRunner, StitchedRunner

REPO = Path(__file__).resolve().parents[1]
GUIDE = (REPO / "docs" / "input-guide.md").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location(
    "generate_docs_reference", REPO / "scripts" / "generate_docs_reference.py"
)
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)


def _frame(csv: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(csv))


HEADER = "taxsimid,year,state,mstat,pwages\n"

REJECTED = {
    "no year column": (
        StitchedRunner,
        "taxsimid,state,mstat,pwages\n1,5,1,50000\n",
        "Input data must contain a 'year' column",
    ),
    "blank year, command line": (
        StitchedRunner,
        HEADER + "1,,5,1,50000\n",
        "Cannot convert non-finite values (NA or inf) to integer",
    ),
    "blank year, PolicyEngineRunner": (
        PolicyEngineRunner,
        HEADER + "1,,5,1,50000\n",
        "cannot convert float NaN to integer",
    ),
    "state out of range": (
        StitchedRunner,
        HEADER + "1,2023,52,1,50000\n",
        "Record 1: 52 is not a valid TAXSIM SOI state code (0-51)",
    ),
    "state -1": (
        StitchedRunner,
        HEADER + "1,2023,-1,1,50000\n",
        "TAXSIM state -1 (compute every state) is not supported",
    ),
    "state as text": (
        StitchedRunner,
        HEADER + "1,2023,CA,1,50000\n",
        "TAXSIM state code must be a number, got 'CA'",
    ),
    "statefip not a state": (
        StitchedRunner,
        "taxsimid,year,statefip,mstat,pwages\n1,2023,3,1,50000\n",
        "statefip must be a valid US state FIPS code (1-56, including DC) or 0",
    ),
    "state and statefip": (
        StitchedRunner,
        "taxsimid,year,state,statefip,mstat,pwages\n1,2023,5,6,1,50000\n",
        "state 5 and statefip 6 are both nonzero; TAXSIM accepts only one of them",
    ),
    "text in a numeric column": (
        StitchedRunner,
        HEADER + "1,2023,5,1,.\n",
        "could not convert string to float: '.'",
    ),
}


@pytest.mark.parametrize("case", sorted(REJECTED))
def test_guide_quotes_the_error(case):
    message = REJECTED[case][2]
    assert message in GUIDE, f"docs/input-guide.md no longer quotes: {message}"


@pytest.mark.parametrize("case", sorted(REJECTED))
def test_emulator_rejects_the_input(case):
    runner, csv, message = REJECTED[case]
    with pytest.raises(Exception) as error:
        runner(_frame(csv)).run(show_progress=False)
    assert message in str(error.value)


def _inputs(**record) -> dict:
    """The PolicyEngine inputs the emulator builds for one 2023 California
    record."""
    return generator.read_inputs({"year": 2023, "state": 5, **record})["inputs"]


def _same(first: dict, second: dict) -> bool:
    return first.keys() == second.keys() and all(
        np.array_equal(first[name], second[name]) for name in first
    )


@pytest.mark.parametrize("code", [3, 8])
def test_other_filing_status_codes_build_an_unmarried_return(code):
    assert _same(_inputs(mstat=code, pwages=50000), _inputs(mstat=1, pwages=50000))


@pytest.mark.parametrize(
    "column", ["sage", "swages", "ssemp", "sbusinc", "sprofinc", "sui"]
)
def test_spouse_columns_are_ignored_unless_joint(column):
    assert "Spouse columns on non-joint returns" in GUIDE
    for mstat in (1, 6):
        with_value = _inputs(mstat=mstat, pwages=50000, **{column: 30000})
        assert _same(with_value, _inputs(mstat=mstat, pwages=50000)), (column, mstat)


def test_nonprop_has_no_effect_on_policyengine_rows():
    for mstat in (1, 2):
        assert _same(
            _inputs(mstat=mstat, pwages=50000, nonprop=10000),
            _inputs(mstat=mstat, pwages=50000),
        )


def test_negative_amounts_are_passed_through():
    inputs = _inputs(mstat=1, pwages=-5000)
    assert inputs["employment_income"][inputs["is_tax_unit_head"]].tolist() == [-5000]


def test_fractions_in_codes_and_counts_are_cut():
    fractional = generator.read_inputs(
        {"year": 2023.9, "state": 5, "mstat": 2.6, "page": 40.7, "sage": 38.2,
         "depx": 1.9, "age1": 7.9}
    )  # fmt: skip
    whole = generator.read_inputs(
        {
            "year": 2023,
            "state": 5,
            "mstat": 2,
            "page": 40,
            "sage": 38,
            "depx": 1,
            "age1": 7,
        }
    )
    assert fractional["frame"]["year"] == 2023
    assert _same(fractional["inputs"], whole["inputs"])


def test_ages_beyond_depx_are_ignored():
    inputs = _inputs(mstat=1, depx=1, age1=3, age2=4)
    assert inputs["age"][inputs["is_tax_unit_dependent"]].tolist() == [3]


def test_unknown_and_misspelled_columns_are_ignored():
    record = {"year": 2023, "state": 5, "mstat": 1}
    misspelled = generator.read_inputs({**record, "PWAGES": 50000, "wages": 50000})
    assert _same(misspelled["inputs"], generator.read_inputs(record)["inputs"])


def test_missing_value_words_read_as_blank():
    df = _frame("taxsimid,year,state,mstat,pwages,page\n1,2023,5,1,NA,null\n")
    assert df[["pwages", "page"]].isna().all().all()
    inputs = generator.read_inputs(df.iloc[0].to_dict())["inputs"]
    assert inputs["employment_income"].tolist() == [0]
    assert inputs["age"].tolist() == [40]


def test_output_level_claims():
    """One simulation: an idtl other than 0, 2 and 5 leaves the record's
    output cells blank, and duplicate taxsimids are both computed."""
    results = PolicyEngineRunner(
        _frame(
            "taxsimid,year,state,mstat,pwages,idtl\n"
            "1,2023,5,1,50000,7\n"
            "2,2023,5,1,50000,2\n"
            "2,2023,5,1,80000,2\n"
        )
    ).run(show_progress=False)
    odd = results[results["taxsimid"] == 1].iloc[0]
    assert pd.isna(odd["fiitax"]) and pd.isna(odd["siitax"])
    duplicates = results[results["taxsimid"] == 2]
    assert len(duplicates) == 2
    assert duplicates["fiitax"].nunique() == 2


# Columns that go to the spouse, so they count only on joint returns.
SPOUSE_COLUMNS = {"swages", "ssemp", "sbusinc", "sprofinc", "sui"}
# Read on pre-2021 rows only: PolicyEngine rows ignore it (the guide says so,
# and #1245 proposes mapping it). An intended exception to conservation.
UNMAPPED_COLUMNS = {"nonprop"}
AMOUNT_COLUMNS = sorted(
    name
    for name, entry in generator.load_input_metadata().items()
    if entry["type"] == "Dollars per year"
)


@settings(max_examples=75, deadline=None)
@given(
    column=st.sampled_from(AMOUNT_COLUMNS),
    amount=st.integers(min_value=-5_000_000, max_value=5_000_000).filter(bool),
    mstat=st.sampled_from([1, 2, 6]),
    page=st.integers(min_value=18, max_value=95),
    sage=st.integers(min_value=18, max_value=95),
    state=st.integers(min_value=1, max_value=51),
    depx=st.integers(min_value=0, max_value=3),
)
def test_every_dollar_reaches_policyengine_exactly_once(
    column, amount, mstat, page, sage, state, depx
):
    """Conservation: whatever the filing status, ages and state, an amount
    column adds exactly its value to the PolicyEngine inputs, summed over
    people and variables. Splitting between spouses and the pension age rule
    move money between people but never create or lose it. Spouse columns add
    nothing off joint returns, and nonprop adds nothing at all."""
    record = {
        "year": 2023,
        "state": state,
        "mstat": mstat,
        "page": page,
        "sage": sage,
        "depx": depx,
    }
    with_amount = generator.read_inputs({**record, column: amount})
    without = generator.read_inputs({**record, column: 0})
    added = sum(
        float(delta.sum())
        for delta in generator.changed_inputs(with_amount, without).values()
    )
    counts = column not in UNMAPPED_COLUMNS and (
        column not in SPOUSE_COLUMNS or mstat == 2
    )
    assert added == (amount if counts else 0)
