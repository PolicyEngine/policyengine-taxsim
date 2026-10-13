"""TAXSIM-32 dependent counts (`dep13`, `dep17`, `dep18`) on the
Microsimulation path.

Callers without individual dependent ages -- notably BLS's Consumer
Expenditure Survey, whose NTAXI files carry only DEPCNT, DEPUND13, DEPUND17
and DEPUND18 -- describe dependents with cumulative counts: `dep13` under 13,
`dep17` under 17, `dep18` under 18, and `depx - dep18` adult dependents.
taxsimtest accepts these columns directly.

`TaxsimMicrosimDataset.generate` pads the input with zero-filled `age1..age10`
(and `dep13/dep17/dep18`) before converting, so the conversion used to see
"individual ages present" and skip itself. Every dependent then defaulted to
age 10, giving adult dependents the EITC and refundable CTC that taxsimtest
denies them (a single filer with two adult dependents and $30K of wages:
taxsimtest $0, emulator -$7,907). The conversion now keys off the columns the
caller supplied.

Ground truth: the bundled binary run on the raw count columns (not the
emulator's own age conversion).
"""

import pandas as pd
import pytest

from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

PA, CA, NY, TX = 39, 5, 33, 44

_COLUMNS = [
    "taxsimid",
    "year",
    "state",
    "mstat",
    "page",
    "sage",
    "depx",
    "dep13",
    "dep17",
    "dep18",
    "pwages",
    "swages",
]
_RECORDS = [
    # Single, two adult dependents: head of household and $500 credits for
    # other dependents, but no EITC or CTC.
    (1, 2023, PA, 1, 45, 0, 2, 0, 0, 0, 30_000, 0),
    # Same filer without dependents (control).
    (2, 2023, PA, 1, 45, 0, 0, 0, 0, 0, 30_000, 0),
    # Married, two adult dependents.
    (3, 2023, PA, 2, 45, 45, 2, 0, 0, 0, 60_000, 0),
    # Single, one adult dependent, low income.
    (4, 2023, PA, 1, 45, 0, 1, 0, 0, 0, 20_000, 0),
    # Married, dependents aged under 13, 13-16 and 17.
    (5, 2023, PA, 2, 40, 40, 3, 1, 2, 3, 50_000, 0),
    # Single, one dependent in each band plus an adult.
    (6, 2023, PA, 1, 40, 0, 4, 1, 2, 3, 35_000, 0),
    # California married couple, two children under 13.
    (8, 2022, CA, 2, 40, 40, 3, 2, 2, 2, 45_000, 15_000),
    # New York single parent of a 13-16-year-old and an adult dependent.
    (9, 2024, NY, 1, 50, 0, 2, 0, 1, 1, 25_000, 0),
    # Texas married couple with an adult dependent, 2025.
    (10, 2025, TX, 2, 55, 50, 1, 0, 0, 0, 80_000, 0),
]
_IDS = [r[0] for r in _RECORDS]
_OUTPUTS = ["fiitax", "siitax", "v13", "v18", "v22", "v25"]


def _frame(records=_RECORDS, columns=_COLUMNS):
    df = pd.DataFrame(records, columns=columns)
    df["idtl"] = 2
    return df


def _by_id(result):
    result = result.copy()
    result["taxsimid"] = result["taxsimid"].astype(float).astype(int)
    return result.set_index("taxsimid")


def _run_binary_on_raw_counts(df, tmp_path):
    """Run taxsimtest on the count columns as given. TaxsimRunner.run would
    first convert them to ages with the emulator's own converter, which is
    not independent ground truth."""
    runner = TaxsimRunner(df)
    input_file = tmp_path / "taxsim_in.csv"
    output_file = tmp_path / "taxsim_out.csv"
    df.to_csv(input_file, index=False)
    runner._execute_taxsim(str(input_file), str(output_file))
    return _by_id(runner._parse_taxsim_output(str(output_file)))


@pytest.fixture(scope="module")
def taxsim(tmp_path_factory):
    return _run_binary_on_raw_counts(_frame(), tmp_path_factory.mktemp("taxsim"))


