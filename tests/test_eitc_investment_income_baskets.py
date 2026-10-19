"""EITC investment income keeps separate loss baskets on every supported PE-US.

Expected values come from IRS Publication 596 (2025). Worksheet 1 counts
interest, tax-exempt interest and dividends (lines 1-3) in full, capital gain
net income only when positive (line 7), and passive income plus passive losses
only when the net is positive (line 13: "If the result is less than zero,
enter -0-"); line 14 adds them. Rule 6: no EIC when line 14 exceeds $11,950.
A passive S-corp loss therefore cannot offset interest. PolicyEngine treats
all rental income as passive (as in its NIIT mapping); that is a modelling
convention, not something Worksheet 1 says.

PE-US fixed this in pe-us#9572 (first released in 2.10.1). scorp_reform
backports the formula to older releases: 1.x on Python 3.10, and 2.x releases
such as 2.6.17 that already define the passive input.
"""

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from policyengine_us import CountryTaxBenefitSystem, Simulation
from policyengine_us.model_api import Reform

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.core import scorp_reform
from policyengine_taxsim.core.scorp_reform import scorp_tax_benefit_system
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

YEAR = 2025
# Pub. 596 (2025), Rule 6 and Worksheet 1 line 15.
INVESTMENT_INCOME_LIMIT = 11_950
# Pub. 596 (2025) EIC Table, row "18,000 / 18,050", single with two children.
# AGI is below the $23,350 phase-out start whether or not the S-corp loss
# reaches AGI (23,000 or 13,000), so the table amount applies either way.
FULL_EITC_TWO_CHILDREN = 7_152


def record(interest, scorp):
    return dict(
        taxsimid=1,
        year=YEAR,
        state=0,
        mstat=1,
        page=35,
        sage=0,
        depx=2,
        age1=5,
        age2=8,
        pwages=18_000,
        intrec=interest,
        scorp=scorp,
        idtl=2,
    )


# (interest, scorp, Worksheet 1 line 14, EITC). Line 13 is max(0, -10,000) = 0,
# so line 14 is the interest alone.
WORKSHEET_CASES = [
    (12_500, -10_000, 12_500, 0),
    (5_000, -10_000, 5_000, FULL_EITC_TWO_CHILDREN),
]


@pytest.fixture(scope="module")
def runner_results():
    df = pd.DataFrame([record(i, s) for i, s, _, _ in WORKSHEET_CASES])
    df["taxsimid"] = np.arange(1, len(df) + 1)
    return {
        mode: PolicyEngineRunner(df.copy(), scorp_treatment=mode).run(
            show_progress=False
        )
        for mode in ("passive", "active")
    }


@pytest.mark.parametrize("mode", ["passive", "active"])
def test_passive_loss_cannot_restore_eitc_in_batch(mode, runner_results):
    eitc = runner_results[mode].sort_values("taxsimid").v25.to_numpy()
    assert eitc == pytest.approx([case[3] for case in WORKSHEET_CASES], abs=0.01)


@pytest.mark.parametrize("interest,scorp,line_14,eitc", WORKSHEET_CASES)
def test_passive_loss_cannot_restore_eitc_single_household(
    interest, scorp, line_14, eitc
):
    row = record(interest, scorp)
    situation = generate_household(row.copy(), scorp_treatment="passive")
    assert situation["people"]["you"]["passive_partnership_s_corp_income"][
        str(YEAR)
    ] == pytest.approx(scorp)
    sim = Simulation(situation=situation, tax_benefit_system=scorp_tax_benefit_system())
    assert sim.calculate("eitc_relevant_investment_income", YEAR)[0] == pytest.approx(
        line_14
    )
    output = export_household(row, situation, False, False)
    assert float(output["v25"]) == pytest.approx(eitc, abs=0.01)


@pytest.mark.parametrize(
    "pe_version,has_passive_input,needs_reform",
    [
        ((1, 783, 0), False, True),  # Python 3.10: no passive input, old EITC
        ((2, 6, 17), True, True),  # dashboard pin: passive input, old EITC
        ((2, 10, 0), True, True),
        ((2, 10, 1), True, False),  # pe-us#9572
        ((2, 23, 4), True, False),
    ],
)
def test_compatibility_reform_selection(
    pe_version, has_passive_input, needs_reform, monkeypatch
):
    monkeypatch.setattr(scorp_reform, "_pe_version", lambda: pe_version)
    variables = {"passive_partnership_s_corp_income"} if has_passive_input else set()
    assert scorp_reform.needs_compatibility_reform(variables) is needs_reform


