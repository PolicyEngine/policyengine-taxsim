import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from ..core.utils import get_state_code
except ImportError:
    from policyengine_taxsim.core.utils import get_state_code


@dataclass
class ComparisonConfig:
    """Configuration for tax comparison"""

    federal_tax_col: str = "fiitax"
    state_tax_col: str = "siitax"
    federal_tolerance: float = 15.0  # $15 absolute tolerance
    state_tolerance: float = 15.0  # $15 absolute tolerance
    id_col: str = "taxsimid"


@dataclass
class MismatchRecord:
    """Record of a tax calculation mismatch"""

    taxsimid: int
    tax_type: str  # "federal" or "state"
    taxsim_value: float
    policyengine_value: float
    difference: float
    state: Optional[int] = None  # For state tax mismatches


class TaxComparator:
    """Compare results between TAXSIM and PolicyEngine"""

    def __init__(
        self,
        taxsim_results: pd.DataFrame,
        policyengine_results: pd.DataFrame,
        config: ComparisonConfig = None,
    ):
        self.taxsim_results = taxsim_results.copy()
        self.policyengine_results = policyengine_results.copy()
        self.config = config or ComparisonConfig()
        self._prepare_data()

    def _prepare_data(self):
        """Prepare data for comparison"""
        # Normalize column names
        self.taxsim_results.columns = self.taxsim_results.columns.str.lower()
        self.policyengine_results.columns = (
            self.policyengine_results.columns.str.lower()
        )

        # Remove any records with NaN taxsimid from TAXSIM results (these are often artifacts)
        if self.config.id_col in self.taxsim_results.columns:
            initial_taxsim_count = len(self.taxsim_results)
            self.taxsim_results = self.taxsim_results.dropna(
                subset=[self.config.id_col]
            )
            removed_count = initial_taxsim_count - len(self.taxsim_results)
            if removed_count > 0:
                print(
                    f"Warning: Removed {removed_count} TAXSIM records with NaN {self.config.id_col}"
                )

        # Sort both DataFrames by taxsimid
        self.taxsim_results = self.taxsim_results.sort_values(
            self.config.id_col
        ).reset_index(drop=True)
        self.policyengine_results = self.policyengine_results.sort_values(
            self.config.id_col
        ).reset_index(drop=True)

        # Handle duplicate taxsimids in TAXSIM results by keeping only the first occurrence
        # This can happen when TAXSIM outputs multiple records per household
        if self.taxsim_results[self.config.id_col].duplicated().any():
            initial_count = len(self.taxsim_results)
            self.taxsim_results = self.taxsim_results.drop_duplicates(
                subset=[self.config.id_col], keep="first"
            ).reset_index(drop=True)
            removed_duplicates = initial_count - len(self.taxsim_results)
            print(
                f"Warning: Removed {removed_duplicates} duplicate TAXSIM records, keeping first occurrence of each {self.config.id_col}"
            )

        # Ensure both datasets contain the same taxsimids
        taxsim_ids = set(self.taxsim_results[self.config.id_col])
        pe_ids = set(self.policyengine_results[self.config.id_col])

        common_ids = taxsim_ids.intersection(pe_ids)
        taxsim_only = taxsim_ids - pe_ids
        pe_only = pe_ids - taxsim_ids

        if taxsim_only:
            print(
                f"Warning: {len(taxsim_only)} {self.config.id_col}s only in TAXSIM results"
            )
        if pe_only:
            print(
                f"Warning: {len(pe_only)} {self.config.id_col}s only in PolicyEngine results"
            )

        # Filter both datasets to only include common IDs
        self.taxsim_results = self.taxsim_results[
            self.taxsim_results[self.config.id_col].isin(common_ids)
        ].reset_index(drop=True)
        self.policyengine_results = self.policyengine_results[
            self.policyengine_results[self.config.id_col].isin(common_ids)
        ].reset_index(drop=True)

        print(f"Comparing {len(common_ids)} records present in both datasets")

        # Convert numeric columns to float
        for df in [self.taxsim_results, self.policyengine_results]:
            numeric_columns = df.select_dtypes(include=["number"]).columns
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    def _compare_tax_column(
        self, col_name: str, tolerance: float, tax_type: str
    ) -> Tuple[np.ndarray, List[MismatchRecord]]:
        """Compare a specific tax column between datasets"""
        mismatches = []

        if (
            col_name not in self.taxsim_results.columns
            or col_name not in self.policyengine_results.columns
        ):
            # Return empty results if column doesn't exist
            return np.array([]), mismatches

        # Compare with tolerance
        matches = np.isclose(
            self.taxsim_results[col_name],
            self.policyengine_results[col_name],
            atol=tolerance,
            equal_nan=True,
        )

        # Collect mismatches
        for i, is_match in enumerate(matches):
            if not is_match:
                taxsim_val = self.taxsim_results.iloc[i][col_name]
                pe_val = self.policyengine_results.iloc[i][col_name]

                mismatch = MismatchRecord(
                    taxsimid=self.taxsim_results.iloc[i][self.config.id_col],
                    tax_type=tax_type,
                    taxsim_value=taxsim_val,
                    policyengine_value=pe_val,
                    difference=taxsim_val - pe_val,
                )

                # Add state info for both federal and state tax mismatches
                if "state" in self.taxsim_results.columns:
                    mismatch.state = self.taxsim_results.iloc[i]["state"]

                mismatches.append(mismatch)

        return matches, mismatches

    def compare(self) -> "ComparisonResults":
        """Perform full comparison between TAXSIM and PolicyEngine results"""
        print("Comparing TAXSIM and PolicyEngine results")

        # Compare federal taxes
        federal_matches, federal_mismatches = self._compare_tax_column(
            self.config.federal_tax_col, self.config.federal_tolerance, "federal"
        )

        # Compare state taxes
        state_matches, state_mismatches = self._compare_tax_column(
            self.config.state_tax_col, self.config.state_tolerance, "state"
        )

        return ComparisonResults(
            total_records=len(self.taxsim_results),
            federal_matches=federal_matches,
            federal_mismatches=federal_mismatches,
            state_matches=state_matches,
            state_mismatches=state_mismatches,
            config=self.config,
            taxsim_results=self.taxsim_results,
            policyengine_results=self.policyengine_results,
        )