@pytest.fixture(scope="module")
def emulator():
    return _by_id(PolicyEngineRunner(_frame(), logs=False).run(show_progress=False))


@pytest.mark.parametrize("taxsimid", _IDS)
def test_emulator_matches_binary_on_dependent_counts(taxsim, emulator, taxsimid):
    for col in _OUTPUTS:
        assert emulator.loc[taxsimid, col] == pytest.approx(
            taxsim.loc[taxsimid, col], abs=1.0
        ), (
            f"record {taxsimid} {col}: emulator {emulator.loc[taxsimid, col]:.2f} "
            f"vs taxsimtest {taxsim.loc[taxsimid, col]:.2f}"
        )


def test_adult_dependents_get_no_eitc_or_ctc(taxsim, emulator):
    for frame in (taxsim, emulator):
        assert frame.loc[1, "v25"] == pytest.approx(0, abs=0.01)
        assert frame.loc[1, "fiitax"] == pytest.approx(0, abs=0.01)
        # Head-of-household standard deduction (2023: $20,800).
        assert frame.loc[1, "v13"] == pytest.approx(20_800, abs=0.01)


def _convert(df):
    """Run only the dataset's default/conversion step, as generate() does."""
    dataset = TaxsimMicrosimDataset.__new__(TaxsimMicrosimDataset)
    supplied = set(df.columns)
    padded = dataset._ensure_required_columns(df.copy())
    return dataset._apply_defaults_vectorized(padded, supplied)


class TestConversion:
    def test_counts_become_band_ages(self):
        df = _frame([(1, 2023, PA, 1, 40, 0, 4, 1, 2, 3, 35_000, 0)])
        row = _convert(df).iloc[0]
        assert [row[f"age{i}"] for i in range(1, 5)] == [10, 15, 17, 21]
        assert row["depx"] == 4

    def test_depx_raised_to_dep18(self):
        df = _frame([(1, 2023, PA, 1, 40, 0, 1, 0, 0, 2, 35_000, 0)])
        row = _convert(df).iloc[0]
        assert row["depx"] == 2
        assert [row["age1"], row["age2"]] == [17, 17]

    def test_explicit_ages_take_precedence(self):
        df = _frame([(1, 2023, PA, 1, 40, 0, 2, 0, 0, 0, 35_000, 0)])
        df["age1"], df["age2"] = 5, 16
        row = _convert(df).iloc[0]
        assert [row["age1"], row["age2"]] == [5, 16]

    def test_depx_alone_still_means_children(self):
        """With neither ages nor counts, TAXSIM treats `depx` as the number
        of EITC-qualifying children, so the dependents stay children."""
        df = pd.DataFrame(
            [dict(taxsimid=1, year=2023, state=PA, mstat=1, depx=2, pwages=30_000)]
        )
        row = _convert(df).iloc[0]
        assert [row["age1"], row["age2"]] == [10, 10]


def test_2021_seventeen_year_old_gets_arpa_ctc(tmp_path):
    """Known divergence from taxsimtest. For 2021 "the child tax credit
    applies to qualifying children who have not attained age 18 by the end
    of 2021" (2021 Schedule 8812 instructions). Given explicit ages (10 and 17),
    taxsimtest allows $6,000; given the equivalent counts (dep13=1, dep17=1,
    dep18=2) it takes `dep17` as the CTC count and allows $3,000 + $500. The
    emulator converts counts to ages, so it follows the ages result."""
    counts = _frame([(7, 2021, PA, 2, 40, 40, 2, 1, 1, 2, 70_000, 0)])
    ages = counts.drop(columns=["dep13", "dep17", "dep18"]).assign(age1=10, age2=17)
    binary_ages = _run_binary_on_raw_counts(ages, tmp_path)
    emulator = _by_id(PolicyEngineRunner(counts, logs=False).run(show_progress=False))
    assert binary_ages.loc[7, "v22"] == pytest.approx(6_000, abs=0.01)
    assert emulator.loc[7, "v22"] == pytest.approx(6_000, abs=0.01)
    assert emulator.loc[7, "fiitax"] == pytest.approx(
        binary_ages.loc[7, "fiitax"], abs=1.0
    )
