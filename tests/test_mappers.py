import pytest

from policyengine_taxsim import generate_household, export_household


@pytest.fixture
def sample_taxsim_input():
    return {
        "year": 2021,
        "state": 3,
        "page": 35,
        "pwages": 50000,
        "taxsimid": 11,
        "idtl": 0,
    }


@pytest.fixture
def sample_taxsim_input_without_state():
    return {"year": 2021, "page": 35, "pwages": 50000, "taxsimid": 11, "idtl": 0}


@pytest.fixture
def sample_taxsim_input_with_state_eq_0():
    return {
        "year": 2021,
        "page": 35,
        "state": 0,
        "pwages": 50000,
        "taxsimid": 11,
        "idtl": 0,
    }


@pytest.fixture
def sample_taxsim_input_for_joint():
    return {
        "year": 2023,
        "page": 40,
        "sage": 40,
        "state": 0,
        "mstat": 2,
        "pwages": 45000,
        "swages": 30000,
        "taxsimid": 11,
        "idtl": 2,
        "depx": 2,
    }


@pytest.fixture
def sample_taxsim_input_for_household_with_dependent():
    return {
        "year": 2023,
        "state": 39,
        "pwages": 81000.001,
        "swages": 0,
        "taxsimid": 11,
        "idtl": 2,
        "mstat": 2,
        "depx": 2,
        "age1": 4,
    }


@pytest.fixture
def sample_taxsim_input_for_household_with_dependent_single_parent():
    return {
        "year": 2023,
        "state": 39,
        "pwages": 81000.001,
        "swages": 0,
        "taxsimid": 11,
        "idtl": 2,
        "mstat": 1,
        "depx": 2,
        "age1": 4,
    }


def test_import_single_household(sample_taxsim_input):
    expected_output = {
        "families": {"your family": {"members": ["you"]}},
        "households": {
            "your household": {"members": ["you"], "state_name": {"2021": "AZ"}}
        },
        "marital_units": {"your marital unit": {"members": ["you"]}},
        "people": {
            "you": {
                "age": {"2021": 35},
                "employment_income": {"2021": 50000},
                "is_tax_unit_head": {"2021": True},
                
            }
        },
        "spm_units": {"your household": {"members": ["you"]}},
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = generate_household(sample_taxsim_input)
    assert result == expected_output


def test_import_single_household_without_state(sample_taxsim_input_without_state):
    expected_output = {
        "families": {"your family": {"members": ["you"]}},
        "households": {
            "your household": {"members": ["you"], "state_name": {"2021": "TX"}}
        },
        "marital_units": {"your marital unit": {"members": ["you"]}},
        "people": {
            "you": {
                "age": {"2021": 35},
                "employment_income": {"2021": 50000},
                "is_tax_unit_head": {"2021": True},
                
            }
        },
        "spm_units": {"your household": {"members": ["you"]}},
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = generate_household(sample_taxsim_input_without_state)
    assert result == expected_output


def test_import_single_household_with_state_eq_0(sample_taxsim_input_with_state_eq_0):
    expected_output = {
        "families": {"your family": {"members": ["you"]}},
        "households": {
            "your household": {"members": ["you"], "state_name": {"2021": "TX"}}
        },
        "marital_units": {"your marital unit": {"members": ["you"]}},
        "people": {
            "you": {
                "age": {"2021": 35},
                "employment_income": {"2021": 50000},
                "is_tax_unit_head": {"2021": True},
                
            }
        },
        "spm_units": {"your household": {"members": ["you"]}},
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = generate_household(sample_taxsim_input_with_state_eq_0)
    assert result == expected_output


def test_export_single_household(sample_taxsim_input):
    policyengine_single_household_situation = {
        "families": {"your family": {"members": ["you"]}},
        "households": {
            "your household": {"members": ["you"], "state_name": {"2021": "AZ"}}
        },
        "marital_units": {"your marital unit": {"members": ["you"]}},
        "people": {
            "you": {
                "age": {"2021": 35},
                "employment_income": {"2021": 50000},
                
                "is_tax_unit_head": {"2021": True},
            }
        },
        "spm_units": {"your household": {"members": ["you"]}},
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = export_household(
        sample_taxsim_input, policyengine_single_household_situation, False, False
    )
    assert result["year"] == 2021
    assert result["state"] == 3
    assert "fiitax" in result
    assert "siitax" in result


def test_joint_household(sample_taxsim_input_for_joint):
    expected_output_joint_situation = {
        "families": {
            "your family": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ]
            }
        },
        "households": {
            "your household": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ],
                "state_name": {"2023": "TX"},
            }
        },
        "marital_units": {
            "your marital unit": {"members": ["you", "your partner"]},
            "your first dependent's marital unit": {
                "members": ["your first dependent"],
                "marital_unit_id": {"2023": 1},
            },
            "your second dependent's marital unit": {
                "members": ["your second dependent"],
                "marital_unit_id": {"2023": 2},
            },
        },
        "people": {
            "you": {
                "age": {"2023": 40},
                "employment_income": {"2023": 45000.0},
                "is_tax_unit_head": {"2023": True},
                
            },
            "your partner": {
                "age": {"2023": 40},
                "employment_income": {"2023": 30000.0},
                "is_tax_unit_spouse": {"2023": True},
                
            },
            "your first dependent": {
                "age": {"2023": 10},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
            "your second dependent": {
                "age": {"2023": 10},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
        },
        "spm_units": {
            "your household": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ]
            }
        },
        "tax_units": {
            "your tax unit": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ]
            }
        },
    }

    result = generate_household(sample_taxsim_input_for_joint)
    assert result == expected_output_joint_situation


