"""
TAXSIM `nonprop` (other non-property income, +/-) -> PolicyEngine routing.

TAXSIM documentation (https://taxsim.nber.org/taxsimtest/, input 15):

    nonprop Other non-property income in AGI not subject to Medicare NIIT
    such as: alimony, nonwage fellowships, state income tax refunds
    (itemizers only). Adjustments and items such as alimony paid, Keogh and
    IRA contributions, foreign income exclusion, NOLs can be entered here as
    negative income.(+/-)

The emulator routes the positive part of nonprop to `alimony_income` and the
magnitude of the negative part to `alimony_expense` (SIGNED_INPUT_SPLITS in
core/utils.py), split 50/50 between spouses for MFJ. Before this, a nonzero
nonprop was ignored (taxsim #1424).

Every expected tax value below is taxsimtest output: the bundled
resources/taxsimtest/taxsimtest-osx.exe (build cd2026081819), idtl=2, run on
the record shown. Single filers are age 40 with $50,000 of pwages. MFJ
filers are both age 40 with pwages $30,000 and swages $20,000. No
dependents. TAXSIM behaviors these pin, observed on that binary for every
jurisdiction in 2021-2025:
  - Federal AGI (v10) moves dollar for dollar with nonprop, in both
    directions.
  - Positive nonprop raises every income-tax state's base, Pennsylvania and
    New Jersey included.
  - Negative nonprop lowers every state base except Pennsylvania's and New
    Jersey's, which it leaves unchanged.
  - For MFJ, states that tax spouses separately (DE, IA 2021-22) match
    TAXSIM only when nonprop is split evenly between the spouses.

Known divergence, by design: taxsimtest also counts nonprop as earned
income for the EITC and the refundable CTC (pensions, UI, interest and
otherprop leave those credits unchanged; nonprop moves them, in both
directions). 26 U.S.C. 32(c)(2)(A) defines earned income as wages, salaries,
tips and other employee compensation plus net earnings from self-employment,
which covers none of TAXSIM's documented nonprop examples, and 24(d)(1)(B)(i)
takes its earned income "within the meaning of section 32". PolicyEngine
therefore keeps nonprop out of earned income; the EITC tests below pin that.
"""

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.core.utils import (
    SIGNED_INPUT_SPLITS,
    load_variable_mappings,
    signed_part,
)
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

SINGLE = dict(mstat=1, page=40, sage=0, pwages=50_000, swages=0)
MFJ = dict(mstat=2, page=40, sage=40, pwages=30_000, swages=20_000)

