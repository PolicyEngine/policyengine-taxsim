from policyengine_taxsim.core.utils import (
    load_variable_mappings,
    get_state_code,
)


def import_single_household(taxsim_vars):
    """
    Convert TAXSIM input variables to a PolicyEngine situation.

    Args:
        taxsim_vars (dict): Dictionary of TAXSIM input variables

    Returns:
        dict: PolicyEngine situation dictionary
    """
    mappings = load_variable_mappings()["taxsim_to_policyengine"]

    year = str(int(taxsim_vars["year"]))  # Ensure year is an integer string
    state = get_state_code(taxsim_vars["state"])

    situation = {
        "people": {
            "you": {
                "age": {year: int(taxsim_vars.get("page", 40))},
                "employment_income": {year: int(taxsim_vars.get("pwages", 0))},
            }
        },
        "households": {
            "your household": {"members": ["you"], "state_name": {year: state}}
        },
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    return situation
