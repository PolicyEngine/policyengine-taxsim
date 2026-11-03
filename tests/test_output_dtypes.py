"""Output amounts are 64-bit floats exact to the cent, and record identifiers
are integers, through every interface.

PolicyEngine computes in 32-bit floating point. The runner used to round in 32
bits, so its amount columns stayed float32, which cannot hold most amounts in
cents: 4009.20 is stored as 4009.199951171875. pandas prints a float32 as the
shortest decimal that identifies it, so PolicyEngine-only output usually looked
clean, but three things went wrong:

- StitchedRunner joins PolicyEngine rows (2021 on) to the TAXSIM binary's
  float64 rows (earlier years). Joining widens float32 to float64, which
  printed 4009.199951171875. The binary prints ``taxsimid`` as "1.", so the
  joined column printed as 1.0.
- Rounding a float32 array scales it by 100 in 32 bits. That can move a value
  near a half-cent to the other side, and from $41,943.04 up the scaled value
  has no room for fractions of a cent: 44737.546875 came out as 44737.54
  instead of 44737.55.
- A .dta file stored the amounts as Stata floats, and a CSV printed some
  amounts from $131,072 up with one decimal place or, with pandas 3, in
  scientific notation from $1 million.

The invariants pinned here, for PolicyEngine-only and mixed-year inputs:

1. Every amount equals itself rounded to 2 decimals in float64 (rates: 4).
2. Amounts are float64, never float32.
3. ``taxsimid``, ``year`` and ``state`` are integers when their values are
   whole numbers, and no identifier value ever changes.
4. A PolicyEngine record's output is the same whether or not the input also
   holds records for the TAXSIM binary.
5. The rounding agrees with exact decimal arithmetic on the 32-bit value.
"""

import csv
import decimal
import io
import math
import re
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner
from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from policyengine_taxsim.cli import cli
from policyengine_taxsim.core.io import write_output
from policyengine_taxsim.core.output_dtypes import (
    IDENTIFIER_COLUMNS,
    identifiers_as_integers,
    round_float64,
)
from policyengine_taxsim.runners import PolicyEngineRunner, StitchedRunner
from policyengine_taxsim.runners import stitched_runner

# Marginal rates are percentages kept to 4 decimals; everything else that is
# not an identifier is an amount in dollars and cents.
RATE_COLUMNS = ("frate", "srate", "ficar")

PE_YEARS = (2021, 2022, 2023, 2024, 2025)
TAXSIM_YEARS = (1995, 2005, 2015, 2019, 2020)

WHOLE_NUMBER = re.compile(r"-?\d+")
AMOUNT = re.compile(r"-?\d+(\.\d{1,2})?")
RATE = re.compile(r"-?\d+(\.\d{1,4})?")


def decimals_of(column):
    return 4 if column in RATE_COLUMNS else 2


def assert_number_types(df):
    """Invariants 1 to 3 on a result table."""
    for column in IDENTIFIER_COLUMNS:
        assert pd.api.types.is_integer_dtype(df[column].dtype), (
            f"{column} is {df[column].dtype}"
        )
    for column in df.columns:
        if column in IDENTIFIER_COLUMNS:
            continue
        dtype = df[column].dtype
        assert pd.api.types.is_numeric_dtype(dtype), f"{column} is {dtype}"
        if pd.api.types.is_float_dtype(dtype):
            assert dtype == np.float64, f"{column} is {dtype}"
        values = df[column].to_numpy(dtype=np.float64)
        rounded = np.round(values, decimals_of(column))
        assert np.array_equal(values, rounded, equal_nan=True), (
            f"{column} holds {values[values != rounded][:3]}"
        )


def assert_csv_text(text):
    """The same invariants on what a user reads: no cell carries more
    decimals than its column allows, and identifiers have none."""
    rows = [row for row in csv.reader(io.StringIO(text)) if row]
    header, records = rows[0], rows[1:]
    assert records
    for record in records:
        assert len(record) == len(header)
        for column, cell in zip(header, record):
            if column in IDENTIFIER_COLUMNS:
                assert WHOLE_NUMBER.fullmatch(cell), f"{column} printed as {cell}"
            elif cell:
                pattern = RATE if column in RATE_COLUMNS else AMOUNT
                assert pattern.fullmatch(cell), f"{column} printed as {cell}"