def test_installed_system_matches_selection():
    native = Simulation.default_tax_benefit_system_instance
    uses_native = not scorp_reform.needs_compatibility_reform(native.variables)
    assert (scorp_tax_benefit_system() is native) is uses_native


amounts = st.integers(min_value=-30_000, max_value=30_000)
positive = st.integers(min_value=0, max_value=15_000)
person_income = st.fixed_dictionaries({"rental": amounts, "passive": amounts})
tax_unit_income = st.fixed_dictionaries(
    {
        "interest": positive,
        "tax_exempt": st.integers(min_value=0, max_value=5_000),
        "dividends": positive,
        "stcg": amounts,
        "ltcg": amounts,
        "head": person_income,
        "spouse": st.none() | person_income,
    }
)


def worksheet_1_line_14(unit):
    """Pub. 596 Worksheet 1, with lines 4, 6 and 10 at zero."""
    people = [unit["head"]] + ([unit["spouse"]] if unit["spouse"] else [])
    line_7 = max(0, unit["stcg"] + unit["ltcg"])
    line_13 = max(0, sum(p["rental"] + p["passive"] for p in people))
    return unit["interest"] + unit["tax_exempt"] + unit["dividends"] + line_7 + line_13


def situation_for(units):
    people, members = {}, {}
    for i, unit in enumerate(units):
        members[i] = []
        for role in ("head", "spouse"):
            if unit[role] is None:
                continue
            name = f"{role}{i}"
            members[i].append(name)
            people[name] = {
                "age": {YEAR: 40},
                "rental_income": {YEAR: unit[role]["rental"]},
                "passive_partnership_s_corp_income": {YEAR: unit[role]["passive"]},
            }
        head = people[f"head{i}"]
        head["taxable_interest_income"] = {YEAR: unit["interest"]}
        head["tax_exempt_interest_income"] = {YEAR: unit["tax_exempt"]}
        head["dividend_income"] = {YEAR: unit["dividends"]}
        head["short_term_capital_gains"] = {YEAR: unit["stcg"]}
        head["long_term_capital_gains"] = {YEAR: unit["ltcg"]}
    situation = {"people": people}
    for entity in ("tax_units", "families", "spm_units", "marital_units", "households"):
        situation[entity] = {
            f"{entity}{i}": {"members": names} for i, names in members.items()
        }
    return situation


PROPERTY_SETTINGS = settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


@PROPERTY_SETTINGS
@given(units=st.lists(tax_unit_income, min_size=1, max_size=8))
def test_investment_income_matches_worksheet_1(units):
    sim = Simulation(
        situation=situation_for(units), tax_benefit_system=scorp_tax_benefit_system()
    )
    expected = np.array([worksheet_1_line_14(u) for u in units], dtype=float)
    actual = sim.calculate("eitc_relevant_investment_income", YEAR)
    np.testing.assert_allclose(actual, expected, atol=0.01)
    # A loss in one basket never pulls investment income below portfolio income.
    portfolio = np.array(
        [u["interest"] + u["tax_exempt"] + u["dividends"] for u in units], float
    )
    assert (actual >= portfolio - 0.01).all()
    eligible = sim.calculate("eitc_investment_income_eligible", YEAR)
    np.testing.assert_array_equal(eligible, expected <= INVESTMENT_INCOME_LIMIT)


class BackportedEITCInvestmentIncome(Reform):
    def apply(self):
        self.update_variable(scorp_reform.eitc_relevant_investment_income)


@pytest.fixture(scope="module")
def backport_system():
    native = Simulation.default_tax_benefit_system_instance
    if scorp_reform.needs_compatibility_reform(native.variables):
        pytest.skip("native formula predates pe-us#9572; nothing to compare")
    return CountryTaxBenefitSystem(reform=BackportedEITCInvestmentIncome)


@PROPERTY_SETTINGS
@given(units=st.lists(tax_unit_income, min_size=1, max_size=8))
def test_backport_matches_native_formula(backport_system, units):
    # Differential: on PE-US 2.10.1+ the backported formula must agree with
    # the native one it copies.
    situation = situation_for(units)
    native = Simulation(situation=situation)
    backport = Simulation(situation=situation, tax_benefit_system=backport_system)
    np.testing.assert_allclose(
        backport.calculate("eitc_relevant_investment_income", YEAR),
        native.calculate("eitc_relevant_investment_income", YEAR),
        atol=0.01,
        err_msg="policyengine-us changed eitc_relevant_investment_income; "
        "update or retire the backport in core/scorp_reform.py",
    )
