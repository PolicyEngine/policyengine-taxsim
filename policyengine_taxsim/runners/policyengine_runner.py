import sys

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
from policyengine_taxsim.core.state_output_resolver import (
    calculate_output_adapter,
    calculate_state_mapped_output,
    get_state_specific_variable_name,
    has_state_variable_mapping,
    is_output_adapter,
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
                if has_state_variable_mapping(mapping):
                    continue

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

    # Household aggregate inputs allocated evenly between spouses for MFJ.
    _SPLITTABLE_VARIABLES = frozenset(
        {
            "taxable_interest_income",
            "qualified_dividend_income",
            "long_term_capital_gains",
            "partnership_s_corp_income",
            "short_term_capital_gains",
        }
    )

    # Pension and Social Security income are split between spouses only
    # when both meet the state-level age threshold (55, the lowest common
    # threshold across states such as CO whose pension subtraction
    # qualifies filers 55+). In mixed-age households the income stays
    # with the older spouse so age-based state exclusions aren't lost on
    # the younger spouse's incorrectly-allocated share. Higher-threshold
    # states (DE 60, GA 62, MD 65) are unaffected: 55-59 splits don't
    # create false exclusions because the filers fail those states' age
    # gates anyway.
    _AGE_GATED_FIELDS = frozenset(
        {"taxable_private_pension_income", "social_security_retirement"}
    )
    _AGE_GATED_SPLIT_AGE = 55

    @staticmethod
    def _make_primary_split(source_field):
        """Return a callable yielding the primary share of a household input."""

        def accessor(row):
            value = float(row.get(source_field, 0))
            return value / 2 if int(row.get("mstat", 1)) == 2 else value

        return accessor

    @staticmethod
    def _make_spouse_split(source_field):
        """Return a callable yielding the spouse share of a household input."""

        def accessor(row):
            value = float(row.get(source_field, 0))
            return value / 2 if int(row.get("mstat", 1)) == 2 else 0.0

        return accessor

    @classmethod
    def _make_age_gated_primary(cls, source_field):
        """Allocate age-gated income (pension, gssi) to the primary filer's
        share. The income is split 50/50 whenever both spouses fall on the
        same side of the elderly-eligibility line (both qualify OR both do
        not); only in mixed-age couples is it assigned entirely to the older
        spouse, so age-based state exclusions reach the qualifying filer.
        See taxsim #774 (pensions) and #924 (gssi) for the mixed-age ->
        older rule, and #965 (KY) / #966 (OK) confirming both-young couples
        must still split 50/50 (TAXSIM does, and per-person exclusions like
        KY/OK are age-independent)."""

        def accessor(row):
            value = float(row.get(source_field, 0))
            if int(row.get("mstat", 1)) != 2:
                return value
            page = int(row.get("page", 0))
            sage = int(row.get("sage", 0))
            primary_eligible = page >= cls._AGE_GATED_SPLIT_AGE
            spouse_eligible = sage >= cls._AGE_GATED_SPLIT_AGE
            if primary_eligible == spouse_eligible:
                return value / 2
            primary_is_older_or_equal = page >= sage
            return value if primary_is_older_or_equal else 0.0

        return accessor

    @classmethod
    def _make_age_gated_spouse(cls, source_field):
        """Spouse's share of age-gated income. Mirror of `_make_age_gated_primary`:
        50/50 when both spouses are on the same side of the elderly-eligibility
        line; in mixed-age couples the full amount goes to the spouse only when
        the spouse is strictly older than the primary."""

        def accessor(row):
            value = float(row.get(source_field, 0))
            if int(row.get("mstat", 1)) != 2:
                return 0.0
            page = int(row.get("page", 0))
            sage = int(row.get("sage", 0))
            primary_eligible = page >= cls._AGE_GATED_SPLIT_AGE
            spouse_eligible = sage >= cls._AGE_GATED_SPLIT_AGE
            if primary_eligible == spouse_eligible:
                return value / 2
            spouse_is_strictly_older = sage > page
            return value if spouse_is_strictly_older else 0.0

        return accessor

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
                        elif pe_var in self._AGE_GATED_FIELDS:
                            # Pension and Social Security require the
                            # age-aware split (both spouses must be 60+
                            # to share, otherwise it stays with the primary
                            # filer so age-based exclusions aren't lost).
                            variable_mapping[pe_var] = {
                                "primary": self._make_age_gated_primary(taxsim_var),
                                "spouse": self._make_age_gated_spouse(taxsim_var),
                                "dependent": 0.0,
                                "default": 0.0,
                            }
                        elif pe_var in self._SPLITTABLE_VARIABLES:
                            # Household aggregate: allocate evenly between
                            # spouses for MFJ, otherwise keep on primary.
                            variable_mapping[pe_var] = {
                                "primary": self._make_primary_split(taxsim_var),
                                "spouse": self._make_spouse_split(taxsim_var),
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
                    dep_num = (
                        dep_position - np.where(dep_has_spouse, 2, 1) + 1
                    )  # 1-indexed

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
                if (
                    isinstance(primary_source, str)
                    and primary_source in year_data.columns
                ):
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
                if (
                    isinstance(spouse_source, str)
                    and spouse_source in year_data.columns
                ):
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
                    dep_counter = np.where(
                        count_series > 0, dep_counter + 1, dep_counter
                    )
                    count_series = np.where(
                        count_series > 0, count_series - 1, count_series
                    )

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
        print("Setting defaults for TAXSIM records...", file=sys.stderr)
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
        print("Processing years for dataset generation...", file=sys.stderr)
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
            data["snap"][year_int] = np.zeros(
                n_year_records
            )  # Set SNAP to 0 to match TAXSIM (which doesn't model SNAP)
            data["tanf"][year_int] = np.zeros(
                n_year_records
            )  # Set TANF to 0 to match TAXSIM (which doesn't model TANF)
            data["free_school_meals"][year_int] = np.zeros(
                n_year_records
            )  # Set free school meals to 0 to match TAXSIM (which doesn't model free school meals)
            data["reduced_price_school_meals"][year_int] = np.zeros(
                n_year_records
            )  # Set reduced price school meals to 0 to match TAXSIM (which doesn't model reduced price school meals)

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
        self,
        input_df: pd.DataFrame,
        logs: bool = False,
        disable_salt: bool = False,
        assume_w2_wages: bool = False,
    ):
        super().__init__(input_df)
        self.logs = logs
        self.disable_salt = disable_salt
        self.assume_w2_wages = assume_w2_wages
        # Per-row state_and_local_sales_or_income_tax override (Pass B of
        # three-pass --disable-salt). Maps taxsimid -> dollar value.
        self._state_tax_override = None
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

    CHUNK_SIZE = 10_000

    def _run_chunk(self, chunk_df: pd.DataFrame) -> pd.DataFrame:
        """
        Run PolicyEngine Microsimulation on a single chunk of records.
        Each chunk must contain only one year.

        Returns:
            DataFrame with TAXSIM-formatted output variables
        """
        dataset = TaxsimMicrosimDataset(chunk_df)

        try:
            dataset.generate()
            sim = Microsimulation(dataset=dataset)

            # Resolve the state_and_local_sales_or_income_tax override for
            # this chunk. Possible sources, in priority order:
            #   1. self._state_tax_override (Pass B of three-pass: per-row
            #      values produced by Pass A, keyed by taxsimid)
            #   2. self.disable_salt (zero out for state-only computation)
            salt_override = None
            if self._state_tax_override is not None:
                ids = chunk_df["taxsimid"].astype(float).astype(int).values
                # Look each id up in the override map; fall back to 0 if
                # the id is unexpectedly missing.
                salt_override = np.array(
                    [self._state_tax_override.get(int(i), 0.0) for i in ids],
                    dtype=float,
                )
            elif self.disable_salt:
                salt_override = np.zeros(len(chunk_df), dtype=float)

            if salt_override is not None:
                years = sorted(set(chunk_df["year"].unique()))
                for year in years:
                    year_mask = chunk_df["year"] == year
                    year_values = salt_override[year_mask.values]
                    sim.set_input(
                        variable_name="state_and_local_sales_or_income_tax",
                        value=year_values,
                        period=str(
                            int(year)
                            if isinstance(year, (float, np.floating))
                            else year
                        ),
                    )

            if self.assume_w2_wages:
                n_persons = sim.get_variable_population(
                    "w2_wages_from_qualified_business"
                ).count
                years = sorted(set(chunk_df["year"].unique()))
                for year in years:
                    sim.set_input(
                        variable_name="w2_wages_from_qualified_business",
                        value=np.full(n_persons, 1e9),
                        period=str(
                            int(year)
                            if isinstance(year, (float, np.floating))
                            else year
                        ),
                    )

            # QBID gate on rental_income (TAXSIM `otherprop`): TAXSIM only
            # triggers § 199A QBID via the explicit `pbusinc` input and never
            # treats `otherprop` (Schedule E passive rents/royalties) as
            # qualified. PE-US's `rental_income_would_be_qualified` defaults
            # to True, which would generate a 20% QBID on emulator-routed
            # rental income that TAXSIM does not produce. § 199A(c)(3)(A)
            # requires the activity to rise to a § 162 trade or business;
            # passive individual rentals generally do not qualify absent the
            # § 1.199A-1(b)(14) safe harbor, which TAXSIM input never
            # signals. We force the gate off for the whole chunk: every
            # rental_income value in PE here originated as `otherprop` from
            # TAXSIM, so the override has no side effect on non-emulated
            # rental income.
            if "otherprop" in chunk_df.columns and (chunk_df["otherprop"] != 0).any():
                n_persons = sim.get_variable_population(
                    "rental_income_would_be_qualified"
                ).count
                years = sorted(set(chunk_df["year"].unique()))
                for year in years:
                    sim.set_input(
                        variable_name="rental_income_would_be_qualified",
                        value=np.zeros(n_persons, dtype=bool),
                        period=str(
                            int(year)
                            if isinstance(year, (float, np.floating))
                            else year
                        ),
                    )

            # MN Renter's Credit: PE-US gates the credit on a Certificate
            # of Rent Paid (CRP) input variable that defaults to False. Per
            # Minn. Stat. § 290.0693, the credit is allowed for renters who
            # paid rent and meet income criteria; subd. 4 places the CRP
            # issuance obligation on the landlord (not the renter), and
            # subd. 9 accepts proof "including but not limited to" the CRP.
            # TAXSIM input never carries CRP info, so we assume any MN
            # tax unit with rent > 0 has the supporting documentation.
            if "rentpaid" in chunk_df.columns and "state" in chunk_df.columns:
                mn_mask = (chunk_df["state"] == 24) & (chunk_df["rentpaid"] > 0)
                if mn_mask.any():
                    years = sorted(set(chunk_df["year"].unique()))
                    for year in years:
                        year_mask = (chunk_df["year"] == year) & mn_mask
                        if year_mask.any():
                            # qualifying_crp is on TaxUnit; vector aligns
                            # with the chunk's tax-unit order, one row per
                            # tax unit.
                            sim.set_input(
                                variable_name="mn_renters_credit_qualifying_crp",
                                value=mn_mask[chunk_df["year"] == year].values,
                                period=str(
                                    int(year)
                                    if isinstance(year, (float, np.floating))
                                    else year
                                ),
                            )

            return self._extract_vectorized_results(sim, chunk_df)

        finally:
            dataset.cleanup()

    # Columns whose semantics belong to the state-side of PE-US. When
    # --disable-salt is set, we run PE twice: a full-SALT pass for the
    # federal side, and a SALT-disabled pass for these state columns.
    # That preserves the original intent of --disable-salt (matching
    # TAXSIM's missing state↔federal SALT iteration) without polluting
    # federal Schedule A on PE's side.
    _STATE_OUTPUT_COLUMNS = frozenset(
        {
            "siitax",
            "srate",
            "v32",
            "v33",
            "v34",
            "v35",
            "v36",
            "v37",
            "v38",
            "v39",
            "v40",
            "v41",
            "v42",
            "v43",
            "v44",
            "staxbc",
            "srebate",
            "senergy",
            "sctc",
            "sptcr",
            "samt",
        }
    )

    def _run_once(self, show_progress: bool, on_progress) -> pd.DataFrame:
        """Single PE pass with the current self.disable_salt setting."""
        if show_progress:
            print(
                f"Running PolicyEngine Microsimulation on {len(self.input_df)} records",
                file=sys.stderr,
            )

        # Ensure years are integers to handle decimal values like 2021.0
        self.input_df["year"] = self.input_df["year"].apply(lambda x: int(float(x)))

        frames = []
        years = sorted(self.input_df["year"].unique())
        total_chunks = sum(
            (len(self.input_df[self.input_df["year"] == y]) + self.CHUNK_SIZE - 1)
            // self.CHUNK_SIZE
            for y in years
        )
        total_rows = len(self.input_df)
        chunks_done = 0
        rows_done = 0

        with tqdm(
            total=total_chunks,
            desc="Processing chunks",
            disable=not show_progress,
        ) as pbar:
            for year in years:
                year_df = self.input_df[self.input_df["year"] == year].copy()
                for start in range(0, len(year_df), self.CHUNK_SIZE):
                    chunk_df = year_df.iloc[start : start + self.CHUNK_SIZE].copy()
                    frames.append(self._run_chunk(chunk_df))
                    chunks_done += 1
                    rows_done += len(chunk_df)
                    pbar.update(1)
                    if on_progress:
                        on_progress(chunks_done, total_chunks, rows_done, total_rows)

        results_df = pd.concat(frames, ignore_index=True)
        if show_progress:
            print("PolicyEngine Microsimulation completed", file=sys.stderr)
        return results_df

    def run(self, show_progress: bool = True, on_progress=None) -> pd.DataFrame:
        """
        Run PolicyEngine Microsimulation on all records.

        When ``disable_salt`` is set, runs a single SALT-disabled pass:
        ``state_and_local_sales_or_income_tax`` is zeroed for both the state
        and federal computation, so PE's federal Schedule A excludes state
        income/sales tax (property tax via ``real_estate_taxes`` still flows
        through). This matches TAXSIM-35, which deducts mortgage interest and
        property tax federally but NOT state income tax — verified against the
        ``taxsimtest`` binary across states/years (e.g. NY single $84K + $37K
        mortgage → federal itemized $37K, state tax not deducted).

        A previous three-pass re-introduced the computed state tax as fixed
        federal SALT, which overshot TAXSIM by the full state-tax amount on
        every itemizing record (see taxsim #971; ~$1,185 mean federal mismatch
        on a 60-record itemizing sample, 0/60 within $15). Excluding the state
        income tax brings PE back onto TAXSIM.

        Without ``disable_salt``, runs a single PE pass with PE-US's native
        (iterative, statutorily-correct) SALT handling.
        """
        return self._run_once(show_progress, on_progress)

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
            return np.array(sim.map_result(values, "person", "tax_unit", how="sum"))
        elif entity_key != "tax_unit":
            # For household/spm_unit etc., project to person then sum to tax_unit
            return np.array(sim.map_result(values, entity_key, "tax_unit"))
        return values

    def _compute_marginal_rates(self, sim, year_str, year_data):
        """Compute TAXSIM-compatible marginal tax rates via wage perturbation.

        Matches TAXSIM-35 methodology:
        - Perturbs employment_income (wages) only, not self-employment
        - Splits perturbation between primary and spouse proportionally
          to their share of total wages (weighted average earnings)
        - Uses $0.01 delta to match TAXSIM batch mode
        - Returns rates as percentages (22.0 for 22%)

        Returns:
            dict with 'frate', 'srate' arrays at tax_unit level
        """
        delta = (
            100.0  # $100: large enough for float32 precision, small for bracket safety
        )
        # Get base tax values from the main simulation.
        # frate must match fiitax definition. NBER TAXSIM-35
        # (`taxsimtest`) reports fiitax as income_tax only —
        # Additional Medicare Tax (Form 8959) flows out in the
        # separate `addmed` column per Form 1040 Line 23 /
        # Schedule 2 Line 11. Mirror that here so the marginal rate
        # doesn't pick up the 0.9% AddMed step above threshold.
        base_federal = self._calc_tax_unit(sim, "income_tax", year_str)
        base_state = self._calc_tax_unit(sim, "state_income_tax", year_str)

        # Get current employment_income at person level
        emp_income = np.array(sim.calculate("employment_income", period=year_str))

        # Compute proportional wage split per person
        # Map person-level income to tax_unit totals, then compute share
        tu_total_wages = np.array(
            sim.map_result(emp_income, "person", "tax_unit", how="sum")
        )
        # Expand tax_unit totals back to person level
        person_tu_id = np.array(sim.populations["tax_unit"].members_entity_id)
        tu_total_expanded = tu_total_wages[person_tu_id]

        # Each person's share of total wages (0.5/0.5 if both zero)
        with np.errstate(divide="ignore", invalid="ignore"):
            wage_share = np.where(
                tu_total_expanded > 0,
                emp_income / tu_total_expanded,
                0.0,
            )
        # For zero-wage households, split 50/50 between head and spouse
        is_head = np.array(sim.calculate("is_tax_unit_head", period=year_str))
        is_spouse = np.array(sim.calculate("is_tax_unit_spouse", period=year_str))
        zero_wage_mask = tu_total_expanded == 0
        wage_share = np.where(zero_wage_mask & is_head, 0.5, wage_share)
        wage_share = np.where(zero_wage_mask & is_spouse, 0.5, wage_share)

        # Create perturbation: delta * wage_share for each person
        perturbation = delta * wage_share

        # Create branch simulation with perturbed wages
        branch = sim.get_branch("mtr_wage_perturbation")

        # Clear cached values for variables that depend on employment_income
        for variable in sim.tax_benefit_system.variables:
            if variable not in sim.input_variables or variable == "employment_income":
                branch.delete_arrays(variable)

        # Set perturbed employment income
        branch.set_input("employment_income", year_str, emp_income + perturbation)

        # Compute perturbed tax values (match base_federal: no AddMed)
        new_federal = self._calc_tax_unit(branch, "income_tax", year_str)
        new_state = self._calc_tax_unit(branch, "state_income_tax", year_str)
        # Compute rates as percentages: 100 * (new - base) / delta
        frate = 100.0 * (new_federal - base_federal) / delta
        srate = 100.0 * (new_state - base_state) / delta

        # Clean up branch
        del sim.branches["mtr_wage_perturbation"]

        return {
            "frate": np.round(frate, 4),
            "srate": np.round(srate, 4),
        }

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
                has_state = pe_var.startswith("state_") or any(
                    v.startswith("state_") for v in variables_list
                )

                if pe_var == "na_pe":
                    # na_pe variables get 0
                    columns[taxsim_var] = np.zeros(n)
                    continue

                if pe_var == "marginal_rate_computed":
                    # Marginal rates are computed specially after this loop
                    continue

                try:
                    if is_output_adapter(pe_var):
                        columns[taxsim_var] = np.round(
                            calculate_output_adapter(
                                mapping,
                                state_codes,
                                lambda variable: self._calc_tax_unit(
                                    sim, variable, year_str
                                ),
                                sim.tax_benefit_system.parameters(year_str),
                            ),
                            2,
                        )
                        continue

                    if has_state_variable_mapping(mapping):
                        columns[taxsim_var] = np.round(
                            calculate_state_mapped_output(
                                mapping,
                                state_codes,
                                lambda variable: self._calc_tax_unit(
                                    sim, variable, year_str
                                ),
                                sim.tax_benefit_system.parameters(year_str),
                            ),
                            2,
                        )
                        continue

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
                                sim.tax_benefit_system.variables.get(v) is not None
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
                                        resolved = get_state_specific_variable_name(
                                            var_template, st
                                        )
                                        if self._is_year_restricted_variable(
                                            resolved, year_int
                                        ):
                                            continue
                                        try:
                                            arr = self._calc_tax_unit(
                                                sim, resolved, year_str
                                            )
                                            var_sum += arr
                                        except Exception as e:
                                            if "does not exist" in str(
                                                e
                                            ) or "was not found" in str(e):
                                                if self.logs:
                                                    print(
                                                        f"Variable {resolved} not implemented, setting to 0"
                                                    )
                                            else:
                                                raise
                                    result_array[state_mask] = var_sum[state_mask]
                                else:
                                    resolved = get_state_specific_variable_name(
                                        pe_var, st
                                    )
                                    if self._is_year_restricted_variable(
                                        resolved, year_int
                                    ):
                                        continue
                                    try:
                                        arr = self._calc_tax_unit(
                                            sim, resolved, year_str
                                        )
                                        result_array[state_mask] = arr[state_mask]
                                    except Exception as e:
                                        if "does not exist" in str(
                                            e
                                        ) or "was not found" in str(e):
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

            # fiitax = income_tax only. NBER TAXSIM-35 (`taxsimtest`)
            # reports the Additional Medicare Tax (Form 8959,
            # IRC § 3101(b)(2) / § 1401(b)(2)) separately in the
            # `addmed` column rather than rolling it into fiitax —
            # matching Form 1040 Line 23 / Schedule 2 Line 11.
            # PE's `income_tax` (which already includes NIIT via
            # `income_tax_before_refundable_credits`) is the correct
            # match. AddMed continues to flow through the `v44`
            # output column (employee_medicare_tax + additional_medicare_tax).
            if "fiitax" not in columns:
                columns["fiitax"] = np.round(
                    self._calc_tax_unit(sim, "income_tax", year_str), 2
                )

            # Apply v22 CTC split: TAXSIM v22 reports only the
            # non-refundable CTC (capped at tax liability) for years
            # where the CTC is not fully refundable. For fully-refundable
            # years (e.g. 2021 ARPA), v22 reports the total CTC.
            if "v22" in columns:
                p = sim.tax_benefit_system.parameters(year_str)
                if not p.gov.irs.credits.ctc.refundable.fully_refundable:
                    ctc_arr = self._calc_tax_unit(sim, "ctc", year_str)
                    limiting_tax = self._calc_tax_unit(
                        sim, "ctc_limiting_tax_liability", year_str
                    )
                    columns["v22"] = np.round(np.minimum(ctc_arr, limiting_tax), 2)

            # Compute marginal rates if any idtl level requests them
            mtr_vars = {"frate", "srate"}
            needs_mtr = any(v in vars_to_compute for v in mtr_vars)
            if needs_mtr:
                try:
                    mtr_results = self._compute_marginal_rates(sim, year_str, year_data)
                    for mtr_var in mtr_vars:
                        if mtr_var in vars_to_compute:
                            columns[mtr_var] = mtr_results[mtr_var]
                except Exception as e:
                    if self.logs:
                        print(f"Warning: marginal rate computation failed: {e}")
                    for mtr_var in mtr_vars:
                        if mtr_var in vars_to_compute:
                            columns[mtr_var] = np.zeros(n)

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
