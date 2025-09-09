from .utils import (
    load_variable_mappings,
    get_state_code,
    get_ordinal,
    convert_taxsim32_dependents,
)
import copy


def add_additional_units(state, year, situation, taxsim_vars):

    additional_tax_units_config = load_variable_mappings()["taxsim_to_policyengine"][
        "household_situation"
    ]["additional_tax_units"]
    additional_income_units_config = load_variable_mappings()["taxsim_to_policyengine"][
        "household_situation"
    ]["additional_income_units"]

    tax_unit = situation["tax_units"]["your tax unit"]
    people_unit = situation["people"]

    # Get marital status to determine if income should be split
    mstat = taxsim_vars.get("mstat", 1)
    is_married_filing_jointly = mstat == 2

    # Income types that should be split evenly between spouses when married filing jointly
    income_types_to_split = {
        "taxable_interest_income",
        "qualified_dividend_income",
        "long_term_capital_gains",
        "partnership_s_corp_income",
        "taxable_private_pension_income",
        "short_term_capital_gains",
        "social_security_retirement",
    }

    for item in additional_tax_units_config:
        for field, values in item.items():
            if not values:
                continue

            if field == "state_use_tax":
                if state.lower() in values:
                    tax_unit[f"{state}_use_tax"] = {str(year): 0}
                continue

            if field == "de_relief_rebate":
                tax_unit["de_relief_rebate"] = {str(year): 0}
                continue

            if field == "state_sales_tax":
                tax_unit["state_sales_tax"] = {str(year): 0}
                continue

            if len(values) > 1:
                matching_values = [
                    taxsim_vars.get(value, 0)
                    for value in values
                    if value in taxsim_vars
                ]
                if matching_values:
                    tax_unit[field] = {str(year): sum(matching_values)}

            elif len(values) == 1 and values[0] in taxsim_vars:
                tax_unit[field] = {str(year): taxsim_vars[values[0]]}

    for item in additional_income_units_config:
        for field, values in item.items():
            if not values:
                continue

            if field == "self_employment_income":
                if "psemp" in taxsim_vars:
                    people_unit["you"][field] = {str(year): taxsim_vars.get("psemp", 0)}
                if "your partner" in people_unit and "ssemp" in taxsim_vars:
                    people_unit["your partner"][field] = {
                        str(year): taxsim_vars.get("ssemp", 0)
                    }

            elif field == "unemployment_compensation":
                if "pui" in taxsim_vars:
                    people_unit["you"][field] = {str(year): taxsim_vars.get("pui", 0)}
                if "your partner" in people_unit and "sui" in taxsim_vars:
                    people_unit["your partner"][field] = {
                        str(year): taxsim_vars.get("sui", 0)
                    }

            elif len(values) > 1:
                matching_values = [
                    taxsim_vars.get(value, 0)
                    for value in values
                    if value in taxsim_vars
                ]
                if matching_values:
                    total_value = sum(matching_values)

                    # Split evenly between spouses if married filing jointly and this income type should be split
                    if (
                        is_married_filing_jointly
                        and "your partner" in people_unit
                        and field in income_types_to_split
                    ):
                        split_value = total_value / 2
                        people_unit["you"][field] = {str(year): split_value}
                        people_unit["your partner"][field] = {str(year): split_value}
                    else:
                        people_unit["you"][field] = {str(year): total_value}

            elif len(values) == 1 and values[0] in taxsim_vars:
                total_value = taxsim_vars[values[0]]

                # Split evenly between spouses if married filing jointly and this income type should be split
                if (
                    is_married_filing_jointly
                    and "your partner" in people_unit
                    and field in income_types_to_split
                ):
                    split_value = total_value / 2
                    people_unit["you"][field] = {str(year): split_value}
                    people_unit["your partner"][field] = {str(year): split_value}
                else:
                    people_unit["you"][field] = {str(year): total_value}

    return situation


