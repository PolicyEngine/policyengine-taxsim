import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from typing import Dict, Any
from .base_runner import BaseTaxRunner

# Import core functions needed for microsimulation
from policyengine_taxsim.core.utils import (
        load_variable_mappings,
        SOI_TO_FIPS_MAP,
        get_state_code,
        get_state_number,
        to_roundedup_number,
    )
from policyengine_taxsim.core.input_mapper import set_taxsim_defaults, get_taxsim_defaults

from policyengine_us import Microsimulation
from policyengine_core.data import Dataset


class TaxsimMicrosimDataset(Dataset):
    """Custom dataset for TAXSIM data using PolicyEngine Microsimulation."""

    name = "taxsim_microsim_dataset"
    label = "TAXSIM Microsimulation Dataset"
    data_format = Dataset.TIME_PERIOD_ARRAYS

    def __init__(self, input_df: pd.DataFrame):
        self.input_df = input_df.copy()
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
        self.file_path = Path(self.tmp_file.name)
        super().__init__()

    def _extract_policyengine_variables_from_mappings(self) -> set:
        """
        Extract all PolicyEngine variables from the variable mappings.
        
        Returns:
            set: Set of all PolicyEngine variable names found in mappings
        """
        pe_variables = set()
        
        # Get variable mappings
        mappings = load_variable_mappings()
        
        # Extract from policyengine_to_taxsim mappings
        pe_to_taxsim = mappings.get("policyengine_to_taxsim", {})
        for taxsim_var, mapping in pe_to_taxsim.items():
            if isinstance(mapping, dict):
                # Single variable mapping
                pe_var = mapping.get("variable")
                if pe_var and pe_var not in ["taxsimid", "get_year", "get_state_code", "na_pe"]:
                    pe_variables.add(pe_var)
                
                # Multiple variables mapping
                variables = mapping.get("variables", [])
                for var in variables:
                    if var and "state" not in var:  # Skip state-specific variables for now
                        pe_variables.add(var)
        
        # Extract from taxsim_to_policyengine additional units
        taxsim_to_pe = mappings.get("taxsim_to_policyengine", {})
        household_situation = taxsim_to_pe.get("household_situation", {})
        
        # Additional income units (person-level variables)
        additional_income_units = household_situation.get("additional_income_units", [])
        for item in additional_income_units:
            if isinstance(item, dict):
                for field, values in item.items():
                    pe_variables.add(field)
        
        # Additional tax units (tax-unit-level variables)
        additional_tax_units = household_situation.get("additional_tax_units", [])
        for item in additional_tax_units:
            if isinstance(item, dict):
                for field, values in item.items():
                    if field not in ["state_use_tax"]:  # Skip state-specific variables
                        pe_variables.add(field)
        
        return pe_variables

    def _initialize_dataset_structure(self) -> dict:
        """
        Initialize the dataset structure with all required PolicyEngine variables.
        Uses variable mappings to automatically discover PolicyEngine variables.
        
        Returns:
            dict: Dictionary with all required variables initialized as empty dicts
        """
        # Extract PolicyEngine variables from mappings
        pe_variables = self._extract_policyengine_variables_from_mappings()
        
        # Define required entity structure variables (these are always needed)
        entity_variables = {
            "person_id", "person_household_id", "person_tax_unit_id", 
            "person_family_id", "person_spm_unit_id", "person_marital_unit_id", 
            "person_weight", "age",
            "household_id", "household_weight", "state_fips",
            "tax_unit_id", "tax_unit_weight",
            "family_id", "family_weight",
            "spm_unit_id", "spm_unit_weight",
            "marital_unit_id", "marital_unit_weight"
        }
        
        # Essential person-level variables that might not be in mappings
        essential_person_variables = {
            "employment_income",  # Core income variable used directly
            "charitable_cash_donations",  # Used in dataset creation
        }
        
        # Variables that can cause circular dependencies
        problematic_variables = {
            "co_child_care_subsidies", "state_and_local_sales_or_income_tax"
        }
        
        # Combine all variables
        all_variables = pe_variables | entity_variables | essential_person_variables | problematic_variables
        
        # Initialize all variables as empty dictionaries
        data = {}
        for var in all_variables:
            data[var] = {}
                
        return data

    def _ensure_required_columns(self, df):
        """
        Ensure all required columns exist in the DataFrame with default values.
        Uses the existing column definitions from TaxsimRunner.

        Args:
            df: The DataFrame to check and modify

        Returns:
            DataFrame with all required columns present
        """
        from .taxsim_runner import TaxsimRunner

        # Use the existing column definitions from TaxsimRunner
        all_columns = TaxsimRunner.ALL_COLUMNS

        # Get default values from shared function
        default_values = get_taxsim_defaults(2021)

        # Add missing columns with default values
        for col in all_columns:
            if col not in df.columns:
                # Use specific default if defined, otherwise 0
                default_value = default_values.get(col, 0)
                df[col] = default_value

        return df

    def generate(self) -> None:
        """Generate the dataset with all TAXSIM records."""
        n_records = len(self.input_df)

        # Ensure all required columns exist with default values
        self.input_df = self._ensure_required_columns(self.input_df)

        # Set defaults for all records
        for idx, row in self.input_df.iterrows():
            taxsim_vars = row.to_dict()
            year = int(taxsim_vars.get("year", 2021))
            taxsim_vars = set_taxsim_defaults(taxsim_vars, year)
            for key, value in taxsim_vars.items():
                self.input_df.loc[idx, key] = value

        # Extract years (assuming all records might have different years)
        years = self.input_df["year"].values
        unique_years = sorted(self.input_df["year"].unique())

        # Use SOI to FIPS mapping from core utils

        # Proper approach: Check mstat to determine household structure
        # mstat 2 or 6 = spouse present → create multi-person household
        # mstat 1,3,4,5 = no spouse → single-person household + dependents
        data = self._initialize_dataset_structure()

        # Process each year separately
        for year in unique_years:
            year_mask = self.input_df["year"] == year
            year_data = self.input_df[year_mask].copy()
            n_year_records = len(year_data)

            if n_year_records == 0:
                continue

            # Fill NaN values with defaults
            year_data = year_data.fillna(0)

            # Calculate total people needed based on household structure
            total_people = 0
            people_per_household = []

            for _, row in year_data.iterrows():
                mstat = int(row["mstat"])
                depx = int(row["depx"])

                # Check if spouse is present: mstat 2 (joint) or 6 (separate)
                has_spouse = mstat in [2, 6]

                # Calculate people: 1 primary + (1 spouse if present) + dependents
                n_people = 1 + (1 if has_spouse else 0) + depx
                people_per_household.append(n_people)
                total_people += n_people

            # Create person-level arrays for the entire year
            all_person_ids = []
            all_person_household_ids = []
            all_person_tax_unit_ids = []
            all_person_family_ids = []
            all_person_spm_unit_ids = []
            all_person_marital_unit_ids = []
            all_ages = []
            all_employment_income = []
            all_self_employment_income = []
            all_dividend_income = []
            all_interest_income = []
            all_stcg = []
            all_ltcg = []
            all_pensions = []
            all_gssi = []
            all_ui = []
            all_scorp = []
            all_real_estate_taxes = []
            all_charitable = []

            current_person_id = 0

            # Create people for each household
            for household_idx, (_, row) in enumerate(year_data.iterrows()):
                mstat = int(row["mstat"])
                depx = int(row["depx"])
                has_spouse = mstat in [2, 6]
                n_people = people_per_household[household_idx]

                for person_idx in range(n_people):
                    all_person_ids.append(current_person_id)
                    all_person_household_ids.append(household_idx)
                    all_person_tax_unit_ids.append(household_idx)
                    all_person_family_ids.append(household_idx)
                    all_person_spm_unit_ids.append(household_idx)
                    all_person_marital_unit_ids.append(household_idx)

                    if person_idx == 0:  # Primary taxpayer
                        all_ages.append(int(row["page"]))
                        all_employment_income.append(float(row["pwages"]))
                        all_self_employment_income.append(float(row["psemp"]))
                        # Primary gets all non-wage income
                        all_dividend_income.append(float(row["dividends"]))
                        all_interest_income.append(float(row["intrec"]))
                        all_stcg.append(float(row["stcg"]))
                        all_ltcg.append(float(row["ltcg"]))
                        all_pensions.append(float(row["pensions"]))
                        all_gssi.append(float(row["gssi"]))
                        all_ui.append(float(row["pui"]) + float(row["sui"]))
                        all_scorp.append(float(row["scorp"]))
                        all_real_estate_taxes.append(float(row["proptax"]))
                        all_charitable.append(float(row["otheritem"]))

                    elif person_idx == 1 and has_spouse:  # Spouse
                        spouse_age = (
                            int(row["sage"]) if row["sage"] > 0 else int(row["page"])
                        )
                        all_ages.append(spouse_age)
                        all_employment_income.append(float(row["swages"]))
                        all_self_employment_income.append(float(row["ssemp"]))
                        # Spouse gets zeros for non-wage income (assigned to primary)
                        all_dividend_income.append(0.0)
                        all_interest_income.append(0.0)
                        all_stcg.append(0.0)
                        all_ltcg.append(0.0)
                        all_pensions.append(0.0)
                        all_gssi.append(0.0)
                        all_ui.append(0.0)
                        all_scorp.append(0.0)
                        all_real_estate_taxes.append(0.0)
                        all_charitable.append(0.0)

                    else:  # Dependent
                        dep_num = person_idx - (1 if has_spouse else 0)
                        age_col = f"age{dep_num}"
                        dep_age = (
                            int(row.get(age_col, 10)) if row.get(age_col, 0) > 0 else 10
                        )
                        all_ages.append(dep_age)
                        # Dependents get zeros for all income
                        all_employment_income.append(0.0)
                        all_self_employment_income.append(0.0)
                        all_dividend_income.append(0.0)
                        all_interest_income.append(0.0)
                        all_stcg.append(0.0)
                        all_ltcg.append(0.0)
                        all_pensions.append(0.0)
                        all_gssi.append(0.0)
                        all_ui.append(0.0)
                        all_scorp.append(0.0)
                        all_real_estate_taxes.append(0.0)
                        all_charitable.append(0.0)

                    current_person_id += 1

            # Create entity ID arrays
            year_household_ids = np.arange(n_year_records)
            year_tax_unit_ids = np.arange(n_year_records)
            year_family_ids = np.arange(n_year_records)
            year_spm_unit_ids = np.arange(n_year_records)
            year_marital_unit_ids = np.arange(n_year_records)

            # Set data for this year using our person-level arrays
            data["person_id"][year] = np.array(all_person_ids)
            data["person_household_id"][year] = np.array(all_person_household_ids)
            data["person_tax_unit_id"][year] = np.array(all_person_tax_unit_ids)
            data["person_family_id"][year] = np.array(all_person_family_ids)
            data["person_spm_unit_id"][year] = np.array(all_person_spm_unit_ids)
            data["person_marital_unit_id"][year] = np.array(all_person_marital_unit_ids)
            data["person_weight"][year] = np.ones(total_people)

            # Personal characteristics and income (now properly distributed across people)
            data["age"][year] = np.array(all_ages)
            data["employment_income"][year] = np.array(all_employment_income)
            data["self_employment_income"][year] = np.array(all_self_employment_income)
            data["qualified_dividend_income"][year] = np.array(all_dividend_income)
            data["taxable_interest_income"][year] = np.array(all_interest_income)
            data["short_term_capital_gains"][year] = np.array(all_stcg)
            data["long_term_capital_gains"][year] = np.array(all_ltcg)
            data["taxable_private_pension_income"][year] = np.array(all_pensions)
            data["social_security_retirement"][year] = np.array(all_gssi)
            data["unemployment_compensation"][year] = np.array(all_ui)
            data["partnership_s_corp_income"][year] = np.array(all_scorp)
            data["real_estate_taxes"][year] = np.array(all_real_estate_taxes)
            data["charitable_cash_donations"][year] = np.array(all_charitable)

            # Set problematic variables to 0 directly in dataset to prevent circular dependency calculations
            data["co_child_care_subsidies"][year] = np.zeros(
                n_year_records
            )  # Prevent Colorado subsidy calculations

            # Household data
            data["household_id"][year] = year_household_ids
            data["household_weight"][year] = np.ones(n_year_records)
            # Convert SOI codes to FIPS codes for PolicyEngine
            data["state_fips"][year] = np.array(
                [SOI_TO_FIPS_MAP.get(int(s), 6) for s in year_data["state"].values]
            )

            # Tax unit data
            data["tax_unit_id"][year] = year_tax_unit_ids
            data["tax_unit_weight"][year] = np.ones(n_year_records)

            # No explicit filing status mapping - let PolicyEngine auto-calculate based on:
            # - Household structure (spouse presence from mstat 2/6)
            # - Dependents (depx > 0)
            # - Other factors (separation, widow status, etc.)
            # This should correctly handle SINGLE vs HEAD_OF_HOUSEHOLD vs JOINT vs SEPARATE

            # Family data
            data["family_id"][year] = year_family_ids
            data["family_weight"][year] = np.ones(n_year_records)

            # SPM unit data
            data["spm_unit_id"][year] = year_spm_unit_ids
            data["spm_unit_weight"][year] = np.ones(n_year_records)

            # Marital unit data
            data["marital_unit_id"][year] = year_marital_unit_ids
            data["marital_unit_weight"][year] = np.ones(n_year_records)

        self.save_dataset(data)

    def cleanup(self) -> None:
        """Clean up temporary file."""
        if hasattr(self, "tmp_file"):
            try:
                self.file_path.unlink()
            except Exception:
                pass


