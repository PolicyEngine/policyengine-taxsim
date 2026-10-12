"""Backport S-corp NIIT and EITC investment-income rules to older PE-US releases.

Python 3.10 resolves PE-US 1.x, which lacks the passive NIIT input; this reform
adds it and includes it in NII. Every release before 2.10.1 also nets passive
losses against interest and dividends in the EITC investment-income test, so
the reform backports pe-us#9572's floored baskets there, including releases
such as 2.6.17 that already define the passive input. On 2.10.1 and later the
native system is used unchanged. It does not implement section 469 loss limits
or change QBI/AGI/SECA.
"""

from functools import lru_cache

from policyengine_us.model_api import (
    Variable,
    Person,
    TaxUnit,
    YEAR,
    USD,
    Reform,
    add,
    max_,
)

from .scorp import EITC_BASKETS_MIN_PE_VERSION, _pe_version


class passive_partnership_s_corp_income(Variable):
    value_type = float
    entity = Person
    definition_period = YEAR
    unit = USD
    default_value = 0
    label = "Passive subset of partnership and S-corporation income"


class net_investment_income(Variable):
    value_type = float
    entity = TaxUnit
    label = "Net investment income including passive pass-through income"
    definition_period = YEAR
    unit = USD

    def formula(tax_unit, period, parameters):
        sources = list(parameters(period).gov.irs.investment.income.sources)
        if "passive_partnership_s_corp_income" not in sources:
            sources.append("passive_partnership_s_corp_income")
        return add(tax_unit, period, sources)


class eitc_relevant_investment_income(Variable):
    value_type = float
    entity = TaxUnit
    label = "EITC-relevant investment income"
    unit = USD
    definition_period = YEAR
    reference = (
        "https://www.law.cornell.edu/uscode/text/26/32#i_2",
        "https://www.irs.gov/pub/irs-prior/p596--2021.pdf#page=7",
    )

    def formula(tax_unit, period, parameters):
        # pe-us#9572, first released in 2.10.1. Publication 596 Worksheet 1
        # keeps portfolio income, net capital gains and net passive income in
        # separate baskets, so a loss in one cannot offset income in another.
        # Rental income is treated as passive, as in the NIIT mapping.
        portfolio_income = add(
            tax_unit,
            period,
            [
                "taxable_interest_income",
                "tax_exempt_interest_income",
                "dividend_income",
            ],
        )
        capital_gains = add(
            tax_unit, period, ["net_capital_gains", "non_sch_d_capital_gains"]
        )
        passive_income = add(
            tax_unit, period, ["rental_income", "passive_partnership_s_corp_income"]
        )
        return portfolio_income + max_(0, capital_gains) + max_(0, passive_income)


class ScorpNIITCompatibility(Reform):
    def apply(self):
        if "passive_partnership_s_corp_income" not in self.variables:
            self.add_variable(passive_partnership_s_corp_income)
            self.replace_variable(net_investment_income)
        if _pe_version() < EITC_BASKETS_MIN_PE_VERSION:
            self.update_variable(eitc_relevant_investment_income)


def needs_compatibility_reform(variables):
    return (
        "passive_partnership_s_corp_income" not in variables
        or _pe_version() < EITC_BASKETS_MIN_PE_VERSION
    )


@lru_cache(maxsize=1)
def scorp_tax_benefit_system():
    """Construct the compatible system before loading any situation inputs.

    Passing a structural reform to Simulation creates an unreformed baseline
    branch in older core releases. That branch cannot hold the new input.
    Supplying the already-configured system avoids that invalid baseline.
    """
    from policyengine_us import CountryTaxBenefitSystem, Simulation

    # PE normally shares this system across simulations. Reconstructing it
    # for each main/rebate/marginal-rate simulation duplicates the full model
    # and can exceed the refresh memory budget even for a small input batch.
    native = Simulation.default_tax_benefit_system_instance
    if not needs_compatibility_reform(native.variables):
        return native
    return CountryTaxBenefitSystem(reform=ScorpNIITCompatibility)
