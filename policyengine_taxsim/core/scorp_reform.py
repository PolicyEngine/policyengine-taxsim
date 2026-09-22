"""Backport the NIIT classification input for supported older PE-US releases.

Python 3.10 resolves PE-US 1.x. Newer PE-US already defines this input and
includes it in NII, so this reform is a no-op there. It does not implement
section 469 loss limits or change QBI/AGI/SECA.
"""

from policyengine_us.model_api import Variable, Person, TaxUnit, YEAR, USD, Reform, add


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


class ScorpNIITCompatibility(Reform):
    def apply(self):
        if "passive_partnership_s_corp_income" not in self.variables:
            self.add_variable(passive_partnership_s_corp_income)
            self.replace_variable(net_investment_income)
