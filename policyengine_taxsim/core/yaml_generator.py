import yaml
import numpy as np
from typing import Dict, Any, Optional, List


class PETestsYAMLGenerator:
    def __init__(self):
        pass

    def _get_year(self, household_data: Dict[str, Any]) -> int:
        """Extract the year from household data."""
        state_name_data = (
            household_data.get("households", {})
            .get("your household", {})
            .get("state_name", {})
        )
        return int(next(iter(state_name_data.keys()), "2024"))

    def _map_person_ids(self, people_data: Dict[str, Any]) -> Dict[str, str]:
        """Map old person IDs to new standardized IDs (person1, person2, etc.)."""
        return {old_id: f"person{i + 1}" for i, old_id in enumerate(people_data.keys())}

    def _get_state_fips(self, state_name: str) -> int:
        """Get FIPS code for a state."""
        state_fips = {
            "AL": 1,
            "AK": 2,
            "AZ": 4,
            "AR": 5,
            "CA": 6,
            "CO": 8,
            "CT": 9,
            "DE": 10,
            "FL": 12,
            "GA": 13,
            "HI": 15,
            "ID": 16,
            "IL": 17,
            "IN": 18,
            "IA": 19,
            "KS": 20,
            "KY": 21,
            "LA": 22,
            "ME": 23,
            "MD": 24,
            "MA": 25,
            "MI": 26,
            "MN": 27,
            "MS": 28,
            "MO": 29,
            "MT": 30,
            "NE": 31,
            "NV": 32,
            "NH": 33,
            "NJ": 34,
            "NM": 35,
            "NY": 36,
            "NC": 37,
            "ND": 38,
            "OH": 39,
            "OK": 40,
            "OR": 41,
            "PA": 42,
            "RI": 44,
            "SC": 45,
            "SD": 46,
            "TN": 47,
            "TX": 48,
            "UT": 49,
            "VT": 50,
            "VA": 51,
            "WA": 53,
            "WV": 54,
            "WI": 55,
            "WY": 56,
            "DC": 11,
            "AS": 60,
            "GU": 66,
            "MP": 69,
            "PR": 72,
            "VI": 78,
        }
        return state_fips.get(state_name, 0)

    def _format_value(self, value: Any) -> Any:
        """Format values for YAML output."""
        if isinstance(value, (float, np.float32, np.float64)):
            return 0 if value == 0 else round(float(value), 2)
        return value

    def generate_yaml(
        self,
        household_data: Dict[str, Any],
        name: Optional[str] = None,
        pe_outputs: Any = None,
    ) -> List[Dict[str, Any]]:
        """Generate YAML test data structure."""
        year = self._get_year(household_data)
        year_str = str(year)
        state_name = household_data["households"]["your household"]["state_name"][
            year_str
        ]
        old_to_new_ids = self._map_person_ids(household_data["people"])
        members = [
            old_to_new_ids[m]
            for m in household_data["tax_units"]["your tax unit"]["members"]
        ]

        # Create the configuration
        config = {
            "name": name or f"Tax unit ({year})",
            "absolute_error_margin": 2,
            "period": year,
            "input": {
                "people": {},
                "tax_units": {
                    "tax_unit": {
                        "members": members,
                        "premium_tax_credit": 0,
                        "local_income_tax": 0,
                        "state_sales_tax": 0,
                    }
                },
                "spm_units": {"spm_unit": {"members": members, "snap": 0, "tanf": 0}},
                "households": {
                    "household": {
                        "members": members,
                        "state_fips": self._get_state_fips(state_name),
                    }
                },
            },
            "output": {},
        }

        # Add output values
        for item in pe_outputs:
            variable_name = item["variable"]
            # Only include state income tax variables (e.g., ca_income_tax, ny_income_tax, etc.)
            # Exclude federal income_tax and net_investment_income_tax
            if (variable_name.endswith("_income_tax") and 
                variable_name != "income_tax" and 
                variable_name != "net_investment_income_tax"):
                config["output"][variable_name] = self._format_value(item["value"])

        # Add person data
        for old_id, person_data in household_data["people"].items():
            new_id = old_to_new_ids[old_id]
            
            # Start with required fields
            person_output = {
                "age": person_data["age"].get(year_str, 0),
                "employment_income": person_data["employment_income"].get(year_str, 0),
            }
            
            # Add optional fields only if they have non-zero values
            optional_fields = [
                "ssi",
                "wic", 
                "deductible_mortgage_interest",
                "self_employment_income",
                "unemployment_compensation",
                "social_security",
                "taxable_private_pension_income",
                "qualified_dividend_income",
                "long_term_capital_gains",
                "short_term_capital_gains",
                "rental_income",
                "partnership_s_corp_income",
                "qualified_business_income",
                "w2_wages_from_qualified_business",
                "business_is_sstb",
                "business_is_qualified",
                "rent",
                "taxable_interest_income",
            ]
            
            for field in optional_fields:
                if field in person_data:
                    value = person_data[field].get(year_str, 0)
                    if value != 0:  # Only include non-zero values
                        person_output[field] = value
            
            config["input"]["people"][new_id] = person_output

        # Add tax unit level fields only if they have non-zero values
        tax_unit = config["input"]["tax_units"]["tax_unit"]
        
        # Map childcare to tax_unit_childcare_expenses
        if "tax_unit_childcare_expenses" in household_data.get("tax_units", {}).get("your tax unit", {}):
            childcare_value = household_data["tax_units"]["your tax unit"]["tax_unit_childcare_expenses"].get(year_str, 0)
            if childcare_value != 0:
                tax_unit["tax_unit_childcare_expenses"] = childcare_value
            else:
                # Remove the default 0 value if childcare is 0
                tax_unit.pop("tax_unit_childcare_expenses", None)
        else:
            # Remove the default 0 value if childcare field doesn't exist
            tax_unit.pop("tax_unit_childcare_expenses", None)

        # Add use tax if applicable
        state_lower = state_name.lower()
        if any(
            f"{state_lower}_use_tax" in key
            for key in household_data["tax_units"].keys()
        ):
            config["input"]["tax_units"]["tax_unit"][f"{state_lower}_use_tax"] = 0

        return [config]


def generate_pe_tests_yaml(household, outputs, file_name, logs):
    """
    Generate PolicyEngine test YAML files.

    Args:
        household (dict): PolicyEngine household situation data
        outputs (list): List of dictionaries with 'variable' and 'value' keys
        file_name (str): Name of the output YAML file
        logs (bool): Whether to generate the YAML file
    """
    if logs:
        generator = PETestsYAMLGenerator()
        yaml_data = generator.generate_yaml(
            household_data=household, name=file_name, pe_outputs=outputs
        )

        # Use PyYAML's built-in dumper with custom formatting
        class FlowStyleDumper(yaml.SafeDumper):
            def represent_sequence(self, tag, sequence, flow_style=None):
                if any(
                    isinstance(item, str) and item.startswith("person")
                    for item in sequence
                ):
                    flow_style = True
                return super().represent_sequence(tag, sequence, flow_style)

            def ignore_aliases(self, data):
                return True

        with open(file_name, "w") as f:
            yaml.dump(
                yaml_data,
                f,
                Dumper=FlowStyleDumper,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
            )
