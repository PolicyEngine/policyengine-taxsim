import functools
import numpy as np
import yaml
from pathlib import Path


@functools.lru_cache(maxsize=1)
def load_variable_mappings():
    """Load variable mappings from YAML file (cached after first call)."""
    config_path = Path(__file__).parent.parent / "config" / "variable_mappings.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


STATE_MAPPING = {
    1: "AL",
    2: "AK",
    3: "AZ",
    4: "AR",
    5: "CA",
    6: "CO",
    7: "CT",
    8: "DE",
    9: "DC",
    10: "FL",
    11: "GA",
    12: "HI",
    13: "ID",
    14: "IL",
    15: "IN",
    16: "IA",
    17: "KS",
    18: "KY",
    19: "LA",
    20: "ME",
    21: "MD",
    22: "MA",
    23: "MI",
    24: "MN",
    25: "MS",
    26: "MO",
    27: "MT",
    28: "NE",
    29: "NV",
    30: "NH",
    31: "NJ",
    32: "NM",
    33: "NY",
    34: "NC",
    35: "ND",
    36: "OH",
    37: "OK",
    38: "OR",
    39: "PA",
    40: "RI",
    41: "SC",
    42: "SD",
    43: "TN",
    44: "TX",
    45: "UT",
    46: "VT",
    47: "VA",
    48: "WA",
    49: "WV",
    50: "WI",
    51: "WY",
}


def get_state_code(state_number):
    """Convert state number to state code."""
    # For invalid state codes (including 0), default to Texas (consistent with set_taxsim_defaults)
    return STATE_MAPPING.get(state_number, "TX")


def get_state_number(state_code):
    """Convert state code to state number."""
    state_mapping_reverse = {v: k for k, v in STATE_MAPPING.items()}
    return state_mapping_reverse.get(state_code, 0)  # Return 0 for invalid state codes


def is_date(string):
    """Check if a string represents a valid year."""
    try:
        year = int(string)
        return 1900 <= year <= 2100  # Assuming years between 1900 and 2100 are valid
    except ValueError:
        return False


def to_roundedup_number(value):
    if isinstance(value, np.ndarray):
        return round(value[0], 2)
    else:
        return round(value, 2)