def csv_part(stdout):
    """The CSV in the stdin command's stdout. Until #1412 the TAXSIM runner
    prints its progress there too, ahead of the header."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    start = next(i for i, line in enumerate(lines) if line.startswith("taxsimid,"))
    return "\n".join(lines[start:]) + "\n"


def holds_cents_float32_cannot(df):
    """Whether the table has an amount that 32 bits cannot hold exactly, so
    that 32-bit amounts would have failed the checks above."""
    amounts = df.drop(columns=list(IDENTIFIER_COLUMNS)).to_numpy(dtype=np.float64)
    amounts = amounts[np.isfinite(amounts)]
    return bool((amounts != amounts.astype(np.float32).astype(np.float64)).any())


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------

# Every 32-bit float up to about a trillion dollars.
float32_amounts = st.floats(
    min_value=-(2.0**40), max_value=2.0**40, width=32, allow_nan=False
)


def test_rounding_in_32_bits_was_the_defect():
    computed = np.float32(4009.2)
    in_32_bits = np.round(np.array([computed]), 2)
    assert in_32_bits.dtype == np.float32
    assert float(in_32_bits[0]) == 4009.199951171875

    assert round_float64(np.array([computed])).tolist() == [4009.2]
    # An amount whose half-cent 32 bits drop when scaling by 100.
    stored = np.array([44737.546875], dtype=np.float32)
    assert f"{np.round(stored, 2)[0]:.2f}" == "44737.54"
    assert round_float64(stored).tolist() == [44737.55]


@settings(max_examples=500, deadline=None)
@given(st.lists(float32_amounts, min_size=1, max_size=20))
def test_rounding_agrees_with_exact_decimal_arithmetic(values):
    """Differential test: numpy's float64 rounding of a 32-bit value against
    Python's decimal module rounding the same value half to even."""
    computed = np.array(values, dtype=np.float32)

    rounded = round_float64(computed)

    assert rounded.dtype == np.float64
    cent = decimal.Decimal("0.01")
    exact = [
        float(
            decimal.Decimal(float(value)).quantize(
                cent, rounding=decimal.ROUND_HALF_EVEN
            )
        )
        for value in computed
    ]
    assert rounded.tolist() == exact
    assert np.array_equal(rounded, np.round(rounded, 2))


@settings(max_examples=500, deadline=None)
@given(
    values=st.lists(
        st.floats(min_value=-1e9, max_value=1e9, allow_nan=False),
        min_size=1,
        max_size=20,
    ),
    decimals=st.sampled_from([2, 4]),
    width=st.sampled_from([np.float32, np.float64]),
)
def test_rounded_values_equal_themselves_rounded(values, decimals, width):
    computed = np.array(values, dtype=width)

    rounded = round_float64(computed, decimals)

    assert rounded.dtype == np.float64
    assert np.array_equal(rounded, np.round(rounded, decimals))
    # Never further from the computed value than half a unit in the last
    # place kept, apart from float64's own error in scaling by a power of 10.
    distance = np.abs(rounded - computed.astype(np.float64))
    assert (distance <= 0.5 * 10.0**-decimals + 1e-6).all()


def test_rounding_keeps_missing_values():
    rounded = round_float64(np.array([np.nan, 1.005], dtype=np.float32))
    assert math.isnan(rounded[0]) and rounded[1] == 1.0


# ---------------------------------------------------------------------------
# Identifier columns
# ---------------------------------------------------------------------------

# Every whole number a float64 holds exactly.
whole_numbers = st.integers(min_value=-(2**53), max_value=2**53)
not_whole_numbers = st.one_of(
    st.sampled_from([math.nan, math.inf, -math.inf, 2.0**63, -(2.0**64), 1e300]),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False).filter(
        lambda value: value != int(value)
    ),
)


@settings(max_examples=300, deadline=None)
@given(
    values=st.lists(whole_numbers, min_size=1, max_size=20),
    column=st.sampled_from(IDENTIFIER_COLUMNS),
    dtype=st.sampled_from(["float64", "Float64"]),
)
def test_whole_number_identifiers_become_int64(values, column, dtype):
    df = pd.DataFrame({column: pd.array(values, dtype=dtype), "fiitax": 100.0})

    result = identifiers_as_integers(df)

    assert result[column].dtype == np.int64
    assert result[column].tolist() == values
    # A whole-dollar amount is still an amount.
    assert result["fiitax"].dtype == np.float64


