import pytest
from policyengine_taxsim.core.input_mapper import import_single_household
from policyengine_taxsim.core.output_mapper import export_single_household


def test_import_single_household():
    taxsim_input = {
        "year": 2022,
        "state": 6,  # Colorado
        "page": 35,
        "pwages": 50000,
    }

    expected_output = {
        "people": {
            "you": {"age": {"2022": 35}, "employment_income": {"2022": 50000}}
        },
        "households": {
            "your household": {
                "members": ["you"],
                "state_name": {"2022": "CO"},
            }
        },
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = import_single_household(taxsim_input)
    assert result == expected_output


def test_export_single_household():
    policyengine_situation = {
        "people": {
            "you": {"age": {"2022": 35}, "employment_income": {"2022": 50000}}
        },
        "households": {
            "your household": {
                "members": ["you"],
                "state_name": {"2022": "CO"},
            }
        },
        "tax_units": {"your tax unit": {"members": ["you"]}},
    }

    result = export_single_household(policyengine_situation)

    assert result["year"] == 2022
    assert result["state"] == 6  # Colorado
    assert "fiitax" in result
    assert "siitax" in result
    # Note: We can't easily predict the exact tax values without mocking the PolicyEngine simulation,
    # so we're just checking that these keys exist in the output.


@pytest.fixture
def sample_taxsim_input():
    return {"year": 2022, "state": 6, "page": 35, "pwages": 50000}  # Colorado


def test_roundtrip(sample_taxsim_input):
    # Import TAXSIM input to PolicyEngine situation
    pe_situation = import_single_household(sample_taxsim_input)

    # Export PolicyEngine situation back to TAXSIM output
    taxsim_output = export_single_household(pe_situation)

    # Check that key information is preserved
    assert taxsim_output["year"] == sample_taxsim_input["year"]
    assert taxsim_output["state"] == sample_taxsim_input["state"]
    # Again, we can't easily check the exact tax values, but we can ensure they exist
    assert "fiitax" in taxsim_output
    assert "siitax" in taxsim_output
