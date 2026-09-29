"""Explicit TAXSIM S-corp NIIT classification, independent of QBI eligibility."""

import re
import warnings
from importlib.metadata import version

# First policyengine-us release that keeps passive losses out of the EITC
# investment-income test (pe-us#9572). On older releases, treating scorp as
# passive lets a passive loss offset interest and dividends and wrongly
# restores the EITC, so the default falls back to active there. PE-US 2.x
# needs Python 3.11+, so Python 3.10 installs always get the fallback.
PASSIVE_MIN_PE_VERSION = (2, 10, 1)


def _pe_version():
    return tuple(
        int(part) for part in re.findall(r"\d+", version("policyengine-us"))[:3]
    )


def default_scorp_treatment():
    if _pe_version() >= PASSIVE_MIN_PE_VERSION:
        return "passive"
    warnings.warn(
        f"policyengine-us {version('policyengine-us')} predates 2.10.1, so S-corp "
        "income is treated as active for NIIT. Upgrade policyengine-us "
        "(Python 3.11+) to use TAXSIM's passive treatment.",
        stacklevel=3,
    )
    return "active"


def validate_scorp_treatment(value=None):
    """Return 'passive' or 'active'; None selects the default for the installed PE."""
    if value is None:
        return default_scorp_treatment()
    if value not in ("passive", "active"):
        raise ValueError("scorp_treatment must be 'passive' or 'active'")
    if value == "passive" and _pe_version() < PASSIVE_MIN_PE_VERSION:
        warnings.warn(
            f"policyengine-us {version('policyengine-us')} predates 2.10.1: passive "
            "S-corp losses can offset interest and dividends in the EITC "
            "investment-income test (pe-us#9572).",
            stacklevel=2,
        )
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