@settings(max_examples=300, deadline=None)
@given(
    values=st.lists(whole_numbers, max_size=20),
    other=not_whole_numbers,
    position=st.integers(min_value=0, max_value=20),
    column=st.sampled_from(IDENTIFIER_COLUMNS),
)
def test_identifiers_with_a_fraction_or_a_gap_are_left_alone(
    values, other, position, column
):
    values = [float(value) for value in values]
    values.insert(min(position, len(values)), other)
    df = pd.DataFrame({column: values})

    result = identifiers_as_integers(df.copy())

    pd.testing.assert_frame_equal(result, df)


@pytest.mark.parametrize("dtype", ["int8", "int16", "int32", "int64", "uint32"])
def test_integer_identifiers_keep_their_type(dtype):
    df = pd.DataFrame({"taxsimid": np.array([1, 2, 3], dtype=dtype)})

    result = identifiers_as_integers(df.copy())

    pd.testing.assert_frame_equal(result, df)


def test_float32_identifiers_from_a_stata_file_become_integers(tmp_path):
    """Stata's default numeric type is a 4-byte float, so an ID generated
    there arrives as float32."""
    path = tmp_path / "ids.dta"
    pd.DataFrame({"taxsimid": np.array([1, 2], dtype=np.float32)}).to_stata(
        path, write_index=False
    )
    from_stata = pd.read_stata(path)
    assert from_stata["taxsimid"].dtype == np.float32

    result = identifiers_as_integers(from_stata)

    assert result["taxsimid"].dtype == np.int64
    assert result["taxsimid"].tolist() == [1, 2]


# ---------------------------------------------------------------------------
# Stitching, with both engines replaced by tables
# ---------------------------------------------------------------------------

cents = st.integers(min_value=-(10**9), max_value=10**9).map(lambda c: c / 100)


@settings(max_examples=200, deadline=None)
@given(data=st.data())
def test_stitching_changes_no_value_and_returns_integer_identifiers(data):
    """Whatever the two engines return, the stitched table holds the same
    numbers in input order, and its identifiers are integers."""
    engines = data.draw(
        st.lists(st.sampled_from(["pe", "taxsim"]), min_size=1, max_size=12)
    )
    n = len(engines)
    ids = data.draw(st.lists(st.integers(1, 10**6), min_size=n, max_size=n))
    amounts = data.draw(st.lists(cents, min_size=n, max_size=n))
    # One year per engine, so PolicyEngineRunner's rows are in input order
    # whether it sorts by year or not.
    years = [2023 if engine == "pe" else 2019 for engine in engines]
    input_df = pd.DataFrame(
        {"taxsimid": ids, "year": years, "state": 6, "mstat": 1, "pwages": 50000}
    )

    def engine_output(engine, id_dtype):
        rows = [i for i in range(n) if engines[i] == engine]
        return pd.DataFrame(
            {
                "taxsimid": np.array([ids[i] for i in rows], dtype=id_dtype),
                "year": [years[i] for i in rows],
                "state": 6,
                "fiitax": np.array([amounts[i] for i in rows], dtype=np.float64),
            }
        )

    with (
        patch.object(stitched_runner, "PolicyEngineRunner") as policyengine,
        patch("policyengine_taxsim.runners.taxsim_runner.TaxsimRunner") as taxsim,
    ):
        policyengine.return_value.run.return_value = engine_output("pe", np.int64)
        # The binary's record ID parses as a float.
        taxsim.return_value.run.return_value = engine_output("taxsim", np.float64)
        result = StitchedRunner(input_df).run(show_progress=False)

    assert_number_types(result)
    assert result["taxsimid"].dtype == np.int64
    assert result["taxsimid"].tolist() == ids
    assert result["year"].tolist() == years
    assert result["fiitax"].tolist() == amounts


# ---------------------------------------------------------------------------
# Both engines for real
# ---------------------------------------------------------------------------

# The pair from the report (a 2019 record for the TAXSIM binary, a 2023 one
# for PolicyEngine), and a record whose wages 32 bits cannot hold exactly. The
# PolicyEngine records share a year: the runner simulates each year apart.
MIXED_CSV = (
    "taxsimid,year,state,mstat,page,pwages,idtl\n"
    "1,2019,5,1,40,50000,2\n"
    "2,2023,33,1,30,52000,2\n"
    "3,2023,22,1,45,81234.56,2\n"
)


def mixed_input():
    return pd.read_csv(io.StringIO(MIXED_CSV))