# (taxsimid, SOI state, year, filer, nonprop, TAXSIM v10, fiitax, siitax)
TAXSIM_RECORDS = [
    # California: both signs flow into federal and state AGI.
    (25, 5, 2021, SINGLE, 0, 50_000, 2895.00, 1350.31),
    (26, 5, 2021, SINGLE, 10_000, 60_000, 4787.50, 2086.10),
    (27, 5, 2021, SINGLE, -5_000, 45_000, 2295.00, 1050.31),
    (1249, 5, 2025, SINGLE, 0, 50_000, 3871.50, 1039.53),
    (1250, 5, 2025, SINGLE, 10_000, 60_000, 5071.50, 1639.53),
    (1251, 5, 2025, SINGLE, -5_000, 45_000, 3271.50, 782.69),
    # Texas: federal only.
    (871, 44, 2023, SINGLE, 0, 50_000, 4118.00, 0.00),
    (872, 44, 2023, SINGLE, 10_000, 60_000, 5460.50, 0.00),
    (873, 44, 2023, SINGLE, -5_000, 45_000, 3518.00, 0.00),
    # Pennsylvania and New Jersey: positive taxed, negative ignored.
    (841, 39, 2023, SINGLE, 0, 50_000, 4118.00, 1535.00),
    (842, 39, 2023, SINGLE, 10_000, 60_000, 5460.50, 1842.00),
    (843, 39, 2023, SINGLE, -5_000, 45_000, 3518.00, 1535.00),
    (793, 31, 2023, SINGLE, 0, 50_000, 4118.00, 1214.75),
    (794, 31, 2023, SINGLE, 10_000, 60_000, 5460.50, 1767.25),
    (795, 31, 2023, SINGLE, -5_000, 45_000, 3518.00, 1214.75),
    (796, 31, 2023, MFJ, 0, 50_000, 2236.00, 770.00),
    (797, 31, 2023, MFJ, 10_000, 60_000, 3436.00, 1001.00),
    (798, 31, 2023, MFJ, -5_000, 45_000, 1730.00, 770.00),
    # Massachusetts subtracts negative nonprop.
    (1045, 22, 2024, SINGLE, 0, 50_000, 4016.00, 2180.00),
    (1046, 22, 2024, SINGLE, 10_000, 60_000, 5216.00, 2680.00),
    (1047, 22, 2024, SINGLE, -5_000, 45_000, 3416.00, 1930.00),
    (1048, 22, 2024, MFJ, 0, 50_000, 2080.00, 1883.50),
    (1049, 22, 2024, MFJ, 10_000, 60_000, 3232.00, 2383.50),
    (1050, 22, 2024, MFJ, -5_000, 45_000, 1580.00, 1633.50),
    # Alabama and Mississippi build state income from their own source lists.
    (613, 1, 2023, SINGLE, 0, 50_000, 4118.00, 1987.85),
    (614, 1, 2023, SINGLE, 10_000, 60_000, 5460.50, 2420.73),
    (615, 1, 2023, SINGLE, -5_000, 45_000, 3518.00, 1767.85),
    (1063, 25, 2024, SINGLE, 0, 50_000, 4016.00, 1489.90),
    (1064, 25, 2024, SINGLE, 10_000, 60_000, 5216.00, 1959.90),
    (1065, 25, 2024, SINGLE, -5_000, 45_000, 3416.00, 1254.90),
    # Spouses taxed separately: these match TAXSIM only with a 50/50 split.
    (94, 16, 2021, MFJ, 0, 50_000, -210.00, 1532.99),
    (95, 16, 2021, MFJ, 10_000, 60_000, 990.00, 2042.76),
    (96, 16, 2021, MFJ, -5_000, 45_000, -810.00, 1288.66),
    (964, 8, 2024, MFJ, 0, 50_000, 2080.00, 1463.13),
    (965, 8, 2024, MFJ, 10_000, 60_000, 3232.00, 1987.63),
    (966, 8, 2024, MFJ, -5_000, 45_000, 1580.00, 1207.00),
]


def _input_row(taxsimid, state, year, filer, nonprop):
    return dict(
        taxsimid=taxsimid,
        year=year,
        state=state,
        depx=0,
        nonprop=nonprop,
        idtl=2,
        **filer,
    )


@pytest.fixture(scope="module")
def runner_results():
    """One PolicyEngineRunner pass over every pinned record."""
    df = pd.DataFrame([_input_row(*rec[:5]) for rec in TAXSIM_RECORDS])
    result = PolicyEngineRunner(df, logs=False, disable_salt=True).run(
        show_progress=False
    )
    result["taxsimid"] = result["taxsimid"].astype(int)
    return result.set_index("taxsimid")


@pytest.mark.parametrize(
    "rec", TAXSIM_RECORDS, ids=lambda rec: f"id{rec[0]}-np{rec[4]}"
)
def test_runner_matches_taxsim(runner_results, rec):
    taxsimid, *_, agi, fiitax, siitax = rec
    row = runner_results.loc[taxsimid]
    assert row["v10"] == pytest.approx(agi, abs=0.01), "federal AGI"
    assert row["fiitax"] == pytest.approx(fiitax, abs=1), "federal income tax"
    assert row["siitax"] == pytest.approx(siitax, abs=1.5), "state income tax"