class PolicyEngineRunner(BaseTaxRunner):
    """
    High-performance PolicyEngine runner using Microsimulation.

    Processes multiple TAXSIM records simultaneously through PolicyEngine's
    vectorized microsimulation engine. Creates proper household structures
    with multiple people based on marital status and dependents.
    """

    def __init__(
        self, input_df: pd.DataFrame, logs: bool = False, disable_salt: bool = False
    ):
        super().__init__(input_df)
        self.logs = logs
        self.disable_salt = disable_salt
        self.mappings = load_variable_mappings()

    def _ensure_required_columns(self, df):
        """
        Ensure all required columns exist in the DataFrame with default values.
        Uses the existing column definitions from TaxsimRunner.

        Args:
            df: The DataFrame to check and modify

        Returns:
            DataFrame with all required columns present
        """
        from .taxsim_runner import TaxsimRunner

        # Use the existing column definitions from TaxsimRunner
        all_columns = TaxsimRunner.ALL_COLUMNS

        # Get default values from shared function
        default_values = get_taxsim_defaults(2021)

        # Add missing columns with default values
        for col in all_columns:
            if col not in df.columns:
                # Use specific default if defined, otherwise 0
                default_value = default_values.get(col, 0)
                df[col] = default_value

        return df

    def run(self, show_progress: bool = True) -> pd.DataFrame:
        """
        Run PolicyEngine Microsimulation on all records simultaneously

        Returns:
            DataFrame with TAXSIM-formatted output variables
        """
        if show_progress:
            print(
                f"Running PolicyEngine Microsimulation on {len(self.input_df)} records"
            )

        # Create the dataset
        dataset = TaxsimMicrosimDataset(self.input_df)

        try:
            # Generate the dataset
            dataset.generate()

            # Create Microsimulation
            sim = Microsimulation(dataset=dataset)

            # Apply SALT override if needed
            if self.disable_salt:
                years = sorted(set(self.input_df["year"].unique()))
                for year in years:
                    year_mask = self.input_df["year"] == year
                    n_year_records = year_mask.sum()
                    sim.set_input(
                        variable_name="state_and_local_sales_or_income_tax",
                        value=np.zeros(n_year_records),
                        period=str(year),
                    )

            # Disable problematic variables that cause circular dependencies
            years = sorted(set(self.input_df["year"].unique()))
            problematic_vars = [
                "ca_child_care_subsidies",
                "ne_child_care_subsidies",  # State-specific subsidies (co_child_care_subsidies handled in dataset)
            ]

            for var in problematic_vars:
                for year in years:
                    try:
                        # Set to zero for annual period
                        sim.set_input(var, 0.0, period=str(year))
                        # Set to zero for all monthly periods
                    except Exception:
                        # If variable doesn't exist in PolicyEngine, continue
                        pass

            # Extract results
            results_df = self._extract_vectorized_results(sim, self.input_df)

        finally:
            dataset.cleanup()

        if show_progress:
            print("PolicyEngine Microsimulation completed")

        return results_df

    def _extract_vectorized_results(
        self, sim: Microsimulation, input_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Extract results from Microsimulation and format as TAXSIM output"""
        results = []

        # Ensure input_df has all required columns
        input_df = self._ensure_required_columns(input_df)

        # Process each unique year
        years = sorted(set(input_df["year"].unique()))

        for year in years:
            year_str = str(year)
            year_mask = input_df["year"] == year
            year_data = input_df[year_mask]

            if len(year_data) == 0:
                continue

            # Get results for this year
            try:
                federal_taxes = sim.calculate("income_tax", period=year_str)
                state_taxes = sim.calculate("state_income_tax", period=year_str)

                # Create results for this year
                for idx, (_, row) in enumerate(year_data.iterrows()):
                    result = {
                        "taxsimid": row["taxsimid"],
                        "year": year,
                        "state": get_state_number(get_state_code(row["state"])),
                        "fiitax": to_roundedup_number(federal_taxes[idx]),
                        "siitax": to_roundedup_number(state_taxes[idx]),
                    }

                    # Add other variables based on idtl
                    pe_to_taxsim = self.mappings["policyengine_to_taxsim"]
                    output_type = row["idtl"]

                    for taxsim_var, mapping in pe_to_taxsim.items():
                        if not mapping.get("implemented", False):
                            continue

                        if taxsim_var in [
                            "taxsimid",
                            "year",
                            "state",
                            "fiitax",
                            "siitax",
                        ]:
                            continue  # Already handled

                        # Check if this variable should be included based on idtl
                        should_include = any(
                            output_type in entry.values()
                            for entry in mapping.get("idtl", [])
                        )

                        if not should_include:
                            continue

                        # Get PolicyEngine variable name
                        pe_var = mapping.get("variable")
                        if not pe_var or pe_var in [
                            "taxsimid",
                            "get_year",
                            "get_state_code",
                            "na_pe",
                        ]:
                            continue

                        # Handle state-specific variables
                        state_name = get_state_code(row["state"])
                        if "state" in pe_var:
                            pe_var = pe_var.replace("state", state_name.lower())

                        # Calculate value
                        try:
                            if "variables" in mapping and len(mapping["variables"]) > 0:
                                # Sum multiple variables
                                value = 0
                                for var in mapping["variables"]:
                                    if "state" in var:
                                        var = var.replace("state", state_name.lower())
                                    var_values = sim.calculate(var, period=year_str)
                                    value += var_values[idx]
                            else:
                                # Single variable
                                var_values = sim.calculate(pe_var, period=year_str)
                                value = var_values[idx]

                            result[taxsim_var] = to_roundedup_number(value)
                        except Exception as e:
                            # Default to 0 on calculation errors (often state-specific variables not implemented)
                            if self.logs and "does not exist" not in str(e):
                                print(f"Error calculating {pe_var}: {e}")
                            result[taxsim_var] = 0.0

                    results.append(result)

            except Exception as e:
                print(f"Error processing year {year}: {e}")
                # Fall back to basic results for this year
                for _, row in year_data.iterrows():
                    result = {
                        "taxsimid": row["taxsimid"],
                        "year": year,
                        "state": get_state_number(get_state_code(row["state"])),
                        "fiitax": 0.0,
                        "siitax": 0.0,
                    }
                    results.append(result)

        return pd.DataFrame(results)
