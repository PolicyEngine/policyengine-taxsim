import pandas as pd
import numpy as np
import tempfile
from pathlib import Path
from typing import Dict, Any
from tqdm import tqdm
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
            "co_child_care_subsidies",
            "il_use_tax",
            "pa_use_tax",
            "ca_use_tax",
            "nc_use_tax",
            "ok_use_tax",
            "id_grocery_credit_qualified_months",
            "ak_energy_relief",
            "ak_permanent_fund_dividend",
        }
        
        # Combine all variables
        all_variables = pe_variables | entity_variables | essential_person_variables | problematic_variables
        
        # Initialize all variables as empty dictionaries
        data = {}
        for var in all_variables:
            data[var] = {}
                
        return data

    def _get_taxsim_to_pe_variable_mapping(self) -> dict:
        """
        Get TAXSIM to PolicyEngine variable mappings from existing configuration.
        Leverages the variable_mappings.yaml to avoid duplication.
        
        Returns:
            dict: Mapping of PolicyEngine variables to their TAXSIM sources and rules
        """
        mappings = load_variable_mappings()
        
        # Get basic age mapping from defaults
        age_mapping = {
            "primary": "page",
            "spouse": "sage", 
            "dependent": lambda dep_num: f"age{dep_num}",
            "default": {"primary": 40, "spouse": 40, "dependent": 10}
        }
        
        # Extract TAXSIM input definitions to understand primary/spouse pairs
        taxsim_input_def = mappings.get("taxsim_input_definition", [])
        paired_vars = {}  # Maps primary var to spouse var
        
        for item in taxsim_input_def:
            if isinstance(item, dict):
                for var_name, definition in item.items():
                    if isinstance(definition, dict) and "pair" in definition:
                        paired_vars[var_name] = definition["pair"]
        
        # Build variable mapping from additional_income_units
        taxsim_to_pe = mappings.get("taxsim_to_policyengine", {})
        household_situation = taxsim_to_pe.get("household_situation", {})
        additional_income_units = household_situation.get("additional_income_units", [])
        
        variable_mapping = {"age": age_mapping}  # Start with age
        
        # Process additional income units to create mappings
        for item in additional_income_units:
            if isinstance(item, dict):
                for pe_var, taxsim_vars in item.items():
                    if not taxsim_vars:  # Skip empty mappings
                        continue
                        
                    if len(taxsim_vars) == 1:
                        # Single variable - check if it has a spouse pair
                        taxsim_var = taxsim_vars[0]
                        spouse_var = paired_vars.get(taxsim_var)
                        
                        if spouse_var:
                            # Has spouse pair (like pwages/swages)
                            variable_mapping[pe_var] = {
                                "primary": taxsim_var,
                                "spouse": spouse_var,
                                "dependent": 0.0,
                                "default": 0.0
                            }
                        else:
                            # No spouse pair - primary gets all, others get 0
                            variable_mapping[pe_var] = {
                                "primary": taxsim_var,
                                "spouse": 0.0,
                                "dependent": 0.0,
                                "default": 0.0
                            }
                    
                    elif len(taxsim_vars) == 2:
                        # Two variables - check if they're a primary/spouse pair
                        var1, var2 = taxsim_vars
                        if var2 == paired_vars.get(var1):
                            # They're a primary/spouse pair
                            variable_mapping[pe_var] = {
                                "primary": var1,
                                "spouse": var2,
                                "dependent": 0.0,
                                "default": 0.0
                            }
                        elif var1 == paired_vars.get(var2):
                            # Reverse order - var2 is primary, var1 is spouse
                            variable_mapping[pe_var] = {
                                "primary": var2,
                                "spouse": var1,
                                "dependent": 0.0,
                                "default": 0.0
                            }
                        else:
                            # Not a pair - combine them (like pui + sui)
                            variable_mapping[pe_var] = {
                                "primary": lambda row, vars=taxsim_vars: sum(float(row.get(v, 0)) for v in vars),
                                "spouse": 0.0,
                                "dependent": 0.0,
                                "default": 0.0
                            }
                    
                    else:
                        # Multiple variables - primary gets all, others get 0
                        variable_mapping[pe_var] = {
                            "primary": taxsim_vars[0],  # Use first one for now
                            "spouse": 0.0,
                            "dependent": 0.0,
                            "default": 0.0
                        }
        
        # Add employment_income manually since it's not in additional_income_units
        variable_mapping["employment_income"] = {
            "primary": "pwages",
            "spouse": "swages",
            "dependent": 0.0,
            "default": 0.0
        }
        
        return variable_mapping

    def _get_tax_unit_variable_mapping(self) -> dict:
        """
        Get TAXSIM to PolicyEngine variable mappings for tax unit level variables.
        
        Returns:
            dict: Mapping of PolicyEngine tax unit variables to their TAXSIM sources
        """
        mappings = load_variable_mappings()
        taxsim_to_pe = mappings.get("taxsim_to_policyengine", {})
        household_situation = taxsim_to_pe.get("household_situation", {})
        additional_tax_units = household_situation.get("additional_tax_units", [])
        
        tax_unit_mapping = {}
        
        # Process additional tax units to create mappings
        for item in additional_tax_units:
            if isinstance(item, dict):
                for pe_var, taxsim_vars in item.items():
                    if not taxsim_vars:  # Skip empty mappings
                        continue
                    
                    # For tax unit variables, use the first TAXSIM variable as the source
                    # (most tax unit variables map to a single TAXSIM input)
                    if isinstance(taxsim_vars, list) and len(taxsim_vars) > 0:
                        tax_unit_mapping[pe_var] = taxsim_vars[0]
                    elif isinstance(taxsim_vars, str):
                        tax_unit_mapping[pe_var] = taxsim_vars
        
        return tax_unit_mapping

    def _process_tax_unit_data_for_year(self, year_data: pd.DataFrame, year: int) -> dict:
        """
        Process tax unit level data for a specific year.
        
        Args:
            year_data: DataFrame containing TAXSIM data for one year
            year: The year being processed
            
        Returns:
            dict: Processed tax unit level data arrays
        """
        n_year_records = len(year_data)
        
        # Get tax unit variable mapping
        tax_unit_mapping = self._get_tax_unit_variable_mapping()
        
        # Filter mapping to only include variables where source data exists
        filtered_mapping = {}
        for pe_var, taxsim_var in tax_unit_mapping.items():
            if taxsim_var in year_data.columns:
                filtered_mapping[pe_var] = taxsim_var
        
        # Initialize data collectors
        tax_unit_data = {}
        
        # Initialize variable data collectors
        for pe_var in filtered_mapping.keys():
            tax_unit_data[pe_var] = []
        
        # Process each tax unit (one per record in TAXSIM)
        for _, row in tqdm(year_data.iterrows(), total=len(year_data), desc=f"Processing tax units ({year})", leave=False):
            # Process each tax unit variable
            for pe_var, taxsim_var in filtered_mapping.items():
                if taxsim_var in row and pd.notna(row[taxsim_var]):
                    value = float(row[taxsim_var])
                else:
                    value = 0.0
                
                tax_unit_data[pe_var].append(value)
        
        # Convert to numpy arrays
        result = {}
        for var, values in tax_unit_data.items():
            result[var] = np.array(values)
        
        return result

    def _process_person_data_for_year(self, year_data: pd.DataFrame, year: int) -> dict:
        """
        Process person-level data for a specific year using consolidated mapping approach.
        
        Args:
            year_data: DataFrame containing TAXSIM data for one year
            year: The year being processed
            
        Returns:
            dict: Processed person-level data arrays
        """
        n_year_records = len(year_data)
        
        # Calculate household structure
        total_people = 0
        people_per_household = []
        
        for _, row in year_data.iterrows():
            mstat = int(row["mstat"])
            depx = int(row["depx"])
            has_spouse = mstat in [2, 6]
            n_people = 1 + (1 if has_spouse else 0) + depx
            people_per_household.append(n_people)
            total_people += n_people
        
        # Get variable mapping
        var_mapping = self._get_taxsim_to_pe_variable_mapping()
        
        # Filter mapping to only include variables where source data exists
        filtered_mapping = {}
        for pe_var, mapping in var_mapping.items():
            if pe_var == "age":
                # Always include age
                filtered_mapping[pe_var] = mapping
                continue
                
            # Check if any of the source variables exist in the data
            source_exists = False
            for person_type in ["primary", "spouse"]:
                source = mapping.get(person_type)
                if isinstance(source, str) and source in year_data.columns:
                    source_exists = True
                    break
                elif callable(source):
                    # For callable sources, check if the variables they reference exist
                    # This is a bit more complex, but for now assume they exist
                    source_exists = True
                    break
            
            if source_exists:
                filtered_mapping[pe_var] = mapping
        
        # Initialize data collectors
        person_data = {}
        entity_data = {
            "person_id": [],
            "person_household_id": [],
            "person_tax_unit_id": [],
            "person_family_id": [],
            "person_spm_unit_id": [],
            "person_marital_unit_id": []
        }
        
        # Initialize variable data collectors
        for pe_var in filtered_mapping.keys():
            person_data[pe_var] = []
        
        current_person_id = 0
        
        # Process each household
        for household_idx, (_, row) in enumerate(tqdm(year_data.iterrows(), total=len(year_data), desc=f"Processing households ({year})", leave=False)):
            mstat = int(row["mstat"])
            depx = int(row["depx"])
            has_spouse = mstat in [2, 6]
            n_people = people_per_household[household_idx]
            
            # Process each person in the household
            for person_idx in range(n_people):
                # Entity structure data
                for entity_var in entity_data.keys():
                    if entity_var == "person_id":
                        entity_data[entity_var].append(current_person_id)
                    else:
                        entity_data[entity_var].append(household_idx)
                
                # Determine person type
                if person_idx == 0:
                    person_type = "primary"
                elif person_idx == 1 and has_spouse:
                    person_type = "spouse"
                else:
                    person_type = "dependent"
                    dep_num = person_idx - (1 if has_spouse else 0)
                
                # Process each variable
                for pe_var, mapping in filtered_mapping.items():
                    if person_type == "dependent" and pe_var == "age":
                        # Special handling for dependent age
                        age_col = mapping["dependent"](dep_num)
                        value = int(row.get(age_col, mapping["default"]["dependent"]))
                        if value <= 0:
                            value = mapping["default"]["dependent"]
                    elif person_type == "spouse" and pe_var == "age":
                        # Special handling for spouse age
                        value = int(row[mapping["spouse"]]) if row[mapping["spouse"]] > 0 else int(row[mapping["primary"]])
                    else:
                        # Standard mapping
                        source = mapping.get(person_type)
                        if callable(source):
                            value = source(row)
                        elif isinstance(source, str):
                            # Only set if the source column exists in the data
                            if source in row and pd.notna(row[source]):
                                value = float(row[source]) if pe_var != "age" else int(row[source])
                            else:
                                # Skip this variable if source data is not available
                                continue
                        else:
                            value = source  # Direct value (like 0.0)
                    
                    person_data[pe_var].append(value)
                
                current_person_id += 1
        
        # Convert to numpy arrays and combine entity + person data
        result = {}
        for var, values in entity_data.items():
            result[var] = np.array(values)
        for var, values in person_data.items():
            result[var] = np.array(values)
        
        # Add person weight
        result["person_weight"] = np.ones(total_people)
        
        return result

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
        print("Setting defaults for TAXSIM records...")
        for idx, row in tqdm(self.input_df.iterrows(), total=n_records, desc="Processing defaults"):
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
        print("Processing years for dataset generation...")
        for year in tqdm(unique_years, desc="Dataset generation by year"):
            year_mask = self.input_df["year"] == year
            year_data = self.input_df[year_mask].copy()
            n_year_records = len(year_data)

            if n_year_records == 0:
                continue

            # Fill NaN values with defaults
            year_data = year_data.fillna(0)

            # Process person-level data using consolidated approach
            person_data = self._process_person_data_for_year(year_data, year)

            # Assign person-level data to dataset
            for var_name, values in person_data.items():
                data[var_name][year] = values

            # Process tax unit level data
            tax_unit_data = self._process_tax_unit_data_for_year(year_data, year)

            # Assign tax unit level data to dataset
            for var_name, values in tax_unit_data.items():
                data[var_name][year] = values

            # Create entity ID arrays for household-level data
            year_household_ids = np.arange(n_year_records)
            year_tax_unit_ids = np.arange(n_year_records)
            year_family_ids = np.arange(n_year_records)
            year_spm_unit_ids = np.arange(n_year_records)
            year_marital_unit_ids = np.arange(n_year_records)

            # Set problematic variables to 0 directly in dataset to prevent circular dependency calculations
            data["co_child_care_subsidies"][year] = np.zeros(
                n_year_records
            )  # Prevent Colorado subsidy calculations

            data["il_use_tax"][year] = np.zeros(
                n_year_records
            )  # Prevent Illinois use tax calculations
            data["pa_use_tax"][year] = np.zeros(
                n_year_records
            )  # Prevent Pennsylvania use tax calculations
            data["ca_use_tax"][year] = np.zeros(
                n_year_records
            )  # Prevent California use tax calculations
            data["nc_use_tax"][year] = np.zeros(
                n_year_records
            )  # Prevent North Carolina use tax calculations
            data["ok_use_tax"][year] = np.zeros(
                n_year_records
            )  # Prevent Oklahoma use tax calculations
            
            # Set person-level variables that need to be set per person, not per tax unit
            total_people_for_year = len(person_data.get("person_id", []))
            if total_people_for_year > 0:
                data["ak_energy_relief"][year] = np.zeros(
                    total_people_for_year
                )  # Prevent Alaska energy relief calculations
                data["ak_permanent_fund_dividend"][year] = np.zeros(
                    total_people_for_year
                )  # Prevent Alaska permanent fund dividend calculations
                data["id_grocery_credit_qualified_months"][year] = np.full(
                    total_people_for_year, 12
                )  # Set qualified months to 12 for full year eligibility

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
            if show_progress:
                print("Generating PolicyEngine dataset...")
            dataset.generate()

            # Create Microsimulation
            if show_progress:
                print("Creating PolicyEngine microsimulation...")
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


            # Extract results
            if show_progress:
                print("Extracting results from PolicyEngine...")
            results_df = self._extract_vectorized_results(sim, self.input_df)

        finally:
            dataset.cleanup()

        if show_progress:
            print("PolicyEngine Microsimulation completed")

        return results_df

    def _is_year_restricted_variable(self, variable_name: str, year: int) -> bool:
        """
        Check if a variable has year restrictions and should not be computed for the given year.
        
        Args:
            variable_name: Name of the PolicyEngine variable
            year: Tax year
            
        Returns:
            True if the variable should be skipped for this year, False otherwise
        """
        # Dictionary of variables and their minimum effective years
        year_restricted_variables = {
            # Georgia programs starting in 2025
            "ga_ctc": 2025,
            "la_standard_deduction": 2025,
            # Add other state programs as needed
            # Format: "variable_name": minimum_year
        }
        
        return variable_name in year_restricted_variables and year < year_restricted_variables[variable_name]

    def _extract_vectorized_results(
        self, sim: Microsimulation, input_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Extract results from Microsimulation and format as TAXSIM output"""
        results = []

        # Ensure input_df has all required columns
        input_df = self._ensure_required_columns(input_df)

        # Process each unique year
        years = sorted(set(input_df["year"].unique()))

        for year in tqdm(years, desc="Processing years"):
            year_str = str(year)
            year_mask = input_df["year"] == year
            year_data = input_df[year_mask]

            if len(year_data) == 0:
                continue

            # Get results for this year
            try:
                federal_taxes_main = sim.calculate("income_tax", period=year_str)
                medicare = sim.calculate("additional_medicare_tax", period=year_str)
                state_taxes = sim.calculate("state_income_tax", period=year_str)
                federal_taxes = federal_taxes_main + medicare

                # Create results for this year
                for idx, (_, row) in enumerate(tqdm(year_data.iterrows(), total=len(year_data), desc=f"Extracting results ({year})", leave=False)):
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

                        # Check for year-restricted state programs before calculation
                        if self._is_year_restricted_variable(pe_var, year):
                            if self.logs:
                                print(f"Variable {pe_var} not available in {year}, setting to 0")
                            result[taxsim_var] = 0.0
                            continue

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
                            # Only catch specific "variable does not exist" errors for unimplemented state variables
                            # All other errors should bubble up to reveal real problems
                            if "does not exist" in str(e):
                                if self.logs:
                                    print(f"Variable {pe_var} not implemented in PolicyEngine, setting to 0")
                                result[taxsim_var] = 0.0
                            else:
                                # Real error - don't mask it
                                raise RuntimeError(f"Error calculating {pe_var} for {taxsim_var}: {e}") from e

                    results.append(result)

            except Exception as e:
                # Don't mask errors with fallback results - let them bubble up
                raise RuntimeError(f"Error processing year {year}: {e}") from e

        return pd.DataFrame(results)