@pytest.mark.parametrize(
    "base_id,state,year,filer,taxsim_deltas",
    [
        # State tax at zero nonprop already differs from TAXSIM here: taxsimtest
        # nets a $500 one-time rebate (srebate) into siitax that PolicyEngine
        # does not report, so pin the change that nonprop causes instead. taxsimtest siitax at nonprop 0 / +10,000 /
        # -5,000: VA 2022 MFJ 847.00 / 1408.05 / 597.00;
        # GA 2024 MFJ 901.40 / 1440.40 / 631.90.
        (586, 47, 2022, MFJ, {10_000: 561.05, -5_000: -250.00}),
        (982, 11, 2024, MFJ, {10_000: 539.00, -5_000: -269.50}),
    ],
)
def test_runner_state_delta_matches_taxsim(base_id, state, year, filer, taxsim_deltas):
    rows = [_input_row(base_id, state, year, filer, 0)] + [
        _input_row(base_id + i + 1, state, year, filer, np_)
        for i, np_ in enumerate(taxsim_deltas)
    ]
    out = PolicyEngineRunner(pd.DataFrame(rows), logs=False, disable_salt=True).run(
        show_progress=False
    )
    siitax = out.set_index(out["taxsimid"].astype(int))["siitax"]
    for i, (np_, expected) in enumerate(taxsim_deltas.items()):
        delta = siitax[base_id + i + 1] - siitax[base_id]
        assert delta == pytest.approx(expected, abs=1), f"nonprop={np_}"


def test_single_household_path_matches_runner(runner_results):
    """Differential: generate_household + Simulation reproduces the runner
    for both signs, single and MFJ."""
    from policyengine_us import Simulation

    for taxsimid in (26, 27, 797, 798, 1050, 95, 96):
        rec = next(r for r in TAXSIM_RECORDS if r[0] == taxsimid)
        situation = generate_household(_input_row(*rec[:5]))
        sim = Simulation(situation=situation)
        year = rec[2]
        agi = sim.calculate("adjusted_gross_income", year)[0]
        fed = sim.calculate("income_tax", year)[0]
        assert agi == pytest.approx(runner_results.loc[taxsimid, "v10"], abs=0.01)
        assert fed == pytest.approx(runner_results.loc[taxsimid, "fiitax"], abs=0.01)


# ---------------------------------------------------------------------------
# nonprop is not EITC earned income (26 U.S.C. 32(c)(2)(A)); see docstring.
# taxsimtest, TX 2023, head of household, one child aged 5, pwages $8,000:
# nonprop 0 -> EITC (v25) $2,720 = 34% x $8,000 (phase-in). taxsimtest gives
# $3,995 at nonprop +$4,000 and $2,040 at -$2,000 because it counts nonprop
# as earned income; PolicyEngine holds the EITC at $2,720 in both cases
# because earned income is still $8,000.
# ---------------------------------------------------------------------------


def test_nonprop_is_not_eitc_earned_income():
    rows = [
        dict(
            taxsimid=i + 1,
            year=2023,
            state=44,
            mstat=1,
            page=40,
            sage=0,
            depx=1,
            age1=5,
            pwages=8_000,
            nonprop=np_,
            idtl=2,
        )
        for i, np_ in enumerate([0, 4_000, -2_000])
    ]
    out = PolicyEngineRunner(pd.DataFrame(rows), logs=False, disable_salt=True).run(
        show_progress=False
    )
    out = out.set_index(out["taxsimid"].astype(int))
    np.testing.assert_allclose(out["v10"].values, [8_000, 12_000, 6_000])
    # TAXSIM's EITC with no nonprop; earned income is unchanged by nonprop.
    np.testing.assert_allclose(out["v25"].values, [2_720, 2_720, 2_720], atol=1)


# ---------------------------------------------------------------------------
# Allocation invariants and cross-path agreement (no simulation).
# ---------------------------------------------------------------------------


