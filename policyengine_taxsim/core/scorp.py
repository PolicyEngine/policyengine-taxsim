"""Explicit TAXSIM S-corp NIIT classification, independent of QBI eligibility."""


def validate_scorp_treatment(value):
    if value not in ("passive", "active"):
        raise ValueError("scorp_treatment must be 'passive' or 'active'")
    return value


def classify_scorp(situation, treatment):
    """Classify already-mapped income; never add a second source of gross income."""
    validate_scorp_treatment(treatment)
    for person in situation["people"].values():
        income = person.get("partnership_s_corp_income", {})
        if any(income.values()):
            person["passive_partnership_s_corp_income"] = {
                year: amount if treatment == "passive" else 0
                for year, amount in income.items()
            }
    return situation
