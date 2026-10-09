"""Explicit TAXSIM S-corp NIIT classification, independent of QBI eligibility."""

import re
from importlib.metadata import version

# First policyengine-us release that keeps passive losses out of the EITC
# investment-income test (pe-us#9572). Older releases net a passive loss
# against interest and dividends there; scorp_reform backports the fixed
# formula to them, so passive is safe on every supported release.
EITC_BASKETS_MIN_PE_VERSION = (2, 10, 1)


def _pe_version():
    return tuple(
        int(part) for part in re.findall(r"\d+", version("policyengine-us"))[:3]
    )


def validate_scorp_treatment(value=None):
    """Return 'passive' or 'active'; None selects TAXSIM's passive convention."""
    if value is None:
        return "passive"
    if value not in ("passive", "active"):
        raise ValueError("scorp_treatment must be 'passive' or 'active'")
    return value


def classify_scorp(situation, treatment):
    """Classify already-mapped income; never add a second source of gross income."""
    treatment = validate_scorp_treatment(treatment)
    for person in situation["people"].values():
        income = person.get("partnership_s_corp_income", {})
        if any(income.values()):
            person["passive_partnership_s_corp_income"] = {
                year: amount if treatment == "passive" else 0
                for year, amount in income.items()
            }
    return situation