def test_yaml_lists_each_signed_split_variable_under_its_source():
    units = load_variable_mappings()["taxsim_to_policyengine"]["household_situation"][
        "additional_income_units"
    ]
    sources = {var: vals for item in units for var, vals in item.items()}
    for pe_var, (source, _sign) in SIGNED_INPUT_SPLITS.items():
        assert sources.get(pe_var) == [source], pe_var
    assert {s for _, (s, _) in SIGNED_INPUT_SPLITS.items()} == {"nonprop"}
    assert sorted(sign for _, sign in SIGNED_INPUT_SPLITS.values()) == [-1, 1]


@pytest.fixture(scope="module")
def runner_mapping():
    ds = TaxsimMicrosimDataset(pd.DataFrame([_input_row(1, 5, 2024, SINGLE, 0)]))
    try:
        yield ds._get_taxsim_to_pe_variable_mapping()
    finally:
        ds.cleanup()


def _runner_allocation(mapping, row):
    """{pe_var: (primary, spouse)} from the Microsimulation runner accessors."""
    return {
        var: (mapping[var]["primary"](row), mapping[var]["spouse"](row))
        for var in SIGNED_INPUT_SPLITS
    }


def _mapper_allocation(row):
    """{pe_var: (primary, spouse)} from the single-household situation."""
    situation = generate_household(dict(row))
    people = situation["people"]
    year = str(int(row["year"]))

    def get(person, var):
        return people.get(person, {}).get(var, {}).get(year, 0.0)

    return {
        var: (get("you", var), get("your partner", var)) for var in SIGNED_INPUT_SPLITS
    }


def _check_allocation(runner_mapping, nonprop, mstat):
    filer = MFJ if mstat == 2 else SINGLE
    row = pd.Series(_input_row(1, 5, 2024, {**filer, "mstat": mstat}, nonprop))
    runner = _runner_allocation(runner_mapping, row)
    mapper = _mapper_allocation(row.to_dict())
    income = sum(runner["alimony_income"])
    expense = sum(runner["alimony_expense"])
    # Conservation: income minus adjustment reproduces nonprop exactly.
    assert income - expense == pytest.approx(nonprop, abs=1e-6)
    # Sign exclusivity and non-negativity.
    assert min(income, expense) == 0
    assert all(v >= 0 for pair in runner.values() for v in pair)
    # MFJ halves; anyone else keeps it all on the primary filer.
    for primary, spouse in runner.values():
        if mstat == 2:
            assert primary == pytest.approx(spouse)
        else:
            assert spouse == 0
    # Both execution paths allocate identically.
    for var in SIGNED_INPUT_SPLITS:
        assert mapper[var] == pytest.approx(runner[var]), var


@pytest.mark.parametrize("mstat", [1, 2])
@pytest.mark.parametrize("nonprop", [0, 10_000, -5_000, 0.5, -1e7])
def test_allocation_examples(runner_mapping, nonprop, mstat):
    _check_allocation(runner_mapping, nonprop, mstat)


def test_allocation_properties(runner_mapping):
    hypothesis = pytest.importorskip("hypothesis")
    st = hypothesis.strategies

    @hypothesis.settings(max_examples=200, deadline=None)
    @hypothesis.given(
        nonprop=st.floats(min_value=-1e8, max_value=1e8, allow_nan=False),
        mstat=st.sampled_from([1, 2]),
    )
    def check(nonprop, mstat):
        _check_allocation(runner_mapping, nonprop, mstat)

    check()


def test_signed_part_properties():
    hypothesis = pytest.importorskip("hypothesis")
    st = hypothesis.strategies

    @hypothesis.given(st.floats(allow_nan=False, allow_infinity=False))
    def check(x):
        pos, neg = signed_part(x, 1), signed_part(x, -1)
        assert pos >= 0 and neg >= 0
        assert min(pos, neg) == 0
        assert pos - neg == x

    check()
    assert signed_part(None, 1) == 0


# ---------------------------------------------------------------------------
# More taxsimtest-pinned records (taxsim #1424). Same bundled binary and
# idtl=2; run without disable_salt. These cover what the grid above does
# not: the NIIT exclusion, no FICA/SECA, AGI below zero, TY2018, the EITC
# AGI phase-out, and the KY, IL and NY state bases.
# ---------------------------------------------------------------------------