class ComparisonResults:
    """Results of tax calculation comparison"""

    def __init__(
        self,
        total_records: int,
        federal_matches: np.ndarray,
        federal_mismatches: List[MismatchRecord],
        state_matches: np.ndarray,
        state_mismatches: List[MismatchRecord],
        config: ComparisonConfig,
        taxsim_results: pd.DataFrame = None,
        policyengine_results: pd.DataFrame = None,
    ):
        self.total_records = total_records
        self.federal_matches = federal_matches
        self.federal_mismatches = federal_mismatches
        self.state_matches = state_matches
        self.state_mismatches = state_mismatches
        self.config = config
        self.taxsim_results = taxsim_results
        self.policyengine_results = policyengine_results

    @property
    def federal_match_count(self) -> int:
        """Number of federal tax matches"""
        return int(self.federal_matches.sum()) if len(self.federal_matches) > 0 else 0

    @property
    def federal_match_percentage(self) -> float:
        """Percentage of federal tax matches"""
        if self.total_records == 0:
            return 0.0
        return (self.federal_match_count / self.total_records) * 100

    @property
    def state_match_count(self) -> int:
        """Number of state tax matches"""
        return int(self.state_matches.sum()) if len(self.state_matches) > 0 else 0

    @property
    def state_match_percentage(self) -> float:
        """Percentage of state tax matches"""
        if self.total_records == 0:
            return 0.0
        return (self.state_match_count / self.total_records) * 100

    def save_mismatches(
        self, output_dir: Path, input_data: pd.DataFrame = None, year: int = None
    ):
        """Save detailed mismatch information to CSV files"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        year_suffix = f"_{year}" if year else ""

        # Save federal mismatches
        if self.federal_mismatches:
            federal_df = self._create_mismatch_dataframe(
                self.federal_mismatches, input_data
            )
            federal_path = output_dir / f"federal_mismatches{year_suffix}.csv"
            federal_df.to_csv(federal_path, index=False)
            print(
                f"Saved {len(self.federal_mismatches)} federal tax mismatches to: {federal_path}"
            )

        # Save state mismatches
        if self.state_mismatches:
            state_df = self._create_mismatch_dataframe(
                self.state_mismatches, input_data
            )
            state_path = output_dir / f"state_mismatches{year_suffix}.csv"
            state_df.to_csv(state_path, index=False)
            print(
                f"Saved {len(self.state_mismatches)} state tax mismatches to: {state_path}"
            )

    def save_consolidated_results(
        self, output_dir: Path, input_data: pd.DataFrame = None, year: int = None
    ):
        """Save consolidated comparison results with both matches and mismatches in a single CSV"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        year_suffix = f"_{year}" if year else ""

        if self.taxsim_results is None or self.policyengine_results is None:
            print(
                "Error: Cannot save consolidated results without original result dataframes"
            )
            return

        # Create consolidated dataframe with 2 rows per record
        consolidated_rows = []

        # Get all taxsimids that we compared
        taxsim_ids = set(self.taxsim_results[self.config.id_col])

        # Create mismatch lookup sets for quick checking
        federal_mismatch_ids = {m.taxsimid for m in self.federal_mismatches}
        state_mismatch_ids = {m.taxsimid for m in self.state_mismatches}

        for taxsim_id in taxsim_ids:
            # Get the records for this ID
            taxsim_record = self.taxsim_results[
                self.taxsim_results[self.config.id_col] == taxsim_id
            ].iloc[0]
            pe_record = self.policyengine_results[
                self.policyengine_results[self.config.id_col] == taxsim_id
            ].iloc[0]

            # Get input data for this record if available
            input_record = None
            if input_data is not None:
                input_matches = input_data[input_data[self.config.id_col] == taxsim_id]
                if len(input_matches) > 0:
                    input_record = input_matches.iloc[0]

            # Determine match status
            federal_match = taxsim_id not in federal_mismatch_ids
            state_match = taxsim_id not in state_mismatch_ids

            # Create TAXSIM row
            taxsim_row = self._create_consolidated_row(
                taxsim_record, input_record, "taxsim", federal_match, state_match
            )
            consolidated_rows.append(taxsim_row)

            # Create PolicyEngine row
            pe_row = self._create_consolidated_row(
                pe_record, input_record, "policyengine", federal_match, state_match
            )
            consolidated_rows.append(pe_row)

        # Create DataFrame and save
        consolidated_df = pd.DataFrame(consolidated_rows)
        consolidated_path = output_dir / f"comparison_results{year_suffix}.csv"
        consolidated_df.to_csv(consolidated_path, index=False)

        print(
            f"Saved consolidated comparison results ({len(consolidated_rows)} rows for {len(taxsim_ids)} records) to: {consolidated_path}"
        )

    def _create_consolidated_row(
        self,
        result_record: pd.Series,
        input_record: pd.Series = None,
        source: str = "taxsim",
        federal_match: bool = True,
        state_match: bool = True,
    ) -> dict:
        """Create a single row for the consolidated output with shared column names"""
        row = {}

        # Add input data columns if available (these should be identical for both rows)
        if input_record is not None:
            for col in input_record.index:
                row[col] = input_record[col]

        # Add state code column based on numeric state value
        if "state" in row:
            row["state_code"] = get_state_code(
                int(float(row["state"])) if pd.notna(row["state"]) else 0
            )
        elif "state" in result_record.index:
            row["state_code"] = get_state_code(
                int(float(result_record["state"]))
                if pd.notna(result_record["state"])
                else 0
            )

        # Add source identifier and match status
        row["source"] = source
        row["federal_match"] = federal_match
        row["state_match"] = state_match
        row["overall_match"] = federal_match and state_match

        # Add all result columns from the source (without prefixes)
        for col in result_record.index:
            # Only add columns that aren't already in the row (from input data)
            if col not in row:
                row[col] = result_record[col]

        return row

    def _create_mismatch_dataframe(
        self, mismatches: List[MismatchRecord], input_data: pd.DataFrame = None
    ) -> pd.DataFrame:
        """Create DataFrame from mismatch records with input data and comparison values at the end"""

        if not mismatches:
            return pd.DataFrame()

        # Start with input data if provided
        if input_data is not None:
            # Get taxsimids of mismatches
            mismatch_ids = [m.taxsimid for m in mismatches]

            # Filter input data to only mismatch records
            result_df = input_data[input_data["taxsimid"].isin(mismatch_ids)].copy()

            # Create a mapping from taxsimid to mismatch data
            mismatch_map = {m.taxsimid: m for m in mismatches}

            # Add comparison columns at the end
            tax_type = mismatches[0].tax_type  # All mismatches should be same type
            if tax_type == "federal":
                result_df["taxsim_federal_tax"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].taxsim_value
                )
                result_df["policyengine_federal_tax"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].policyengine_value
                )
                result_df["federal_difference"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].difference
                )
            else:  # state
                result_df["taxsim_state_tax"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].taxsim_value
                )
                result_df["policyengine_state_tax"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].policyengine_value
                )
                result_df["state_difference"] = result_df["taxsimid"].map(
                    lambda x: mismatch_map[x].difference
                )

        else:
            # Fallback to basic mismatch data if no input data provided
            mismatch_data = []
            for m in mismatches:
                record = {
                    "taxsimid": m.taxsimid,
                    "tax_type": m.tax_type,
                    "taxsim_value": m.taxsim_value,
                    "policyengine_value": m.policyengine_value,
                    "difference": m.difference,
                }
                if m.state is not None:
                    record["state"] = m.state
                mismatch_data.append(record)

            result_df = pd.DataFrame(mismatch_data)

        return result_df
