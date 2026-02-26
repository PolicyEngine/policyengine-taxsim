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
    convert_taxsim32_dependents,
)
from policyengine_taxsim.core.input_mapper import (
    set_taxsim_defaults,
    get_taxsim_defaults,
)

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
                if pe_var and pe_var not in [
                    "taxsimid",
                    "get_year",
                    "get_state_code",
                    "na_pe",
                ]:
                    pe_variables.add(pe_var)

                # Multiple variables mapping
                variables = mapping.get("variables", [])
                for var in variables:
                    if (
                        var and "state" not in var
                    ):  # Skip state-specific variables for now
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
            "person_id",
            "person_household_id",
            "person_tax_unit_id",
            "person_family_id",
            "person_spm_unit_id",
            "person_marital_unit_id",
            "person_weight",
            "age",
            "household_id",
            "household_weight",
            "state_fips",
            "tax_unit_id",
            "tax_unit_weight",
            "family_id",
            "family_weight",
            "spm_unit_id",
            "spm_unit_weight",
            "marital_unit_id",
            "marital_unit_weight",
        }

        # Essential person-level variables that might not be in mappings
        essential_person_variables = {
            "employment_income",  # Core income variable used directly
            "charitable_cash_donations",  # Used in dataset creation
            "is_tax_unit_head",  # Tax unit role - must be explicit to avoid misclassification
            "is_tax_unit_spouse",  # Tax unit role - must be explicit to avoid misclassification
            "is_tax_unit_dependent",  # Tax unit role - must be explicit to avoid misclassification
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
            "ssi",  # SSI should be 0 to match TAXSIM (which doesn't model SSI)
            "wic",  # WIC should be 0 to match TAXSIM (which doesn't model WIC)
            "snap",  # SNAP should be 0 to match TAXSIM (which doesn't model SNAP)
            "tanf",  # TANF should be 0 to match TAXSIM (which doesn't model TANF)
            "free_school_meals",  # Free school meals should be 0 to match TAXSIM (which doesn't model free school meals)
            "reduced_price_school_meals",  # Reduced price school meals should be 0 to match TAXSIM (which doesn't model reduced price school meals)
            "head_start",  # Head Start should be 0 to match TAXSIM (which doesn't model Head Start)
            "early_head_start",  # Early Head Start should be 0 to match TAXSIM (which doesn't model Early Head Start)
            "commodity_supplemental_food_program",  # Commodity supplemental food program should be 0 to match TAXSIM (which doesn't model this program)
        }

        # Combine all variables
        all_variables = (
            pe_variables
            | entity_variables
            | essential_person_variables
            | problematic_variables
        )

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
            "default": {"primary": 40, "spouse": 40, "dependent": 10},
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
                                "default": 0.0,
                            }
                        else:
                            # No spouse pair - primary gets all, others get 0
                            variable_mapping[pe_var] = {
                                "primary": taxsim_var,
                                "spouse": 0.0,
                                "dependent": 0.0,
                                "default": 0.0,
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
                                "default": 0.0,
                            }
                        elif var1 == paired_vars.get(var2):
                            # Reverse order - var2 is primary, var1 is spouse
                            variable_mapping[pe_var] = {
                                "primary": var2,
                                "spouse": var1,
                                "dependent": 0.0,
                                "default": 0.0,
                            }
                        else:
                            # Not a pair - combine them (like pui + sui)
                            variable_mapping[pe_var] = {
                                "primary": lambda row, vars=taxsim_vars: sum(
                                    float(row.get(v, 0)) for v in vars
                                ),
                                "spouse": 0.0,
                                "dependent": 0.0,
                                "default": 0.0,
                            }

                    else:
                        # Multiple variables - primary gets all, others get 0
                        variable_mapping[pe_var] = {
                            "primary": taxsim_vars[0],  # Use first one for now
                            "spouse": 0.0,
                            "dependent": 0.0,
                            "default": 0.0,
                        }

        # Add employment_income manually since it's not in additional_income_units
        variable_mapping["employment_income"] = {
            "primary": "pwages",
            "spouse": "swages",
            "dependent": 0.0,
            "default": 0.0,
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

    def _process_tax_unit_data_for_year(
        self, year_data: pd.DataFrame, year: int
    ) -> dict:
        """
        Process tax unit level data for a specific year (vectorized).

        Args:
            year_data: DataFrame containing TAXSIM data for one year
            year: The year being processed

        Returns:
            dict: Processed tax unit level data arrays
        """
        tax_unit_mapping = self._get_tax_unit_variable_mapping()

        result = {}
        for pe_var, taxsim_var in tax_unit_mapping.items():
            if taxsim_var in year_data.columns:
                result[pe_var] = year_data[taxsim_var].fillna(0).astype(float).values

        return result

    def _process_person_data_for_year(self, year_data: pd.DataFrame, year: int) -> dict:
        """
        Process person-level data for a specific year (vectorized).

        Expands household-level rows into person-level arrays using
        np.repeat and boolean masks instead of iterrows.
        """
        n = len(year_data)

        # Vectorized household structure
        mstat = year_data["mstat"].values.astype(int)
        depx = year_data["depx"].values.astype(int)
        has_spouse = np.isin(mstat, [2, 6])
        people_per_hh = 1 + has_spouse.astype(int) + depx
        total_people = int(people_per_hh.sum())

        # Entity IDs: each person maps to their household index
        household_ids = np.repeat(np.arange(n), people_per_hh)

        # Person IDs: sequential
        person_ids = np.arange(total_people)

        # Determine person type for each person in the expanded array
        # Build position_in_household: 0-based index within each household
        position_in_hh = np.zeros(total_people, dtype=int)
        offsets = np.cumsum(people_per_hh)
        starts = np.concatenate([[0], offsets[:-1]])
        for i in range(n):
            s, e = starts[i], offsets[i]
            position_in_hh[s:e] = np.arange(e - s)

        # Expand has_spouse to person level
        has_spouse_expanded = np.repeat(has_spouse, people_per_hh)

        is_primary = position_in_hh == 0
        is_spouse = (position_in_hh == 1) & has_spouse_expanded
        is_dependent = ~is_primary & ~is_spouse

        # Get variable mapping
        var_mapping = self._get_taxsim_to_pe_variable_mapping()

        # Filter mapping
        filtered_mapping = {}
        for pe_var, mapping in var_mapping.items():
            if pe_var == "age":
                filtered_mapping[pe_var] = mapping
                continue
            for person_type in ["primary", "spouse"]:
                source = mapping.get(person_type)
                if isinstance(source, str) and source in year_data.columns:
                    filtered_mapping[pe_var] = mapping
                    break
                elif callable(source):
                    filtered_mapping[pe_var] = mapping
                    break

        result = {
            "person_id": person_ids,
            "person_household_id": household_ids,
            "person_tax_unit_id": household_ids,
            "person_family_id": household_ids,
            "person_spm_unit_id": household_ids,
            "person_marital_unit_id": household_ids,
            "is_tax_unit_head": is_primary,
            "is_tax_unit_spouse": is_spouse,
            "is_tax_unit_dependent": is_dependent,
            "person_weight": np.ones(total_people),
        }

        # Process each variable
        for pe_var, mapping in filtered_mapping.items():
            values = np.zeros(total_people, dtype=float)

            if pe_var == "age":
                # Primary ages
                primary_ages = year_data["page"].values.astype(float)
                primary_ages = np.where(primary_ages > 0, primary_ages, 40)
                values[is_primary] = np.repeat(primary_ages, people_per_hh)[is_primary]

                # Spouse ages: use sage if > 0, else use page
                sage_vals = year_data["sage"].values.astype(float)
                spouse_ages = np.where(sage_vals > 0, sage_vals, primary_ages)
                values[is_spouse] = np.repeat(spouse_ages, people_per_hh)[is_spouse]

                # Dependent ages: need to map position → age column
                dep_mask_indices = np.where(is_dependent)[0]
                if len(dep_mask_indices) > 0:
                    # For each dependent, figure out which dep number they are
                    dep_position = position_in_hh[dep_mask_indices]
                    dep_has_spouse = has_spouse_expanded[dep_mask_indices]
                    dep_num = dep_position - np.where(dep_has_spouse, 2, 1) + 1  # 1-indexed

                    dep_hh_idx = household_ids[dep_mask_indices]
                    for dep_slot in range(1, 12):
                        age_col = f"age{dep_slot}"
                        if age_col in year_data.columns:
                            age_vals = year_data[age_col].values.astype(float)
                            slot_mask = dep_num == dep_slot
                            if slot_mask.any():
                                ages = age_vals[dep_hh_idx[slot_mask]]
                                ages = np.where(ages > 0, ages, 10)
                                values[dep_mask_indices[slot_mask]] = ages

                result[pe_var] = values.astype(int)
            else:
                # Standard variable mapping
                primary_source = mapping.get("primary")
                spouse_source = mapping.get("spouse")
                default_val = mapping.get("default", 0.0)

                # Primary values
                if isinstance(primary_source, str) and primary_source in year_data.columns:
                    prim_vals = year_data[primary_source].fillna(0).values.astype(float)
                    values[is_primary] = np.repeat(prim_vals, people_per_hh)[is_primary]
                elif callable(primary_source):
                    # Callable sources need per-row evaluation (rare)
                    prim_vals = np.array(
                        [primary_source(row) for _, row in year_data.iterrows()],
                        dtype=float,
                    )
                    values[is_primary] = np.repeat(prim_vals, people_per_hh)[is_primary]
                elif isinstance(primary_source, (int, float)):
                    values[is_primary] = primary_source

                # Spouse values
                if isinstance(spouse_source, str) and spouse_source in year_data.columns:
                    sp_vals = year_data[spouse_source].fillna(0).values.astype(float)
                    values[is_spouse] = np.repeat(sp_vals, people_per_hh)[is_spouse]
                elif callable(spouse_source):
                    sp_vals = np.array(
                        [spouse_source(row) for _, row in year_data.iterrows()],
                        dtype=float,
                    )
                    values[is_spouse] = np.repeat(sp_vals, people_per_hh)[is_spouse]
                elif isinstance(spouse_source, (int, float)):
                    values[is_spouse] = spouse_source

                # Dependents get default value (already 0 from initialization)
                dep_default = mapping.get("dependent", 0.0)
                if isinstance(dep_default, (int, float)) and dep_default != 0.0:
                    values[is_dependent] = dep_default

                result[pe_var] = values

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

    def _apply_defaults_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply TAXSIM defaults and TAXSIM32 dependent conversion vectorized."""
        # Vectorized set_taxsim_defaults: fill falsy values with defaults
        defaults = {
            "state": 44,
            "depx": 0,
            "mstat": 1,
            "taxsimid": 0,
            "idtl": 0,
            "page": 40,
            "sage": 40,
        }
        for col, default_val in defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default_val)
                df[col] = df[col].where(df[col] != 0, default_val).astype(int)
            else:
                df[col] = default_val

        if "year" in df.columns:
            df["year"] = df["year"].fillna(2021).astype(int)
        else:
            df["year"] = 2021

        # Vectorized TAXSIM32 dependent conversion (dep13/dep17/dep18 → age1..age11)
        has_dep13 = "dep13" in df.columns
        has_dep17 = "dep17" in df.columns
        has_dep18 = "dep18" in df.columns
        has_taxsim32 = has_dep13 or has_dep17 or has_dep18

        # Check if individual age fields already exist
        has_individual_ages = any(
            f"age{i}" in df.columns and df[f"age{i}"].notna().any()
            for i in range(1, 12)
        )

        if has_taxsim32 and not has_individual_ages:
            dep13 = df.get("dep13", pd.Series(0, index=df.index)).fillna(0).astype(int)
            dep17 = df.get("dep17", pd.Series(0, index=df.index)).fillna(0).astype(int)
            dep18 = df.get("dep18", pd.Series(0, index=df.index)).fillna(0).astype(int)
            depx = df["depx"].astype(int)

            # Ensure depx >= dep18
            df["depx"] = np.maximum(depx, dep18)

            num_under_13 = dep13
            num_13_to_16 = dep17 - dep13
            num_17 = dep18 - dep17
            num_18_plus = np.maximum(depx - dep18, 0)

            # Assign ages vectorized: iterate over dependent slots 1-11
            dep_counter = np.ones(len(df), dtype=int)  # starts at 1

            age_cols = {}
            for age_val, count_series in [
                (10, num_under_13),
                (15, num_13_to_16),
                (17, num_17),
                (21, num_18_plus),
            ]:
                for _ in range(count_series.max() if len(count_series) > 0 else 0):
                    for dep_slot in range(1, 12):
                        col = f"age{dep_slot}"
                        if col not in age_cols:
                            age_cols[col] = np.zeros(len(df), dtype=int)
                        mask = (dep_counter == dep_slot) & (count_series > 0)
                        age_cols[col] = np.where(mask, age_val, age_cols[col])
                    dep_counter = np.where(count_series > 0, dep_counter + 1, dep_counter)
                    count_series = np.where(count_series > 0, count_series - 1, count_series)

            for col, vals in age_cols.items():
                if col not in df.columns:
                    df[col] = 0
                df[col] = np.where(df[col] == 0, vals, df[col])

        # Normalize ages: NaN or 0 → 10 for dependent age fields
        for i in range(1, 12):
            col = f"age{i}"
            if col in df.columns:
                df[col] = df[col].fillna(10)
                df[col] = df[col].where(df[col] != 0, 10)

        return df

    def generate(self) -> None:
        """Generate the dataset with all TAXSIM records."""
        n_records = len(self.input_df)

        # Ensure all required columns exist with default values
        self.input_df = self._ensure_required_columns(self.input_df)

        # Set defaults and convert TAXSIM32 format (vectorized)
        print("Setting defaults for TAXSIM records...")
        self.input_df = self._apply_defaults_vectorized(self.input_df)

        # Extract years (assuming all records might have different years)
        # Years should already be converted to integers in the run() method
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
            # Ensure year is an integer for proper period handling
            year_int = int(year) if isinstance(year, (float, np.floating)) else year
            person_data = self._process_person_data_for_year(year_data, year_int)

            # Assign person-level data to dataset
            for var_name, values in person_data.items():
                data[var_name][year_int] = values

            # Process tax unit level data
            tax_unit_data = self._process_tax_unit_data_for_year(year_data, year_int)

            # Assign tax unit level data to dataset
            for var_name, values in tax_unit_data.items():
                data[var_name][year_int] = values

            # Create entity ID arrays for household-level data
            year_household_ids = np.arange(n_year_records)
            year_tax_unit_ids = np.arange(n_year_records)
            year_family_ids = np.arange(n_year_records)
            year_spm_unit_ids = np.arange(n_year_records)
            year_marital_unit_ids = np.arange(n_year_records)

            # Set problematic variables to 0 directly in dataset to prevent circular dependency calculations
            data["co_child_care_subsidies"][year_int] = np.zeros(
                n_year_records
            )  # Prevent Colorado subsidy calculations

            data["il_use_tax"][year_int] = np.zeros(
                n_year_records
            )  # Prevent Illinois use tax calculations
            data["pa_use_tax"][year_int] = np.zeros(
                n_year_records
            )  # Prevent Pennsylvania use tax calculations
            data["ca_use_tax"][year_int] = np.zeros(
                n_year_records
            )  # Prevent California use tax calculations
            data["nc_use_tax"][year_int] = np.zeros(
                n_year_records
            )  # Prevent North Carolina use tax calculations
            data["ok_use_tax"][year_int] = np.zeros(
                n_year_records
            )  # Prevent Oklahoma use tax calculations

            # Set person-level variables that need to be set per person, not per tax unit
            total_people_for_year = len(person_data.get("person_id", []))
            if total_people_for_year > 0:
                data["ak_energy_relief"][year_int] = np.zeros(
                    total_people_for_year
                )  # Prevent Alaska energy relief calculations
                data["ak_permanent_fund_dividend"][year_int] = np.zeros(
                    total_people_for_year
                )  # Prevent Alaska permanent fund dividend calculations
                data["id_grocery_credit_qualified_months"][year_int] = np.full(
                    total_people_for_year, 12
                )  # Set qualified months to 12 for full year eligibility
                data["ssi"][year_int] = np.zeros(
                    total_people_for_year
                )  # Set SSI to 0 to match TAXSIM (which doesn't model SSI)
                data["wic"][year_int] = np.zeros(
                    total_people_for_year
                )  # Set WIC to 0 to match TAXSIM (which doesn't model WIC)
                data["head_start"][year_int] = np.zeros(
                    total_people_for_year
                )  # Set Head Start to 0 to match TAXSIM (which doesn't model Head Start)
                data["early_head_start"][year_int] = np.zeros(
                    total_people_for_year
                )  # Set Early Head Start to 0 to match TAXSIM (which doesn't model Early Head Start)
                data["commodity_supplemental_food_program"][year_int] = np.zeros(
                    total_people_for_year
                )  # Set commodity supplemental food program to 0 to match TAXSIM (which doesn't model this program)

            # Household data
            data["household_id"][year_int] = year_household_ids
            data["household_weight"][year_int] = np.ones(n_year_records)
            # Convert SOI codes to FIPS codes for PolicyEngine
            data["state_fips"][year_int] = np.array(
                [
                    SOI_TO_FIPS_MAP.get(int(float(s)), 6)
                    for s in year_data["state"].values
                ]
            )

            # Tax unit data
            data["tax_unit_id"][year_int] = year_tax_unit_ids
            data["tax_unit_weight"][year_int] = np.ones(n_year_records)

            # No explicit filing status mapping - let PolicyEngine auto-calculate based on:
            # - Household structure (spouse presence from mstat 2/6)
            # - Dependents (depx > 0)
            # - Other factors (separation, widow status, etc.)
            # This should correctly handle SINGLE vs HEAD_OF_HOUSEHOLD vs JOINT vs SEPARATE

            # Family data
            data["family_id"][year_int] = year_family_ids
            data["family_weight"][year_int] = np.ones(n_year_records)

            # SPM unit data
            data["spm_unit_id"][year_int] = year_spm_unit_ids
            data["spm_unit_weight"][year_int] = np.ones(n_year_records)
            data["snap"][year_int] = np.zeros(n_year_records)  # Set SNAP to 0 to match TAXSIM (which doesn't model SNAP)
            data["tanf"][year_int] = np.zeros(n_year_records)  # Set TANF to 0 to match TAXSIM (which doesn't model TANF)
            data["free_school_meals"][year_int] = np.zeros(n_year_records)  # Set free school meals to 0 to match TAXSIM (which doesn't model free school meals)
            data["reduced_price_school_meals"][year_int] = np.zeros(n_year_records)  # Set reduced price school meals to 0 to match TAXSIM (which doesn't model reduced price school meals)

            # Marital unit data
            data["marital_unit_id"][year_int] = year_marital_unit_ids
            data["marital_unit_weight"][year_int] = np.ones(n_year_records)

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

        # Ensure years are integers to handle decimal values like 2021.0
        self.input_df["year"] = self.input_df["year"].apply(lambda x: int(float(x)))

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
                        period=str(
                            int(year)
                            if isinstance(year, (float, np.floating))
                            else year
                        ),
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

        return (
            variable_name in year_restricted_variables
            and year < year_restricted_variables[variable_name]
        )

    def _calc_tax_unit(self, sim, var_name, period):
        """Calculate a variable and ensure result is at tax_unit level.

        Person-level variables are summed to tax_unit via map_result.
        Tax_unit level variables are returned directly.
        """
        var_obj = sim.tax_benefit_system.variables.get(var_name)
        if var_obj is None:
            raise ValueError(f"Variable {var_name} does not exist")
        values = np.array(sim.calculate(var_name, period=period))
        entity_key = var_obj.entity.key
        if entity_key == "person":
            return np.array(
                sim.map_result(values, "person", "tax_unit", how="sum")
            )
        elif entity_key != "tax_unit":
            # For household/spm_unit etc., project to person then sum to tax_unit
            return np.array(
                sim.map_result(values, entity_key, "tax_unit")
            )
        return values

    def _extract_vectorized_results(
        self, sim: Microsimulation, input_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Extract results from Microsimulation and format as TAXSIM output.

        Uses vectorized sim.calculate() calls (one per variable, not per row)
        and builds the output DataFrame from arrays directly.
        """
        input_df = self._ensure_required_columns(input_df)
        pe_to_taxsim = self.mappings["policyengine_to_taxsim"]
        years = sorted(set(input_df["year"].unique()))
        year_frames = []

        for year in tqdm(years, desc="Processing years"):
            year_str = str(year)
            year_int = int(year)
            year_mask = input_df["year"] == year
            year_data = input_df[year_mask]
            n = len(year_data)

            if n == 0:
                continue

            # Pre-compute state codes for all rows in this year (vectorized)
            state_numbers = year_data["state"].values
            state_codes = np.array([get_state_code(s) for s in state_numbers])
            state_initials = np.char.lower(state_codes)
            output_state_numbers = np.array(
                [get_state_number(sc) for sc in state_codes]
            )

            # Start building the result columns
            columns: Dict[str, np.ndarray] = {
                "taxsimid": year_data["taxsimid"].values,
                "year": np.full(n, year_int),
                "state": output_state_numbers,
            }

            # Determine which taxsim vars to compute based on idtl values
            idtl_values = year_data["idtl"].values
            unique_idtls = set(idtl_values)

            # Pre-compute which taxsim vars are needed for any row in this year
            vars_to_compute = {}
            for taxsim_var, mapping in pe_to_taxsim.items():
                if not mapping.get("implemented", False):
                    continue
                if taxsim_var in ["taxsimid", "year", "state"]:
                    continue

                pe_var = mapping.get("variable", "")
                if pe_var in ["taxsimid", "get_year", "get_state_code"]:
                    continue

                # Check if any idtl level in this year needs this variable
                idtl_entries = mapping.get("idtl", [])
                needed_for_idtls = set()
                for entry in idtl_entries:
                    for idtl_val in entry.values():
                        if idtl_val in unique_idtls:
                            needed_for_idtls.add(idtl_val)

                if not needed_for_idtls:
                    continue

                vars_to_compute[taxsim_var] = {
                    "mapping": mapping,
                    "needed_for_idtls": needed_for_idtls,
                }

            # Compute all needed variables vectorized
            for taxsim_var, info in vars_to_compute.items():
                mapping = info["mapping"]
                pe_var = mapping.get("variable", "")
                variables_list = mapping.get("variables", [])
                has_state = "state" in pe_var or any(
                    "state" in v for v in variables_list
                )

                if pe_var == "na_pe":
                    # na_pe variables get 0
                    columns[taxsim_var] = np.zeros(n)
                    continue

                try:
                    if has_state:
                        # Check if unified PE variable exists (e.g., state_agi,
                        # state_eitc). These use defined_for internally so a
                        # single calculate() call returns correct per-state
                        # values without iterating over states.
                        unified_var = (
                            sim.tax_benefit_system.variables.get(pe_var)
                            if pe_var and not variables_list
                            else None
                        )
                        unified_vars_list = (
                            all(
                                sim.tax_benefit_system.variables.get(v)
                                is not None
                                for v in variables_list
                            )
                            if variables_list
                            else False
                        )

                        if unified_var and not variables_list:
                            # Single unified state variable — one call
                            arr = self._calc_tax_unit(sim, pe_var, year_str)
                            columns[taxsim_var] = np.round(arr, 2)

                        elif unified_vars_list:
                            # Multi-variable sum with unified state vars
                            var_sum = np.zeros(n)
                            for var in variables_list:
                                arr = self._calc_tax_unit(sim, var, year_str)
                                var_sum += arr
                            columns[taxsim_var] = np.round(var_sum, 2)

                        else:
                            # Fallback: per-state iteration for vars without
                            # a unified PE equivalent
                            result_array = np.zeros(n)
                            unique_states = np.unique(state_initials)

                            for st in unique_states:
                                state_mask = state_initials == st

                                if variables_list:
                                    var_sum = np.zeros(n)
                                    for var_template in variables_list:
                                        resolved = var_template.replace("state", st)
                                        if self._is_year_restricted_variable(
                                            resolved, year_int
                                        ):
                                            continue
                                        try:
                                            arr = self._calc_tax_unit(sim, resolved, year_str)
                                            var_sum += arr
                                        except Exception as e:
                                            if "does not exist" in str(e):
                                                if self.logs:
                                                    print(
                                                        f"Variable {resolved} not implemented, setting to 0"
                                                    )
                                            else:
                                                raise
                                    result_array[state_mask] = var_sum[state_mask]
                                else:
                                    resolved = pe_var.replace("state", st)
                                    if self._is_year_restricted_variable(
                                        resolved, year_int
                                    ):
                                        continue
                                    try:
                                        arr = self._calc_tax_unit(sim, resolved, year_str)
                                        result_array[state_mask] = arr[state_mask]
                                    except Exception as e:
                                        if "does not exist" in str(e):
                                            if self.logs:
                                                print(
                                                    f"Variable {resolved} not implemented, setting to 0"
                                                )
                                        else:
                                            raise

                            columns[taxsim_var] = np.round(result_array, 2)

                    elif variables_list:
                        # Multi-variable sum (non-state)
                        var_sum = np.zeros(n)
                        for var in variables_list:
                            arr = self._calc_tax_unit(sim, var, year_str)
                            var_sum += arr
                        columns[taxsim_var] = np.round(var_sum, 2)

                    else:
                        # Single non-state variable
                        arr = self._calc_tax_unit(sim, pe_var, year_str)
                        columns[taxsim_var] = np.round(arr, 2)

                except Exception as e:
                    err_msg = str(e)
                    if "does not exist" in err_msg or "was not found" in err_msg:
                        if self.logs:
                            print(
                                f"Variable {pe_var} not available for {taxsim_var}, setting to 0"
                            )
                        columns[taxsim_var] = np.zeros(n)
                    else:
                        raise RuntimeError(
                            f"Error calculating {pe_var} for {taxsim_var}: {e}"
                        ) from e

            # Apply fiitax special calculation (income_tax + additional_medicare_tax)
            if "fiitax" in columns:
                pass  # Already computed above
            else:
                fiitax_arr = self._calc_tax_unit(
                    sim, "income_tax", year_str
                ) + self._calc_tax_unit(
                    sim, "additional_medicare_tax", year_str
                )
                columns["fiitax"] = np.round(fiitax_arr, 2)

            # Apply idtl filtering: mask out columns not requested by each row's idtl
            if len(unique_idtls) > 1 or 0 in unique_idtls:
                for taxsim_var, info in vars_to_compute.items():
                    if taxsim_var in columns:
                        needed_for_idtls = info["needed_for_idtls"]
                        # Zero out values for rows whose idtl doesn't need this var
                        mask = np.zeros(n, dtype=bool)
                        for idtl_val in needed_for_idtls:
                            mask |= idtl_values == idtl_val
                        if not mask.all():
                            columns[taxsim_var] = np.where(
                                mask, columns[taxsim_var], np.nan
                            )

            year_frames.append(pd.DataFrame(columns))

        if not year_frames:
            return pd.DataFrame()

        result_df = pd.concat(year_frames, ignore_index=True)

        # Drop columns that are all NaN (not needed for any row)
        result_df = result_df.dropna(axis=1, how="all")

        return result_df