# (case id, record inputs, taxsimtest output). State 0 = federal only.
EXTRA_CASES = [
    (
        # Not in the NIIT base: the same record with otherprop gives niit
        # 3,800. fiitax is not compared because taxsimtest includes the
        # Additional Medicare Tax in it and the emulator does not (#1239).
        "not_in_niit_base_2023",
        dict(year=2023, state=0, mstat=1, page=40, pwages=300_000, nonprop=100_000),
        {"v10": 400_000.0, "v18": 386_150.0, "v28": 107_047.0, "niit": 0.0},
    ),
    (
        # Not earnings: no FICA or SECA.
        "nonprop_only_2023",
        dict(year=2023, state=0, mstat=1, page=40, nonprop=30_000),
        {"v10": 30_000.0, "v18": 16_150.0, "fiitax": 1718.0, "tfica": 0.0},
    ),
    (
        # A negative amount can take AGI below zero. (taxsimtest also zeroes
        # the EITC here because it counts nonprop as earned income; PE keeps
        # the 7.65% credit on the $5,000 of wages. See the module docstring.)
        "negative_agi_2023",
        dict(year=2023, state=0, mstat=1, page=40, pwages=5000, nonprop=-20_000),
        {"v10": -15_000.0, "v18": 0.0},
    ),
    (
        "single_positive_2018",
        dict(year=2018, state=0, mstat=1, page=40, pwages=60_000, nonprop=12_000),
        {"v10": 72_000.0, "v18": 60_000.0, "fiitax": 9139.5},
    ),
    (
        "single_negative_2018",
        dict(year=2018, state=0, mstat=1, page=40, pwages=60_000, nonprop=-12_000),
        {"v10": 48_000.0, "v18": 36_000.0, "fiitax": 4129.5},
    ),
    (
        # Above the EITC plateau nonprop moves the credit only through the
        # AGI phase-out, where both engines agree.
        "eitc_phaseout_on_agi_2024",
        dict(
            year=2024,
            state=0,
            mstat=1,
            page=35,
            depx=1,
            age1=5,
            pwages=20_000,
            nonprop=12_000,
        ),
        {"v10": 32_000.0, "v25": 2730.06, "fiitax": -3720.06},
    ),
    (
        "ny_joint_negative_2024",
        dict(
            year=2024,
            state=33,
            mstat=2,
            page=40,
            sage=40,
            pwages=50_000,
            swages=30_000,
            nonprop=-12_000,
        ),
        {"v10": 68_000.0, "fiitax": 4192.0, "siitax": 2524.75},
    ),
    (
        # One earner: with nonprop all on the primary filer, siitax is 3,473.60.
        "ky_joint_split_2024",
        dict(
            year=2024,
            state=18,
            mstat=2,
            page=40,
            sage=40,
            pwages=60_000,
            nonprop=30_000,
        ),
        {"v10": 90_000.0, "fiitax": 6832.0, "siitax": 3347.2},
    ),
    (
        # Illinois exempts the pension and Social Security, not nonprop.
        "il_joint_retired_2024",
        dict(
            year=2024,
            state=14,
            mstat=2,
            page=70,
            sage=68,
            pensions=30_000,
            gssi=20_000,
            nonprop=10_000,
        ),
        {"v10": 51_100.0, "fiitax": 1880.0, "siitax": 121.28},
    ),
]
EXTRA_IDS = [case[0] for case in EXTRA_CASES]


def _extra_record(taxsimid, inputs):
    return {"taxsimid": taxsimid, "sage": 0, "depx": 0, "idtl": 2, **inputs}


@pytest.fixture(scope="module")
def extra_results():
    df = pd.DataFrame(
        [_extra_record(i + 1, inputs) for i, (_, inputs, _) in enumerate(EXTRA_CASES)]
    ).fillna(0)
    out = PolicyEngineRunner(df, logs=False).run(show_progress=False)
    out["taxsimid"] = out["taxsimid"].astype(float).astype(int)
    return out.set_index("taxsimid")