def convert_taxsim32_dependents(taxsim_vars):
    """
    Convert TAXSIM32 dependent count format (dep13, dep17, dep18) 
    to individual age format (age1, age2, etc.).
    
    TAXSIM32 format uses cumulative counts:
    - dep13: Number of dependents under 13
    - dep17: Number of dependents under 17 (includes those under 13)
    - dep18: Number of dependents under 18 (includes those under 17 and 13)
    
    This function infers individual ages based on these counts.
    If depx exceeds dep18, additional dependents are assigned age 21.
    
    Args:
        taxsim_vars (dict): Dictionary containing TAXSIM input variables
        
    Returns:
        dict: Updated dictionary with age1, age2, etc. fields added
    """
    # Check if we have the TAXSIM32 format fields present
    # Just check for presence, not values, since all three could be 0 with depx > 0 (all dependents 18+)
    has_taxsim32_fields = 'dep13' in taxsim_vars or 'dep17' in taxsim_vars or 'dep18' in taxsim_vars
    
    # Check if we already have individual age fields explicitly set (including 0 for newborns)
    # We consider age fields as explicitly set if they exist in the input
    has_individual_age_fields = any(
        f'age{i}' in taxsim_vars and taxsim_vars[f'age{i}'] is not None
        for i in range(1, 12)
    )
    
    # Get depx value
    depx = int(taxsim_vars.get('depx', 0) or 0)
    
    # Only convert if:
    # 1. We have TAXSIM32 fields (dep13/17/18) with meaningful values
    # 2. AND we don't already have individual age fields set
    # This ensures we only convert when TAXSIM32 format is actually being used
    if has_taxsim32_fields and not has_individual_age_fields:
        dep13 = int(taxsim_vars.get('dep13', 0) or 0)
        dep17 = int(taxsim_vars.get('dep17', 0) or 0)
        dep18 = int(taxsim_vars.get('dep18', 0) or 0)
        depx = int(taxsim_vars.get('depx', 0) or 0)
        
        # Calculate the number of dependents in each age bracket
        # Note: These are cumulative, so we need to subtract to get individual counts
        num_under_13 = dep13
        num_13_to_16 = dep17 - dep13  # Those under 17 but not under 13
        num_17 = dep18 - dep17  # Those under 18 but not under 17 (i.e., exactly 17)
        
        # Calculate number of dependents 18 or older
        num_18_or_older = 0
        if depx > dep18:
            num_18_or_older = depx - dep18  # These will be assigned age 21
        
        # Set depx to the total number of dependents if not already set
        if 'depx' not in taxsim_vars or taxsim_vars['depx'] is None:
            taxsim_vars['depx'] = max(depx, dep18)
        else:
            # Ensure depx is at least as large as dep18
            taxsim_vars['depx'] = max(int(taxsim_vars['depx']), dep18)
        
        # Generate individual ages based on the counts
        # We'll use typical ages for each bracket
        dep_counter = 1
        
        # Add dependents under 13 (use age 10 as default)
        for _ in range(num_under_13):
            if dep_counter <= 11:  # TAXSIM supports up to 11 dependents
                taxsim_vars[f'age{dep_counter}'] = 10
                dep_counter += 1
        
        # Add dependents aged 13-16 (use age 15 as default)
        for _ in range(num_13_to_16):
            if dep_counter <= 11:
                taxsim_vars[f'age{dep_counter}'] = 15
                dep_counter += 1
        
        # Add dependents aged 17 (use age 17)
        for _ in range(num_17):
            if dep_counter <= 11:
                taxsim_vars[f'age{dep_counter}'] = 17
                dep_counter += 1
        
        # Add dependents aged 18 or older (use age 21 as default for adult dependents)
        for _ in range(num_18_or_older):
            if dep_counter <= 11:
                taxsim_vars[f'age{dep_counter}'] = 21
                dep_counter += 1
    
    # Handle NaN and age 0 inputs - default them to age 10
    # Check all age fields up to age11
    for i in range(1, 12):
        age_field = f'age{i}'
        if age_field in taxsim_vars:
            age_value = taxsim_vars[age_field]
            # Check for NaN (using numpy's isnan if it's a numpy type, or math.isnan for regular floats)
            is_nan = False
            try:
                import math
                if isinstance(age_value, (float, np.floating)):
                    is_nan = math.isnan(age_value) if not isinstance(age_value, np.ndarray) else np.isnan(age_value)
            except (TypeError, ValueError):
                pass
            
            # If age is NaN or 0, default to 10
            if is_nan or age_value == 0 or age_value == 0.0:
                taxsim_vars[age_field] = 10
    
    return taxsim_vars


def get_ordinal(n):
    ordinals = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
    }
    return ordinals.get(n, f"{n}th")


# TAXSIM SOI to PolicyEngine FIPS state code mapping
# Based on https://taxsim.nber.org/statesoi.html and PolicyEngine's state mapping
SOI_TO_FIPS_MAP = {
    1: 1,  # Alabama
    2: 2,  # Alaska
    3: 4,  # Arizona
    4: 5,  # Arkansas
    5: 6,  # California
    6: 8,  # Colorado
    7: 9,  # Connecticut
    8: 10,  # Delaware
    9: 11,  # DC
    10: 12,  # Florida
    11: 13,  # Georgia
    12: 15,  # Hawaii
    13: 16,  # Idaho
    14: 17,  # Illinois
    15: 18,  # Indiana
    16: 19,  # Iowa
    17: 20,  # Kansas
    18: 21,  # Kentucky
    19: 22,  # Louisiana
    20: 23,  # Maine
    21: 24,  # Maryland
    22: 25,  # Massachusetts
    23: 26,  # Michigan
    24: 27,  # Minnesota
    25: 28,  # Mississippi
    26: 29,  # Missouri
    27: 30,  # Montana
    28: 31,  # Nebraska
    29: 32,  # Nevada
    30: 33,  # NewHampshire
    31: 34,  # NewJersey
    32: 35,  # NewMexico
    33: 36,  # NewYork (SOI 33 → FIPS 36!)
    34: 37,  # NorthCarolina
    35: 38,  # NorthDakota
    36: 39,  # Ohio
    37: 40,  # Oklahoma
    38: 41,  # Oregon
    39: 42,  # Pennsylvania
    40: 44,  # RhodeIsland
    41: 45,  # SouthCarolina
    42: 46,  # SouthDakota
    43: 47,  # Tennessee
    44: 48,  # Texas
    45: 49,  # Utah
    46: 50,  # Vermont
    47: 51,  # Virginia
    48: 53,  # Washington
    49: 54,  # WestVirginia
    50: 55,  # Wisconsin
    51: 56,  # Wyoming
}