@pytest.fixture(scope="module")
def mixed_result():
    return StitchedRunner(mixed_input()).run(show_progress=False)


@pytest.fixture(scope="module")
def policyengine_only_result():
    records = mixed_input()
    records = records[records["year"] >= StitchedRunner.PE_MIN_YEAR]
    return PolicyEngineRunner(records).run(show_progress=False)


def test_policyengine_runner_returns_cents_in_float64(policyengine_only_result):
    assert_number_types(policyengine_only_result)
    assert_csv_text(policyengine_only_result.to_csv(index=False))
    assert policyengine_only_result["taxsimid"].tolist() == [2, 3]
    assert holds_cents_float32_cannot(policyengine_only_result)


def test_stitched_runner_returns_cents_in_float64_for_mixed_years(mixed_result):
    assert_number_types(mixed_result)
    assert_csv_text(mixed_result.to_csv(index=False))
    assert mixed_result["taxsimid"].tolist() == [1, 2, 3]
    assert mixed_result["year"].tolist() == [2019, 2023, 2023]
    assert mixed_result["state"].tolist() == [5, 33, 22]
    policyengine_rows = mixed_result[mixed_result["year"] >= 2021]
    assert holds_cents_float32_cannot(policyengine_rows)


def test_policyengine_rows_do_not_depend_on_taxsim_rows(
    mixed_result, policyengine_only_result
):
    """Invariant 4: the same PolicyEngine records, alone and beside a record
    for the TAXSIM binary, give the same table."""
    columns = list(policyengine_only_result.columns)
    beside_taxsim = mixed_result[mixed_result["year"] >= 2021][columns]

    pd.testing.assert_frame_equal(
        beside_taxsim.reset_index(drop=True),
        policyengine_only_result.reset_index(drop=True),
    )
    assert beside_taxsim.to_csv(index=False) == policyengine_only_result.to_csv(
        index=False
    )


def test_stitched_runner_returns_integer_ids_for_taxsim_only_input():
    records = mixed_input()
    records = records[records["year"] < StitchedRunner.PE_MIN_YEAR]

    result = StitchedRunner(records).run(show_progress=False)

    assert_number_types(result)
    assert result["taxsimid"].tolist() == [1]


def test_stdin_command_writes_cents_and_integer_ids_for_mixed_years():
    """In process; test_public_contract.py runs the installed command."""
    invoked = CliRunner().invoke(cli, [], input=MIXED_CSV)

    assert invoked.exit_code == 0, invoked.output
    text = csv_part(invoked.stdout)
    assert_csv_text(text)
    result = pd.read_csv(io.StringIO(text))
    assert_number_types(result)
    assert result["taxsimid"].tolist() == [1, 2, 3]


@pytest.mark.parametrize("extension", ["csv", "dta"])
def test_policyengine_subcommand_writes_cents_and_integer_ids(tmp_path, extension):
    input_path = tmp_path / "mixed.csv"
    input_path.write_text(MIXED_CSV)
    output_path = tmp_path / f"output.{extension}"

    invoked = CliRunner().invoke(
        cli, ["policyengine", str(input_path), "-o", str(output_path)]
    )

    assert invoked.exit_code == 0, invoked.output
    if extension == "csv":
        assert_csv_text(output_path.read_text())
        result = pd.read_csv(output_path)
    else:
        result = pd.read_stata(output_path)
    assert_number_types(result)
    assert result["taxsimid"].tolist() == [1, 2, 3]
    assert holds_cents_float32_cannot(result[result["year"] >= 2021])


def test_stata_output_stores_policyengine_amounts_as_doubles(
    tmp_path, policyengine_only_result
):
    """A Stata float is 32 bits: `tfica == 4009.2` is false for it."""
    path = tmp_path / "output.dta"

    write_output(policyengine_only_result, path)

    from_stata = pd.read_stata(path)
    assert_number_types(from_stata)
    pd.testing.assert_frame_equal(
        from_stata, policyengine_only_result, check_dtype=False
    )


# ---------------------------------------------------------------------------
# Both engines for real, on generated records
# ---------------------------------------------------------------------------

dollars_and_cents = st.integers(min_value=0, max_value=500_000_000).map(
    lambda c: c / 100
)
sometimes = st.one_of(st.just(0.0), dollars_and_cents)