@pytest.mark.parametrize("case", EXTRA_CASES, ids=EXTRA_IDS)
def test_extra_cases_runner_matches_taxsim(case, extra_results):
    case_id, _, expected = case
    row = extra_results.loc[EXTRA_IDS.index(case_id) + 1]
    for column, value in expected.items():
        assert float(row[column]) == pytest.approx(value, abs=1.0), (
            f"{case_id} {column}: emulator {row[column]} vs taxsimtest {value}"
        )


@pytest.mark.parametrize("case", EXTRA_CASES, ids=EXTRA_IDS)
def test_extra_cases_single_household_path_matches_taxsim(case):
    case_id, inputs, expected = case
    record = _extra_record(1, inputs)
    output = export_household(
        dict(record), generate_household(dict(record)), False, False
    )
    for column, value in expected.items():
        assert float(output[column]) == pytest.approx(value, abs=1.0), (
            f"{case_id} {column}: single-household path {output[column]} "
            f"vs taxsimtest {value}"
        )


# ---------------------------------------------------------------------------
# Guard every hard-coded taxsimtest number in this module: the bundled binary
# must still produce them, including the EITC values PolicyEngine diverges
# from by design. If NBER changes behavior, this fails here first instead of
# leaving stale expectations and a stale divergence note.
# ---------------------------------------------------------------------------

# taxsimtest siitax at nonprop 0 / +10,000 / -5,000 (see the delta test).
DELTA_LEVELS = {
    (47, 2022): (847.00, 1408.05, 597.00),
    (11, 2024): (901.40, 1440.40, 631.90),
}
# taxsimtest EITC (v25), TX 2023, head of household, one child aged 5,
# pwages 8,000, at nonprop 0 / +4,000 / -2,000.
EITC_TAXSIM = (2720.0, 3995.0, 2040.0)


def test_bundled_taxsimtest_still_produces_expected_values():
    rows, checks = [], []
    for rec in TAXSIM_RECORDS:
        taxsimid, state, year, filer, nonprop, agi, fiitax, siitax = rec
        rows.append(_input_row(taxsimid, state, year, filer, nonprop))
        checks.append((taxsimid, {"v10": agi, "fiitax": fiitax, "siitax": siitax}))
    for k, ((state, year), levels) in enumerate(DELTA_LEVELS.items()):
        for j, (nonprop, siitax) in enumerate(zip((0, 10_000, -5_000), levels)):
            taxsimid = 5000 + 10 * k + j
            rows.append(_input_row(taxsimid, state, year, MFJ, nonprop))
            checks.append((taxsimid, {"siitax": siitax}))
    for j, (nonprop, eitc) in enumerate(zip((0, 4000, -2000), EITC_TAXSIM)):
        taxsimid = 6000 + j
        rows.append(
            dict(
                _input_row(taxsimid, 44, 2023, SINGLE, nonprop),
                pwages=8000,
                depx=1,
                age1=5,
            )
        )
        checks.append((taxsimid, {"v25": eitc}))
    for i, (_, inputs, expected) in enumerate(EXTRA_CASES):
        rows.append(_extra_record(7000 + i, inputs))
        checks.append((7000 + i, expected))
    output = TaxsimRunner(pd.DataFrame(rows).fillna(0)).run(show_progress=False)
    output["taxsimid"] = output["taxsimid"].astype(float).astype(int)
    output = output.set_index("taxsimid")
    for taxsimid, expected in checks:
        for column, value in expected.items():
            assert float(output.loc[taxsimid, column]) == pytest.approx(
                value, abs=0.01
            ), f"taxsimid {taxsimid} {column}"


