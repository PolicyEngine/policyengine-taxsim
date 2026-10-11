"""
TAXSIM `nonprop` (other non-property income, +/-) -> PolicyEngine routing.

TAXSIM documentation (https://taxsim.nber.org/taxsimtest/, input 15):

    nonprop Other non-property income in AGI not subject to Medicare NIIT
    such as: alimony, nonwage fellowships, state income tax refunds
    (itemizers only). Adjustments and items such as alimony paid, Keogh and
    IRA contributions, foreign income exclusion, NOLs can be entered here as
    negative income.(+/-)

The emulator routes the positive part of nonprop to `miscellaneous_income`
(`alimony_income` in AL, AR and MS, whose PE-US gross-income lists name
alimony but not miscellaneous income) and the magnitude of the negative part
to `alimony_expense` (nonprop_parts in core/utils.py), split 50/50 between
spouses for MFJ. Before this, a nonzero nonprop was ignored (taxsim #1424).

`alimony_income` is not used in the other states because PE-US gives alimony
treatment taxsimtest does not give nonprop. Two such cases are pinned below:
Georgia's retirement-income exclusion for filers aged 62 and over
(test_georgia_senior_nonprop_is_not_retirement_income), and Pennsylvania tax
forgiveness, whose eligibility income adds alimony on top of taxable income
that already holds it (pa_forgiveness_counts_nonprop_once_2023). Rhode
Island's property-tax relief for elderly renters has the same double count;
it is not pinned because PE's credit already differs from taxsimtest's there.

Every expected tax value below is taxsimtest output: the bundled
resources/taxsimtest/taxsimtest-osx.exe (build cd2026081819; the bundled
Linux binary is the same build and the Windows one is cd2026081318), idtl=2,
run on the record shown. test_bundled_taxsimtest_still_produces_expected_values
re-runs each platform's binary on every one of them. Single filers are age 40 with $50,000 of pwages. MFJ
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
    NONPROP_ALIMONY_STATES,
    NONPROP_SOURCE,
    NONPROP_VARIABLES,
    get_calculation_state_code,
    load_variable_mappings,
    nonprop_parts,
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
    # PE rounds a few state computations to the dollar where taxsimtest
    # keeps cents (largest gap in this grid: $1.03, Iowa 2021).
    assert row["siitax"] == pytest.approx(siitax, abs=1.5), "state income tax"


# taxsimtest siitax for MFJ filers at nonprop 0 / +10,000 / -5,000, keyed by
# (SOI state, year): VA 2022 and GA 2024. State tax at zero nonprop already
# differs from TAXSIM here: taxsimtest nets a $500 one-time rebate (srebate)
# into siitax that PolicyEngine does not report, so the test pins the change
# that nonprop causes instead of the level.
DELTA_NONPROP = (0, 10_000, -5_000)
DELTA_LEVELS = {
    (47, 2022): (847.00, 1408.05, 597.00),
    (11, 2024): (901.40, 1440.40, 631.90),
}


@pytest.mark.parametrize("state,year", list(DELTA_LEVELS))
def test_runner_state_delta_matches_taxsim(state, year):
    levels = DELTA_LEVELS[(state, year)]
    rows = [
        _input_row(i + 1, state, year, MFJ, np_) for i, np_ in enumerate(DELTA_NONPROP)
    ]
    out = PolicyEngineRunner(pd.DataFrame(rows), logs=False, disable_salt=True).run(
        show_progress=False
    )
    siitax = out.set_index(out["taxsimid"].astype(int))["siitax"]
    for i, np_ in enumerate(DELTA_NONPROP[1:], start=1):
        delta = siitax[i + 1] - siitax[1]
        assert delta == pytest.approx(levels[i] - levels[0], abs=1), f"nonprop={np_}"


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


def test_yaml_lists_each_nonprop_variable_under_nonprop():
    units = load_variable_mappings()["taxsim_to_policyengine"]["household_situation"][
        "additional_income_units"
    ]
    sources = {var: vals for item in units for var, vals in item.items()}
    reading_nonprop = {
        var for var, vals in sources.items() if NONPROP_SOURCE in (vals or [])
    }
    assert reading_nonprop == set(NONPROP_VARIABLES)
    for pe_var in NONPROP_VARIABLES:
        assert sources[pe_var] == [NONPROP_SOURCE], pe_var


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
        for var in NONPROP_VARIABLES
    }


def _mapper_allocation(row):
    """{pe_var: (primary, spouse)} from the single-household situation."""
    situation = generate_household(dict(row))
    people = situation["people"]
    year = str(int(row["year"]))

    def get(person, var):
        return people.get(person, {}).get(var, {}).get(year, 0.0)

    return {
        var: (get("you", var), get("your partner", var)) for var in NONPROP_VARIABLES
    }


def _check_allocation(runner_mapping, nonprop, mstat, state=5):
    filer = MFJ if mstat == 2 else SINGLE
    row = pd.Series(_input_row(1, state, 2024, {**filer, "mstat": mstat}, nonprop))
    runner = _runner_allocation(runner_mapping, row)
    mapper = _mapper_allocation(row.to_dict())
    totals = {var: sum(pair) for var, pair in runner.items()}
    income = totals["miscellaneous_income"] + totals["alimony_income"]
    expense = totals["alimony_expense"]
    # Conservation: income minus adjustment reproduces nonprop exactly.
    assert income - expense == pytest.approx(nonprop, abs=1e-6)
    # Sign exclusivity and non-negativity.
    assert min(income, expense) == 0
    assert all(v >= 0 for pair in runner.values() for v in pair)
    # One income variable per state: alimony_income only where listed.
    as_alimony = get_calculation_state_code(state) in NONPROP_ALIMONY_STATES
    unused = "miscellaneous_income" if as_alimony else "alimony_income"
    assert totals[unused] == 0
    # MFJ halves; anyone else keeps it all on the primary filer.
    for primary, spouse in runner.values():
        if mstat == 2:
            assert primary == pytest.approx(spouse)
        else:
            assert spouse == 0
    # Both execution paths allocate identically.
    for var in NONPROP_VARIABLES:
        assert mapper[var] == pytest.approx(runner[var]), var


# SOI codes: 0 no state, 1 AL, 4 AR, 5 CA, 11 GA, 25 MS, 39 PA.
@pytest.mark.parametrize("state", [0, 1, 4, 5, 11, 25, 39])
@pytest.mark.parametrize("mstat", [1, 2, 6])
@pytest.mark.parametrize("nonprop", [0, 10_000, -5_000, 0.5, -1e7])
def test_allocation_examples(runner_mapping, nonprop, mstat, state):
    _check_allocation(runner_mapping, nonprop, mstat, state)


@settings(max_examples=200, deadline=None)
@given(
    nonprop=st.floats(min_value=-1e8, max_value=1e8, allow_nan=False),
    mstat=st.sampled_from([1, 2, 6]),
    state=st.integers(min_value=0, max_value=51),
)
def test_allocation_properties(runner_mapping, nonprop, mstat, state):
    _check_allocation(runner_mapping, nonprop, mstat, state)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_signed_part_properties(x):
    pos, neg = signed_part(x, 1), signed_part(x, -1)
    assert pos >= 0 and neg >= 0
    assert min(pos, neg) == 0
    assert pos - neg == x


def test_missing_nonprop_is_zero():
    """A blank cell (None, "", whitespace, NaN or pd.NA) is no nonprop, not
    NaN income."""
    for missing in (None, "", "   ", float("nan"), np.nan, pd.NA):
        assert signed_part(missing, 1) == 0
        assert signed_part(missing, -1) == 0
        assert set(nonprop_parts(missing, "CA").values()) == {0.0}


def test_alimony_states_are_the_ones_pe_us_needs():
    """Each state in NONPROP_ALIMONY_STATES has a PE-US gross-income list
    that names alimony_income but not miscellaneous_income. When PE-US adds
    miscellaneous_income to one of these lists this test fails: drop that
    state from NONPROP_ALIMONY_STATES. (It does not search the other states
    for a list that would need the same exception.)"""
    from policyengine_us import CountryTaxBenefitSystem

    states = CountryTaxBenefitSystem().parameters.gov.states
    lists = {
        "AL": [states.al.tax.income.agi.gross_income_sources],
        "AR": [
            states.ar.tax.income.gross_income.sources.individual,
            states.ar.tax.income.gross_income.sources.joint,
        ],
        "MS": [states.ms.tax.income.income_sources],
    }
    assert NONPROP_ALIMONY_STATES == set(lists)
    for state, parameters in lists.items():
        for parameter in parameters:
            for year in range(2021, 2026):
                sources = parameter(f"{year}-01-01")
                assert "alimony_income" in sources, (state, parameter.name, year)
                assert "miscellaneous_income" not in sources, (
                    f"PE-US now lists miscellaneous_income in {parameter.name} "
                    f"({year}): drop {state} from NONPROP_ALIMONY_STATES"
                )
    assert nonprop_parts(100, "al")["alimony_income"] == 100
    assert nonprop_parts(100, "GA")["miscellaneous_income"] == 100


def _batch_people(records):
    frame = pd.DataFrame(records)
    dataset = TaxsimMicrosimDataset(frame)
    try:
        return dataset._process_person_data_for_year(frame, 2024)
    finally:
        dataset.cleanup()


def test_batch_builder_skips_nonprop_accessors_when_unused(monkeypatch):
    """With no nonprop in the batch the dataset builder writes the three
    variables as zeros without calling nonprop_parts; with any nonprop it
    allocates every record, including the zero ones."""
    from policyengine_taxsim.runners import policyengine_runner

    # Five people: California MFJ, Alabama single, Mississippi MFJ.
    rows = [
        _input_row(1, 5, 2024, MFJ, 0),
        _input_row(2, 1, 2024, SINGLE, 0),
        _input_row(3, 25, 2024, MFJ, 0),
    ]

    def accessor_ran(*args, **kwargs):
        raise AssertionError("nonprop accessor ran for a batch without nonprop")

    with monkeypatch.context() as patch:
        patch.setattr(policyengine_runner, "nonprop_parts", accessor_ran)
        people = _batch_people(rows)
    for var in NONPROP_VARIABLES:
        np.testing.assert_array_equal(people[var], np.zeros(5), err_msg=var)

    used = [
        dict(rows[0], nonprop=600),
        dict(rows[1], nonprop=-40),
        dict(rows[2], nonprop=200),
    ]
    people = _batch_people(used)
    np.testing.assert_allclose(people["miscellaneous_income"], [300, 300, 0, 0, 0])
    np.testing.assert_allclose(people["alimony_income"], [0, 0, 0, 100, 100])
    np.testing.assert_allclose(people["alimony_expense"], [0, 0, 40, 0, 0])


# ---------------------------------------------------------------------------
# More taxsimtest-pinned records (taxsim #1424). Same bundled binary and
# idtl=2; run without disable_salt. These cover what the grid above does
# not: the NIIT exclusion, no FICA/SECA, AGI below zero, TY2018, the EITC
# AGI phase-out, the KY, IL and NY state bases, and Pennsylvania tax
# forgiveness.
# ---------------------------------------------------------------------------

# (case id, record inputs, taxsimtest output). State 0 = federal only.
EXTRA_CASES = [
    (
        # Not in the NIIT base: the same record with otherprop in place of
        # nonprop owes NIIT (OTHERPROP_NIIT_TAXSIM). fiitax is not compared
        # because taxsimtest includes the Additional Medicare Tax in it and
        # the emulator does not (#1239).
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
        # One earner. PolicyEngine with nonprop all on the primary filer
        # gives siitax 3,473.60; the 50/50 split gives taxsimtest's value.
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
        # Pennsylvania tax forgiveness: eligibility income is 6,000, under the
        # 6,500 limit for a single claimant, so the tax is fully forgiven.
        # With alimony_income PolicyEngine counts the 2,000 twice and gives
        # siitax 110.52. (fiitax is not compared: taxsimtest's EITC counts
        # nonprop as earned income.)
        "pa_forgiveness_counts_nonprop_once_2023",
        dict(year=2023, state=39, mstat=1, page=40, pwages=4000, nonprop=2000),
        {"v10": 6000.0, "siitax": 0.0},
    ),
    (
        # Arkansas, the third NONPROP_ALIMONY_STATES member (AL and MS are in
        # the grid above): with miscellaneous_income PolicyEngine adds no
        # Arkansas tax and siitax is 0.
        "ar_joint_retired_2024",
        dict(
            year=2024,
            state=4,
            mstat=2,
            page=70,
            sage=68,
            pensions=30_000,
            gssi=20_000,
            nonprop=10_000,
        ),
        {"v10": 51_100.0, "fiitax": 1880.0, "siitax": 21.46},
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

# taxsimtest EITC (v25), TX 2023, head of household, one child aged 5,
# pwages 8,000, at nonprop 0 / +4,000 / -2,000.
EITC_TAXSIM = (2720.0, 3995.0, 2040.0)
# taxsimtest siitax, Georgia 2024, single, age 65, no other income, at
# nonprop 30,000 / 60,000. Both levels net a $250 one-time rebate (srebate)
# that PolicyEngine does not report, so the test pins their difference.
GA_SENIOR_NONPROP = (30_000, 60_000)
GA_SENIOR_TAXSIM = (720.20, 2337.20)
# taxsimtest niit for the not_in_niit_base_2023 record with the 100,000 as
# otherprop instead of nonprop: 3.8% of it.
OTHERPROP_NIIT_TAXSIM = 3800.0


def _ga_senior_row(taxsimid, nonprop):
    return dict(_input_row(taxsimid, 11, 2024, SINGLE, nonprop), page=65, pwages=0)


def test_georgia_senior_nonprop_is_not_retirement_income():
    """taxsimtest taxes a 65-year-old Georgian's nonprop in full: the second
    30,000 adds 1,617.00 (5.39%). Georgia's retirement-income exclusion (up
    to $65,000 at 65) names alimony, so routing nonprop to alimony_income
    would exclude both amounts and add nothing."""
    rows = [_ga_senior_row(i + 1, np_) for i, np_ in enumerate(GA_SENIOR_NONPROP)]
    out = PolicyEngineRunner(pd.DataFrame(rows), logs=False).run(show_progress=False)
    siitax = out.set_index(out["taxsimid"].astype(float).astype(int))["siitax"]
    assert float(siitax[2]) - float(siitax[1]) == pytest.approx(
        GA_SENIOR_TAXSIM[1] - GA_SENIOR_TAXSIM[0], abs=1
    )


def test_bundled_taxsimtest_still_produces_expected_values():
    rows, checks = [], []
    for rec in TAXSIM_RECORDS:
        taxsimid, state, year, filer, nonprop, agi, fiitax, siitax = rec
        rows.append(_input_row(taxsimid, state, year, filer, nonprop))
        checks.append((taxsimid, {"v10": agi, "fiitax": fiitax, "siitax": siitax}))
    for k, ((state, year), levels) in enumerate(DELTA_LEVELS.items()):
        for j, (nonprop, siitax) in enumerate(zip(DELTA_NONPROP, levels)):
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
    for j, (nonprop, siitax) in enumerate(zip(GA_SENIOR_NONPROP, GA_SENIOR_TAXSIM)):
        rows.append(_ga_senior_row(8000 + j, nonprop))
        checks.append((8000 + j, {"siitax": siitax}))
    niit_inputs = dict(EXTRA_CASES[EXTRA_IDS.index("not_in_niit_base_2023")][1])
    niit_inputs["otherprop"] = niit_inputs.pop("nonprop")
    rows.append(_extra_record(9000, niit_inputs))
    checks.append((9000, {"niit": OTHERPROP_NIIT_TAXSIM}))
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
