from .utils import (
    load_variable_mappings,
    get_state_code, get_ordinal,
)
import copy


def add_additional_units(state, year, situation, taxsim_vars):

    additional_tax_units_config = load_variable_mappings()["taxsim_to_policyengine"]["household_situation"]["additional_tax_units"]
    additional_income_units_config = load_variable_mappings()["taxsim_to_policyengine"]["household_situation"]["additional_income_units"]

    tax_unit = situation["tax_units"]["your tax unit"]
    people_unit = situation["people"]["you"]

    for item in additional_tax_units_config:
        for field, values in item.items():
            if not values:
                continue

            if field == "state_use_tax":
                if state.lower() in values:
                    tax_unit[f"{state}_use_tax"] = {str(year): 0}
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

            if len(values) > 1:
                matching_values = [
                    taxsim_vars.get(value, 0)
                    for value in values
                    if value in taxsim_vars
                ]
                if matching_values:
                    people_unit[field] = {str(year): sum(matching_values)}

            elif len(values) == 1 and values[0] in taxsim_vars:
                people_unit[field] = {str(year): taxsim_vars[values[0]]}

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
                "marital_unit_id": {str(year): i}
            }
    else:
        household_situation["marital_units"]["your marital unit"]["members"] = (
            ["you", "your partner"] if mstat == 2 else ["you"]
        )

    household_situation["households"]["your household"]["state_name"][str(year)] = state

    people = household_situation["people"]

    people["you"] = {
        "age": {str(year): int(taxsim_vars.get("page", 40))},
        "employment_income": {str(year): float(taxsim_vars.get("pwages", 0))}
    }

    if mstat == 2:
        people["your partner"] = {
            "age": {str(year): int(taxsim_vars.get("sage", 40))},
            "employment_income": {str(year): float(taxsim_vars.get("swages", 0))}
        }

    for i in range(1, depx + 1):
        dep_name = f"your {get_ordinal(i)} dependent"
        people[dep_name] = {
            "age": {str(year): int(taxsim_vars.get(f"age{i}", 10))},
            "employment_income": {str(year): 0}
        }

    household_situation = add_additional_units(state.lower(), year, household_situation, taxsim_vars)

    return household_situation


def check_if_exists_or_set_defaults(taxsim_vars):
    taxsim_vars["state"] = int(taxsim_vars.get("state",
                                               44) or 44)  # set TX (texas) as default is no state field has passed or passed as 0

    taxsim_vars["depx"] = int(taxsim_vars.get("depx", 0) or 0)

    taxsim_vars["mstat"] = int(taxsim_vars.get("mstat", 1) or 1)

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

    taxsim_vars = check_if_exists_or_set_defaults(taxsim_vars)

    state = get_state_code(taxsim_vars["state"])

    situation = form_household_situation(year, state, taxsim_vars)

    return situation