# ---------------------------------------------------------------------------
# Invariants of the computed return, on random federal records without
# Social Security (whose taxable share would make AGI nonlinear in nonprop):
#   - AGI moves one-for-one with nonprop;
#   - federal income tax is nondecreasing in nonprop;
#   - NIIT never exceeds 3.8% of interest plus dividends (nonprop is outside
#     the net-investment-income base);
#   - the runner and the single-household path agree.
# ---------------------------------------------------------------------------

_NONPROP_STEPS = (-40_000.0, -7500.0, 0.0, 9000.0, 60_000.0)


@st.composite
def _federal_record(draw):
    mstat = draw(st.sampled_from([1, 2]))
    depx = draw(st.integers(min_value=0, max_value=2))
    record = {
        "year": draw(st.sampled_from([2019, 2021, 2023, 2024, 2025])),
        "state": 0,
        "mstat": mstat,
        "page": draw(st.integers(min_value=20, max_value=80)),
        "sage": draw(st.integers(min_value=20, max_value=80)) if mstat == 2 else 0,
        "depx": depx,
        "pwages": float(draw(st.integers(min_value=0, max_value=400_000))),
        "swages": (
            float(draw(st.integers(min_value=0, max_value=150_000)))
            if mstat == 2
            else 0.0
        ),
        "intrec": float(draw(st.sampled_from([0, 0, 3000, 250_000]))),
        "dividends": float(draw(st.sampled_from([0, 0, 5000]))),
    }
    for d in range(1, depx + 1):
        record[f"age{d}"] = draw(st.integers(min_value=1, max_value=16))
    return record


FIXED_RECORDS = [
    {
        "year": 2023,
        "state": 0,
        "mstat": 2,
        "page": 45,
        "sage": 43,
        "depx": 2,
        "age1": 4,
        "age2": 9,
        "pwages": 31_000.0,
        "swages": 0.0,
        "intrec": 3000.0,
        "dividends": 0.0,
    },
    {
        "year": 2025,
        "state": 0,
        "mstat": 1,
        "page": 67,
        "sage": 0,
        "depx": 0,
        "pwages": 180_000.0,
        "swages": 0.0,
        "intrec": 250_000.0,
        "dividends": 5000.0,
    },
]


@settings(
    max_examples=3,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(records=st.lists(_federal_record(), min_size=2, max_size=4))
@example(records=FIXED_RECORDS)
def test_property_return_invariants(records):
    rows = []
    for r, record in enumerate(records):
        for s, step in enumerate(_NONPROP_STEPS):
            rows.append(
                {**record, "taxsimid": 100 * (r + 1) + s, "nonprop": step, "idtl": 2}
            )
    df = pd.DataFrame(rows).fillna(0)
    out = PolicyEngineRunner(df, logs=False).run(show_progress=False)
    out["taxsimid"] = out["taxsimid"].astype(float).astype(int)
    out = out.set_index("taxsimid")
    inputs = df.set_index("taxsimid")
    for r, record in enumerate(records):
        ids = [100 * (r + 1) + s for s in range(len(_NONPROP_STEPS))]
        base = ids[_NONPROP_STEPS.index(0.0)]
        agi = out.loc[ids, "v10"].astype(float).to_numpy()
        np.testing.assert_allclose(
            agi - float(out.loc[base, "v10"]),
            np.array(_NONPROP_STEPS),
            atol=0.01,
            err_msg=f"AGI not one-for-one in nonprop: {record}",
        )
        tax = out.loc[ids, "fiitax"].astype(float).to_numpy()
        assert (np.diff(tax) >= -0.01).all(), (
            f"fiitax fell as nonprop rose: {tax.tolist()} for {record}"
        )
        cap = 0.038 * (record["intrec"] + record["dividends"]) + 0.01
        assert (out.loc[ids, "niit"].astype(float) <= cap).all(), record
        tid = ids[-1]
        record_in = dict(inputs.loc[tid], taxsimid=tid)
        single = export_household(
            dict(record_in), generate_household(dict(record_in)), False, False
        )
        for column in ("v10", "fiitax"):
            assert float(single[column]) == pytest.approx(
                float(out.loc[tid, column]), abs=1.0
            ), (column, record)
