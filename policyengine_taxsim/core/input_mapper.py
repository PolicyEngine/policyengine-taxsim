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


def convert_v32_dependent_format(taxsim_vars, keep_v32_fields=False):
    """
    Convert TAXSIM v32 dependent age format to individual ages.
    
    In v32:
    - depx: Total personal exemption count
    - dep13: Dependents under 13
    - dep17: Dependents under 17 (includes those under 13)
    - dep18: Dependents under 18 (includes those under 17 and 13)
    
    This function converts these overlapping counts into individual dependent ages
    compatible with the current format (age1, age2, etc.)
    
    Args:
        taxsim_vars (dict): Input variables potentially in v32 format
        keep_v32_fields (bool): If True, preserve v32 fields alongside converted ages
    
    Returns:
        dict: Modified taxsim_vars with individual dependent ages
    """
    # Check if v32 format is being used
    if "dep13" in taxsim_vars or "dep17" in taxsim_vars or "dep18" in taxsim_vars:
        depx = int(taxsim_vars.get("depx", 0))
        dep13 = int(taxsim_vars.get("dep13", 0))
        dep17 = int(taxsim_vars.get("dep17", 0))
        dep18 = int(taxsim_vars.get("dep18", 0))
        
        # Calculate the number of dependents in each age group
        # dep13: under 13
        # dep17 - dep13: 13-16
        # dep18 - dep17: 17
        # depx - dep18: 18+
        
        num_under_13 = dep13
        num_13_to_16 = max(0, dep17 - dep13)
        num_17 = max(0, dep18 - dep17)
        num_18_plus = max(0, depx - dep18)
        
        # Assign ages to dependents
        dependent_ages = []
        
        # Add dependents under 13 (assign age 10 as default)
        for _ in range(num_under_13):
            dependent_ages.append(10)
        
        # Add dependents 13-16 (assign age 15 as default)
        for _ in range(num_13_to_16):
            dependent_ages.append(15)
        
        # Add dependents who are 17
        for _ in range(num_17):
            dependent_ages.append(17)
        
        # Add dependents 18+ (assign age 19 as default)
        for _ in range(num_18_plus):
            dependent_ages.append(19)
        
        # Set individual ages in taxsim_vars
        for i, age in enumerate(dependent_ages, 1):
            taxsim_vars[f"age{i}"] = age
        
        # Clean up v32 specific fields unless asked to keep them
        if not keep_v32_fields:
            taxsim_vars.pop("dep13", None)
            taxsim_vars.pop("dep17", None)
            taxsim_vars.pop("dep18", None)
    
    return taxsim_vars


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
        - idtl: 2 (output flag - full output)
        - year: 2021 (Tax year, can be overridden)
        - page: 40 (Primary taxpayer age)
        - sage: 40 (Spouse age)
    """
    DEFAULTS = {
        "state": 44,  # Texas
        "depx": 0,  # Number of dependents
        "mstat": 1,  # Marital status
        "taxsimid": 0,  # TAXSIM ID
        "idtl": 2,  # output flag - full output
        "year": year,  # Tax year
        "page": 40,  # Primary taxpayer age
        "sage": 40,  # Spouse age
    }

    for key, default_value in DEFAULTS.items():
        # Use default only if key is missing or None, not if it's 0
        if key not in taxsim_vars or taxsim_vars[key] is None:
            taxsim_vars[key] = default_value
        else:
            taxsim_vars[key] = int(taxsim_vars[key])

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
        "idtl": 2,  # Output flag - full output
        "page": 40,  # Primary age
        "sage": 40,  # Spouse age
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

    taxsim_vars = set_taxsim_defaults(taxsim_vars, int(year))
    
    # Convert v32 dependent format if present
    taxsim_vars = convert_v32_dependent_format(taxsim_vars)

    state = get_state_code(taxsim_vars["state"])

    situation = form_household_situation(year, state, taxsim_vars)

    return situation
