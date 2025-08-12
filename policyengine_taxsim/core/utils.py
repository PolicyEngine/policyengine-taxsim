import numpy as np
import yaml
from pathlib import Path


def load_variable_mappings():
    """Load variable mappings from YAML file."""
    config_path = Path(__file__).parent.parent / "config" / "variable_mappings.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


STATE_MAPPING = {
    1: "AL",   # Alabama
    2: "AK",   # Alaska
    4: "AZ",   # Arizona
    5: "AR",   # Arkansas
    6: "CA",   # California
    8: "CO",   # Colorado
    9: "CT",   # Connecticut
    10: "DE",  # Delaware
    11: "DC",  # District of Columbia
    12: "FL",  # Florida
    13: "GA",  # Georgia
    15: "HI",  # Hawaii
    16: "ID",  # Idaho
    17: "IL",  # Illinois
    18: "IN",  # Indiana
    19: "IA",  # Iowa
    20: "KS",  # Kansas
    21: "KY",  # Kentucky
    22: "LA",  # Louisiana
    23: "ME",  # Maine
    24: "MD",  # Maryland
    25: "MA",  # Massachusetts
    26: "MI",  # Michigan
    27: "MN",  # Minnesota
    28: "MS",  # Mississippi
    29: "MO",  # Missouri
    30: "MT",  # Montana
    31: "NE",  # Nebraska
    32: "NV",  # Nevada
    33: "NH",  # New Hampshire
    34: "NJ",  # New Jersey
    35: "NM",  # New Mexico
    36: "NY",  # New York
    37: "NC",  # North Carolina
    38: "ND",  # North Dakota
    39: "OH",  # Ohio
    40: "OK",  # Oklahoma
    41: "OR",  # Oregon
    42: "PA",  # Pennsylvania
    44: "RI",  # Rhode Island
    45: "SC",  # South Carolina
    46: "SD",  # South Dakota
    47: "TN",  # Tennessee
    48: "TX",  # Texas
    49: "UT",  # Utah
    50: "VT",  # Vermont
    51: "VA",  # Virginia
    53: "WA",  # Washington
    54: "WV",  # West Virginia
    55: "WI",  # Wisconsin
    56: "WY",  # Wyoming
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
