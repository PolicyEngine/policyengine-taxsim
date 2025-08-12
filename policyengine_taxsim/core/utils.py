import numpy as np
import yaml
from pathlib import Path


def load_variable_mappings():
    """Load variable mappings from YAML file."""
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