def test_household_with_dependent(sample_taxsim_input_for_household_with_dependent):
    expected_output = {
        "families": {
            "your family": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ]
            }
        },
        "households": {
            "your household": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ],
                "state_name": {"2023": "PA"},
            }
        },
        "marital_units": {
            "your marital unit": {"members": ["you", "your partner"]},
            "your first dependent's marital unit": {
                "members": ["your first dependent"],
                "marital_unit_id": {"2023": 1},
            },
            "your second dependent's marital unit": {
                "members": ["your second dependent"],
                "marital_unit_id": {"2023": 2},
            },
        },
        "people": {
            "you": {
                "age": {"2023": 40},
                "employment_income": {"2023": 81000.001},
                "is_tax_unit_head": {"2023": True},
                
            },
            "your partner": {
                "age": {"2023": 40},
                "employment_income": {"2023": 0.0},
                "is_tax_unit_spouse": {"2023": True},
                
            },
            "your first dependent": {
                "age": {"2023": 4},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
            "your second dependent": {
                "age": {"2023": 10},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
        },
        "spm_units": {
            "your household": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ]
            }
        },
        "tax_units": {
            "your tax unit": {
                "members": [
                    "you",
                    "your partner",
                    "your first dependent",
                    "your second dependent",
                ],
                                    "pa_use_tax": {"2023": 0},
            }
        },
    }

    result = generate_household(sample_taxsim_input_for_household_with_dependent)
    assert result == expected_output


def test_household_with_dependent_single_parent(
    sample_taxsim_input_for_household_with_dependent_single_parent,
):
    expected_output = {
        "families": {
            "your family": {
                "members": ["you", "your first dependent", "your second dependent"]
            }
        },
        "households": {
            "your household": {
                "members": ["you", "your first dependent", "your second dependent"],
                "state_name": {"2023": "PA"},
            }
        },
        "marital_units": {
            "your marital unit": {"members": ["you"]},
            "your first dependent's marital unit": {
                "members": ["your first dependent"],
                "marital_unit_id": {"2023": 1},
            },
            "your second dependent's marital unit": {
                "members": ["your second dependent"],
                "marital_unit_id": {"2023": 2},
            },
        },
        "people": {
            "you": {
                "age": {"2023": 40},
                "employment_income": {"2023": 81000.001},
                "is_tax_unit_head": {"2023": True},
                
            },
            "your first dependent": {
                "age": {"2023": 4},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
            "your second dependent": {
                "age": {"2023": 10},
                "employment_income": {"2023": 0},
                "is_tax_unit_dependent": {"2023": True},
                "is_tax_unit_spouse": {"2023": False},
                "is_tax_unit_head": {"2023": False},
            },
        },
        "spm_units": {
            "your household": {
                "members": ["you", "your first dependent", "your second dependent"]
            }
        },
        "tax_units": {
            "your tax unit": {
                "members": ["you", "your first dependent", "your second dependent"],
                                    "pa_use_tax": {"2023": 0},
            }
        },
    }

    result = generate_household(
        sample_taxsim_input_for_household_with_dependent_single_parent
    )
    assert result == expected_output


def test_roundtrip(sample_taxsim_input):
    # Import TAXSIM input to PolicyEngine situation
    pe_situation = generate_household(sample_taxsim_input)

    # Export PolicyEngine situation back to TAXSIM output
    taxsim_output = export_household(sample_taxsim_input, pe_situation, False, False)

    # Check that key information is preserved
    assert taxsim_output["year"] == sample_taxsim_input["year"]
    assert taxsim_output["state"] == sample_taxsim_input["state"]
    # Again, we can't easily check the exact tax values, but we can ensure they exist
    assert "fiitax" in taxsim_output
    assert "siitax" in taxsim_output
