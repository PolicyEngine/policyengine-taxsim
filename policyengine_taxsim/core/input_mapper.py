from .utils import (
    load_variable_mappings,
    get_state_code,
    get_ordinal,
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
            if field == "qualified_business_income":
                if "pbusinc" in taxsim_vars:
                    people_unit["you"][field] =  {str(year): taxsim_vars.get("pbusinc", 0)}
                if "your_partner" in people_unit and "sbusinc" in taxsim_vars:
                    people_unit["your_partner"][field] = {
                        str(year): taxsim_vars.get("sbusinc", 0)
                    }
            elif len(values) > 1:
                matching_values = [
                    taxsim_vars.get(value, 0)
                    for value in values
                    if value in taxsim_vars
                ]
                if matching_values:
                    people_unit["you"][field] = {str(year): sum(matching_values)}

            elif len(values) == 1 and values[0] in taxsim_vars:
                people_unit["you"][field] = {str(year): taxsim_vars[values[0]]}

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
        "unemployment_compensation": {str(year): float(taxsim_vars.get("pui", 0))},
    }

    if mstat == 2:
        people["your partner"] = {
            "age": {str(year): int(taxsim_vars.get("sage") or 40)},
            "employment_income": {str(year): float(taxsim_vars.get("swages", 0))},
            "is_tax_unit_spouse": {str(year): True},
            "unemployment_compensation": {str(year): float(taxsim_vars.get("sui", 0))},
        }

    for i in range(1, depx + 1):
        dep_name = f"your {get_ordinal(i)} dependent"
        people[dep_name] = {
            "age": {str(year): int(taxsim_vars.get(f"age{i}", 10))},
            "employment_income": {str(year): 0},
            "is_tax_unit_dependent": {str(year): True},
            "is_tax_unit_spouse": {str(year): False},
            "is_tax_unit_head": {str(year): False},
        }

    household_situation = add_additional_units(
        state.lower(), year, household_situation, taxsim_vars
    )

    return household_situation


def set_taxsim_defaults(taxsim_vars: dict) -> dict:
    """
    Set default values for TAXSIM variables if they don't exist or are falsy.

    Args:
        taxsim_vars (dict): Dictionary containing TAXSIM input variables

    Returns:
        dict: Updated dictionary with default values set where needed

    Default values:
        - state: 44 (Texas)
        - depx: 0 (Number of dependents)
        - mstat: 1 (Marital status)
        - taxsimid: 0 (TAXSIM ID)
        - idtl: 0 (output flag)
    """
    DEFAULTS = {
        "state": 44,  # Texas
        "depx": 0,  # Number of dependents
        "mstat": 1,  # Marital status
        "taxsimid": 0,  # TAXSIM ID
        "idtl": 0,  # output flag
    }

    for key, default_value in DEFAULTS.items():
        taxsim_vars[key] = int(taxsim_vars.get(key, default_value) or default_value)

    return taxsim_vars


def generate_household(taxsim_vars):
    """
    Convert TAXSIM input variables to a PolicyEngine situation.

    Args:
        taxsim_vars (dict): Dictionary of TAXSIM input variables

    Returns:
        dict: PolicyEngine situation dictionary
    """

    year = str(int(taxsim_vars["year"]))  # Ensure year is an integer string

    taxsim_vars = set_taxsim_defaults(taxsim_vars)

    state = get_state_code(taxsim_vars["state"])

    situation = form_household_situation(year, state, taxsim_vars)

    return situation