@st.composite
def taxsim_record(draw, years):
    married = draw(st.booleans())
    dependents = draw(st.integers(min_value=0, max_value=3))
    record = {
        "year": draw(st.sampled_from(years)),
        "state": draw(st.integers(min_value=0, max_value=51)),
        "mstat": 2 if married else 1,
        "page": draw(st.integers(min_value=18, max_value=85)),
        "sage": draw(st.integers(min_value=18, max_value=85)) if married else 0,
        "depx": dependents,
        "pwages": draw(dollars_and_cents),
        "swages": draw(sometimes) if married else 0.0,
        "intrec": draw(sometimes),
        "dividends": draw(sometimes),
        "ltcg": draw(sometimes),
        "proptax": draw(sometimes),
    }
    for i in (1, 2, 3):
        record[f"age{i}"] = (
            draw(st.integers(min_value=1, max_value=17)) if i <= dependents else 0
        )
    return record


# Each example runs PolicyEngine, so these tests take a few examples and do not
# shrink a failure, which would rerun the simulation many times. A failing
# example is reported as generated.
POLICYENGINE_EXAMPLES = settings(
    max_examples=4,
    deadline=None,
    derandomize=True,
    phases=[Phase.explicit, Phase.generate],
)


@st.composite
def taxsim_input(draw, mixed_years):
    """Two to five records with distinct IDs. A mixed-year input has at least
    one record for each engine. The identifier columns arrive as integers or
    as whole-number floats, as they do from a Stata or R data frame."""
    if mixed_years:
        records = [
            draw(taxsim_record(TAXSIM_YEARS)),
            draw(taxsim_record(PE_YEARS)),
            *draw(st.lists(taxsim_record(TAXSIM_YEARS + PE_YEARS), max_size=3)),
        ]
    else:
        records = draw(st.lists(taxsim_record(PE_YEARS), min_size=2, max_size=5))
    records = draw(st.permutations(records))
    ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=10**6),
            min_size=len(records),
            max_size=len(records),
            unique=True,
        )
    )
    df = pd.DataFrame(records)
    df.insert(0, "taxsimid", ids)
    df["idtl"] = draw(st.sampled_from([0, 2]))
    identifier_type = draw(st.sampled_from([np.int64, np.float64]))
    for column in IDENTIFIER_COLUMNS:
        df[column] = df[column].astype(identifier_type)
    return df


@POLICYENGINE_EXAMPLES
@given(input_df=taxsim_input(mixed_years=False))
def test_every_policyengine_amount_equals_itself_rounded_to_cents(input_df):
    result = PolicyEngineRunner(input_df).run(show_progress=False)

    assert_number_types(result)
    assert_csv_text(result.to_csv(index=False))
    assert sorted(result["taxsimid"]) == sorted(input_df["taxsimid"].astype(int))


class RecordingPolicyEngineRunner(PolicyEngineRunner):
    """PolicyEngineRunner that keeps the table it returned."""

    returned = []

    def run(self, *args, **kwargs):
        result = super().run(*args, **kwargs)
        self.returned.append(result.copy())
        return result


@POLICYENGINE_EXAMPLES
@given(input_df=taxsim_input(mixed_years=True))
def test_every_mixed_year_amount_equals_itself_rounded_to_cents(input_df):
    RecordingPolicyEngineRunner.returned.clear()
    with patch.object(
        stitched_runner, "PolicyEngineRunner", RecordingPolicyEngineRunner
    ):
        result = StitchedRunner(input_df).run(show_progress=False)

    assert_number_types(result)
    assert_csv_text(result.to_csv(index=False))
    assert result["taxsimid"].tolist() == input_df["taxsimid"].astype(int).tolist()
    assert result["year"].tolist() == input_df["year"].astype(int).tolist()
    assert result["state"].tolist() == input_df["state"].astype(int).tolist()

    # Invariant 4: stitching leaves PolicyEngine's rows exactly as
    # PolicyEngineRunner returned them.
    (alone,) = RecordingPolicyEngineRunner.returned
    alone = alone.sort_values("taxsimid").reset_index(drop=True)
    stitched = result[result["year"] >= StitchedRunner.PE_MIN_YEAR]
    stitched = stitched.sort_values("taxsimid").reset_index(drop=True)
    pd.testing.assert_frame_equal(stitched[list(alone.columns)], alone)
    assert stitched[list(alone.columns)].to_csv(index=False) == alone.to_csv(
        index=False
    )