def form_household_situation(year, state, taxsim_vars):
    mappings = load_variable_mappings()["taxsim_to_policyengine"]

    household_situation = copy.deepcopy(mappings["household_situation"])
    household_situation.pop("additional_tax_units", None)
    household_situation.pop("additional_income_units", None)

    depx = taxsim_vars["depx"]
    mstat = taxsim_vars["mstat"]

    if mstat == 2:  # Married filing jointly
        members = ["you", "your partner"]
    else:  # Single, separate, or dependent taxpayer
        members = ["you"]

    for i in range(1, depx + 1):
        members.append(f"your {get_ordinal(i)} dependent")

    household_situation["families"]["your family"]["members"] = members
    household_situation["households"]["your household"]["members"] = members
    household_situation["tax_units"]["your tax unit"]["members"] = members

    household_situation["spm_units"]["your household"]["members"] = members

    if depx > 0:
        household_situation["marital_units"] = {
            "your marital unit": {
                "members": ["you", "your partner"] if mstat == 2 else ["you"]
            }
        }
        for i in range(1, depx + 1):
            dep_name = f"your {get_ordinal(i)} dependent"
            household_situation["marital_units"][f"{dep_name}'s marital unit"] = {
                "members": [dep_name],
                "marital_unit_id": {str(year): i},
            }
    else:
        household_situation["marital_units"]["your marital unit"]["members"] = (
            ["you", "your partner"] if mstat == 2 else ["you"]
        )

    household_situation["households"]["your household"]["state_name"][str(year)] = state

    people = household_situation["people"]

    people["you"] = {
        "age": {str(year): int(taxsim_vars.get("page") or 40)},
        "employment_income": {str(year): float(taxsim_vars.get("pwages", 0))},
        "is_tax_unit_head": {str(year): True},
    }

    if mstat == 2:
        people["your partner"] = {
            "age": {str(year): int(taxsim_vars.get("sage") or 40)},
            "employment_income": {str(year): float(taxsim_vars.get("swages", 0))},
            "is_tax_unit_spouse": {str(year): True},
        }

    for i in range(1, depx + 1):
        dep_name = f"your {get_ordinal(i)} dependent"
        people[dep_name] = {
            "age": {str(year): int(taxsim_vars.get(f"age{i}", 10)) if taxsim_vars.get(f"age{i}") is not None else 10},
            "employment_income": {str(year): 0},
            "is_tax_unit_dependent": {str(year): True},
            "is_tax_unit_spouse": {str(year): False},
            "is_tax_unit_head": {str(year): False},
        }

    household_situation = add_additional_units(
        state.lower(), year, household_situation, taxsim_vars
    )
    
    # Explicitly set SSI to 0 for all people to prevent PolicyEngine from imputing SSI benefits
    # TAXSIM does not model SSI, so we need to ensure it's not automatically calculated
    for person_name in household_situation["people"]:
        household_situation["people"][person_name]["ssi"] = {str(year): 0}
    
    # Explicitly set person-level benefit programs to 0 to prevent PolicyEngine from imputing these benefits
    # TAXSIM does not model these programs, so we need to ensure they're not automatically calculated
    for person_name in household_situation["people"]:
        household_situation["people"][person_name]["head_start"] = {str(year): 0}
        household_situation["people"][person_name]["early_head_start"] = {str(year): 0}
        household_situation["people"][person_name]["commodity_supplemental_food_program"] = {str(year): 0}
    
    # Explicitly set SNAP to 0 for all SPM units to prevent PolicyEngine from imputing SNAP benefits
    # TAXSIM does not model SNAP, so we need to ensure it's not automatically calculated
    for spm_unit_name in household_situation["spm_units"]:
        household_situation["spm_units"][spm_unit_name]["snap"] = {str(year): 0}
    
    # Explicitly set TANF to 0 for all SPM units to prevent PolicyEngine from imputing TANF benefits
    # TAXSIM does not model TANF, so we need to ensure it's not automatically calculated
    for spm_unit_name in household_situation["spm_units"]:
        household_situation["spm_units"][spm_unit_name]["tanf"] = {str(year): 0}
    
    # Explicitly set free_school_meals to 0 for all SPM units to prevent PolicyEngine from imputing free school meal benefits
    # TAXSIM does not model free school meals, so we need to ensure it's not automatically calculated
    for spm_unit_name in household_situation["spm_units"]:
        household_situation["spm_units"][spm_unit_name]["free_school_meals"] = {str(year): 0}
    
    # Explicitly set reduced_price_school_meals to 0 for all SPM units to prevent PolicyEngine from imputing reduced price school meal benefits
    # TAXSIM does not model reduced price school meals, so we need to ensure it's not automatically calculated
    for spm_unit_name in household_situation["spm_units"]:
        household_situation["spm_units"][spm_unit_name]["reduced_price_school_meals"] = {str(year): 0}

    return household_situation


def set_taxsim_defaults(taxsim_vars: dict, year: int = 2021) -> dict:
    """
    Set default values for TAXSIM variables if they don't exist or are falsy.

    Args:
        taxsim_vars (dict): Dictionary containing TAXSIM input variables
        year (int): Default year to use if not specified in taxsim_vars

    Returns:
        dict: Updated dictionary with default values set where needed

    Default values:
        - state: 44 (Texas)
        - depx: 0 (Number of dependents)
        - mstat: 1 (Marital status)
        - taxsimid: 0 (TAXSIM ID)
        - idtl: 0 (output flag)
        - year: 2021 (Tax year, can be overridden)
        - page: 40 (Primary taxpayer age)
        - sage: 40 (Age of secondary taxpayer)
    """
    DEFAULTS = {
        "state": 44,  # Texas
        "depx": 0,  # Number of dependents
        "mstat": 1,  # Marital status
        "taxsimid": 0,  # TAXSIM ID
        "idtl": 0,  # output flag
        "year": year,  # Tax year
        "page": 40,  # Primary taxpayer age
        "sage": 40,  # Age of secondary taxpayer
    }

    for key, default_value in DEFAULTS.items():
        taxsim_vars[key] = int(taxsim_vars.get(key, default_value) or default_value)

    return taxsim_vars


def get_taxsim_defaults(year: int = 2021) -> dict:
    """
    Get a dictionary of all TAXSIM default values.

    Args:
        year (int): Tax year for defaults

    Returns:
        dict: Dictionary containing all default TAXSIM values
    """
    return {
        "taxsimid": 0,
        "year": year,
        "state": 44,  # Texas
        "mstat": 1,  # Single
        "depx": 0,  # Number of dependents
        "idtl": 0,  # Output flag
        "page": 40,  # Primary age
        "sage": 40,  # Age of secondary taxpayer
    }


def generate_household(taxsim_vars):
    """
    Convert TAXSIM input variables to a PolicyEngine situation.

    Args:
        taxsim_vars (dict): Dictionary of TAXSIM input variables

    Returns:
        dict: PolicyEngine situation dictionary
    """

    year = str(
        int(float(taxsim_vars.get("year", 2021)))
    )  # Ensure year is an integer string, handling decimals

    # Convert TAXSIM32 dependent format if present
    taxsim_vars = convert_taxsim32_dependents(taxsim_vars)
    
    taxsim_vars = set_taxsim_defaults(taxsim_vars, int(year))

    state = get_state_code(taxsim_vars["state"])

    situation = form_household_situation(year, state, taxsim_vars)

    return situation
