"""
CPS to TAXSIM Comparison Tool (Consolidated Version)

This script processes a CPS H5 file or a CSV file and compares tax calculations between TAXSIM and PolicyEngine.
It can extract person, household, and tax unit data from the H5 file, converts it to TAXSIM format,
or directly use a pre-formatted CSV file. It runs both TAXSIM and PolicyEngine on the data, and reports
the percentage of records that match in state and federal tax calculations.

Usage with H5:
  python vectorized_validation.py [file].h5 --use-h5 --year 2022 [--sample 100] [--output-dir output]

Usage with CSV:
  python vectorized_validation.py [file].csv --year 2022 [--output-dir output]

Extract H5 to CSV:
  python vectorized_validation.py [file].h5 --extract-only --year 2022 [--output-dir output]

Arguments:
  file:           Path to the H5 file or CSV file (required)
  --use-h5:       Flag indicating the input is an H5 file (default: False)
  --extract-only: Extract data from H5 file to CSV and exit (no comparison)
  --year:         Tax year (2021, 2022, or 2023), defaults to 2022
  --output-dir:   Directory to save output files (optional)
  --sample:       Number of records to sample (0 = use all)
"""

import pandas as pd
import numpy as np
import os
import subprocess
import sys
import platform
import h5py
from pathlib import Path
from policyengine_taxsim.core.input_mapper import generate_household
from policyengine_taxsim.core.output_mapper import export_household
from policyengine_taxsim.core.utils import get_state_number


def h5_to_dataframe(
    h5_file_path,
    person_fields=None,
    household_fields=None,
    tax_unit_fields=None,
    spm_unit_fields=None,
    year="2024",
    sample_size=0,
):
    """
    Extract data from an H5 file into a pandas DataFrame

    Args:
        h5_file_path: Path to the H5 file
        person_fields: List of person-level fields to extract
        household_fields: List of household-level fields to extract
        tax_unit_fields: List of tax unit-level fields to extract
        spm_unit_fields: List of SPM unit-level fields to extract
        year: Year string to use for extracting data
        sample_size: Number of records to sample (0 = use all)

    Returns:
        DataFrame with extracted data
    """
    if person_fields is None:
        person_fields = [
            "age",
            "employment_income",
            "self_employment_income",
            "taxable_interest_income",
            "qualified_dividend_income",
            "short_term_capital_gains",
            "long_term_capital_gains",
            "taxable_pension_income",
            "unemployment_compensation",
            "social_security_retirement",
            "person_tax_unit_id",
            "person_household_id",
            "person_spm_unit_id",
            "is_household_head",
            "is_female",
            "rent",
            "partnership_s_corp_income",
            "qualified_business_income",
        ]

    if household_fields is None:
        household_fields = ["household_id", "state_fips"]

    if tax_unit_fields is None:
        tax_unit_fields = ["tax_unit_id"]

    if spm_unit_fields is None:
        spm_unit_fields = ["spm_unit_id", "spm_unit_pre_subsidy_childcare_expenses"]

    print(f"Reading H5 file: {h5_file_path}")

    # Open the H5 file
    with h5py.File(h5_file_path, "r") as f:
        # Extract person-level data
        person_data = {}
        for field in person_fields:
            if field in f and f"{year}" in f[field]:
                person_data[field] = f[field][f"{year}"][:]

        # Create person DataFrame
        person_df = pd.DataFrame(person_data)

        # Extract household-level data
        household_data = {}
        for field in household_fields:
            if field in f and f"{year}" in f[field]:
                household_data[field] = f[field][f"{year}"][:]

        # Create household DataFrame with proper indexing
        if household_data:
            # Create household index
            household_index = np.arange(
                len(household_data["household_id"])
                if "household_id" in household_data
                else 0
            )
            household_df = pd.DataFrame(household_data, index=household_index)

            # Merge household data to person data
            if (
                "person_household_id" in person_df.columns
                and "household_id" in household_df.columns
            ):
                # Create a mapping from household_id to household data
                household_mapping = {
                    hid: {"state_fips": sf}
                    for hid, sf in zip(
                        household_df["household_id"],
                        (
                            household_df["state_fips"]
                            if "state_fips" in household_df
                            else [0] * len(household_df)
                        ),
                    )
                }

                # Apply the mapping to add household data to person records
                if (
                    "state_fips" not in person_df.columns
                    and "state_fips" in household_fields
                ):
                    person_df["state_fips"] = person_df["person_household_id"].apply(
                        lambda hid: household_mapping.get(hid, {}).get("state_fips", 0)
                    )

        # Extract tax unit-level data
        tax_unit_data = {}
        for field in tax_unit_fields:
            if field in f and f"{year}" in f[field]:
                tax_unit_data[field] = f[field][f"{year}"][:]

        # Add tax unit-level fields individually
        if tax_unit_data and "tax_unit_id" in tax_unit_data:
            # Add fields that are stored at tax unit level
            for field in ["deductible_mortgage_interest", "real_estate_taxes"]:
                if field in f and f"{year}" in f[field]:
                    # Create mapping from tax_unit_id to field value
                    field_values = f[field][f"{year}"][:]
                    if len(field_values) == len(tax_unit_data["tax_unit_id"]):
                        # Direct mapping from tax_unit_id index to field value
                        field_mapping = {
                            tuid: val
                            for tuid, val in zip(
                                tax_unit_data["tax_unit_id"], field_values
                            )
                        }

                        # Apply mapping to add field to person records
                        person_df[field] = person_df["person_tax_unit_id"].apply(
                            lambda tuid: field_mapping.get(tuid, 0)
                        )

        # Extract SPM unit-level data
        spm_unit_data = {}
        for field in spm_unit_fields:
            if field in f and f"{year}" in f[field]:
                spm_unit_data[field] = f[field][f"{year}"][:]

        # Add SPM unit-level fields to person records
        if spm_unit_data and "spm_unit_id" in spm_unit_data:
            # Create SPM unit DataFrame
            spm_unit_index = np.arange(len(spm_unit_data["spm_unit_id"]))
            spm_unit_df = pd.DataFrame(spm_unit_data, index=spm_unit_index)

            # Map childcare expenses from SPM unit to person
            if "spm_unit_pre_subsidy_childcare_expenses" in spm_unit_data:
                # Create mapping from spm_unit_id to childcare expenses
                childcare_mapping = {
                    spm_id: expense
                    for spm_id, expense in zip(
                        spm_unit_data["spm_unit_id"],
                        spm_unit_data["spm_unit_pre_subsidy_childcare_expenses"],
                    )
                }

                # Apply the mapping to add childcare expenses to person records
                if "person_spm_unit_id" in person_df.columns:
                    person_df["childcare_expenses"] = person_df[
                        "person_spm_unit_id"
                    ].apply(lambda spm_id: childcare_mapping.get(spm_id, 0))

    print(f"Created DataFrame with {len(person_df)} records")

    # Sample records if requested
    if sample_size > 0:
        total_records = len(person_df)
        print(f"Total records in H5 file: {total_records}")

        # Sample records
        person_df = person_df.sample(n=min(sample_size, total_records), random_state=42)
        print(f"Sampled {len(person_df)} records")

    return person_df


def convert_fips_to_taxsim_state(fips_code):
    """
    Convert FIPS state code to TAXSIM state code

    Args:
        fips_code: State FIPS code (1-56)

    Returns:
        TAXSIM state code (1-51)
    """
    # Mapping from FIPS to TAXSIM state codes
    mapping = {
        2: 2,  # Alaska
        4: 3,  # Arizona
        5: 4,  # Arkansas
        6: 5,  # California
        8: 6,  # Colorado
        9: 7,  # Connecticut
        10: 8,  # Delaware
        11: 9,  # DC
        12: 10,  # Florida
        13: 11,  # Georgia
        15: 12,  # Hawaii
        16: 13,  # Idaho
        17: 14,  # Illinois
        18: 15,  # Indiana
        19: 16,  # Iowa
        20: 17,  # Kansas
        21: 18,  # Kentucky
        22: 19,  # Louisiana
        23: 20,  # Maine
        24: 21,  # Maryland
        25: 22,  # Massachusetts
        26: 23,  # Michigan
        27: 24,  # Minnesota
        28: 25,  # Mississippi
        29: 26,  # Missouri
        30: 27,  # Montana
        31: 28,  # Nebraska
        32: 29,  # Nevada
        33: 30,  # New Hampshire
        34: 31,  # New Jersey
        35: 32,  # New Mexico
        36: 33,  # New York
        37: 34,  # North Carolina
        38: 35,  # North Dakota
        39: 36,  # Ohio
        40: 37,  # Oklahoma
        41: 38,  # Oregon
        42: 39,  # Pennsylvania
        44: 40,  # Rhode Island
        45: 41,  # South Carolina
        46: 42,  # South Dakota
        47: 43,  # Tennessee
        48: 44,  # Texas
        49: 45,  # Utah
        50: 46,  # Vermont
        51: 47,  # Virginia
        53: 48,  # Washington
        54: 49,  # West Virginia
        55: 50,  # Wisconsin
        56: 51,  # Wyoming
    }

    return mapping.get(fips_code, 0)  # Default to 0 if not found


def h5_to_taxsim_format(h5_file_path, year, output_csv_path=None, sample_size=0):
    """
    Convert H5 file to TAXSIM input format

    Args:
        h5_file_path: Path to the H5 file
        year: Tax year (2021, 2022, or 2023)
        output_csv_path: Path to save the CSV file (optional)
        sample_size: Number of records to sample (0 = use all)

    Returns:
        DataFrame in TAXSIM format
    """
    print(f"Reading H5 file: {h5_file_path}")

    # Read the H5 file using our custom function
    h5_year = "2024"  # CPS data is for 2024, we'll adjust the tax year later
    person_fields = [
        "age",
        "employment_income",
        "self_employment_income",
        "taxable_interest_income",
        "qualified_dividend_income",
        "short_term_capital_gains",
        "long_term_capital_gains",
        "taxable_pension_income",
        "unemployment_compensation",
        "social_security_retirement",
        "person_tax_unit_id",
        "person_household_id",
        "person_spm_unit_id",
        "is_household_head",
        "is_female",
        "rent",
        "partnership_s_corp_income",
    ]
    household_fields = ["household_id", "state_fips"]
    tax_unit_fields = ["tax_unit_id"]
    spm_unit_fields = ["spm_unit_id", "spm_unit_pre_subsidy_childcare_expenses"]

    df = h5_to_dataframe(
        h5_file_path,
        person_fields=person_fields,
        household_fields=household_fields,
        tax_unit_fields=tax_unit_fields,
        spm_unit_fields=spm_unit_fields,
        year=h5_year,
        sample_size=sample_size,
    )

    # Prepare a list to store TAXSIM input records
    taxsim_records = []

    # Group by tax_unit_id to create tax unit-level records
    tax_units = df.groupby("person_tax_unit_id")

    # Assign a unique taxsimid to each record
    taxsim_id = 1
    total_units = len(tax_units)

    print(f"Converting {total_units} tax units to TAXSIM format")

    # Process tax units with progress indicator
    for i, (tax_unit_id, group) in enumerate(tax_units, 1):
        # Show progress every 100 units, or for the first and last unit
        if i % 100 == 0 or i == 1 or i == total_units:
            print(f"Converting tax units: {i}/{total_units}", end="\r")
        # Filter the group to get tax unit head and spouse
        is_head = group["is_household_head"] == True

        if is_head.any():
            # Get the head's record
            head = group[is_head].iloc[0]

            # Determine filing status based on whether there's another adult in the unit
            # For simplicity, we'll assume single (1) unless we find evidence of a spouse
            filing_status = 1

            # Get spouse if present (assuming not head and adult)
            non_head_adults = group[(~is_head) & (group["age"] >= 18)]
            spouse = None
            if len(non_head_adults) > 0:
                spouse = non_head_adults.iloc[0]
                filing_status = 2  # Married filing jointly

            # Get number of dependents (assuming anyone who is not head or spouse)
            dependents = group[
                (
                    ~is_head
                    if spouse is None
                    else ~(is_head | (group.index == spouse.name))
                )
            ]
            num_dependents = len(dependents)

            # Convert state FIPS to TAXSIM state code
            state_fips = int(head.get("state_fips", 0))
            taxsim_state = convert_fips_to_taxsim_state(state_fips)

            # Create a TAXSIM input record with all required fields
            taxsim_record = {
                # ID and basic info
                "taxsimid": taxsim_id,
                "year": int(year),
                "state": taxsim_state,
                "mstat": filing_status,
                # Taxpayer info
                "page": int(head.get("age", 40)),
                "sage": int(spouse.get("age", 40)) if spouse is not None else 0,
                # Dependents
                "depx": num_dependents,
                # Income - primary taxpayer
                "pwages": float(head.get("employment_income", 0)),
                "psemp": float(head.get("self_employment_income", 0)),
                # Income - spouse
                "swages": (
                    float(spouse.get("employment_income", 0))
                    if spouse is not None
                    else 0
                ),
                "ssemp": (
                    float(spouse.get("self_employment_income", 0))
                    if spouse is not None
                    else 0
                ),
                # Investment income
                "dividends": float(group["qualified_dividend_income"].sum()),
                "intrec": float(group["taxable_interest_income"].sum()),
                "stcg": float(group["short_term_capital_gains"].sum()),
                "ltcg": float(group["long_term_capital_gains"].sum()),
                "otherprop": 0,
                "nonprop": 0,
                # Retirement and benefits
                "pensions": float(group["taxable_pension_income"].sum()),
                "gssi": float(group["social_security_retirement"].sum()),
                # Unemployment
                "pui": float(head.get("unemployment_compensation", 0)),
                "sui": (
                    float(spouse.get("unemployment_compensation", 0))
                    if spouse is not None
                    else 0
                ),
                # Other income and deductions
                "transfers": 0,
                "rentpaid": (
                    float(group["rent"].sum()) if "rent" in group.columns else 0
                ),
                "proptax": float(head.get("real_estate_taxes", 0)),
                "otheritem": 0,
                "childcare": float(head.get("childcare_expenses", 0)),
                "mortgage": float(head.get("deductible_mortgage_interest", 0)),
                "scorp": (
                    float(group["partnership_s_corp_income"].sum())
                    if "partnership_s_corp_income" in group.columns
                    else 0
                ),
                "pbusinc": float(head.get("qualified_business_income", 0)),
                "sbusinc": (
                    float(spouse.get("qualified_business_income", 0))
                    if spouse is not None
                    else 0
                ),
                "idtl": 2,  # Full output format
            }

            # Add ages for dependents if available
            if len(dependents) > 0:
                dependent_ages = dependents["age"].values
                for i, age in enumerate(dependent_ages, 1):
                    if i <= num_dependents:
                        taxsim_record[f"age{i}"] = int(age)

            # Append the record to our list
            taxsim_records.append(taxsim_record)

            # Increment the ID
            taxsim_id += 1

    # Clear the progress line
    print("")

    # Convert list of records to DataFrame
    taxsim_df = pd.DataFrame(taxsim_records)

    # Save to CSV if output path is provided
    if output_csv_path:
        taxsim_df.to_csv(output_csv_path, index=False)
        print(f"TAXSIM input saved to: {output_csv_path}")

    return taxsim_df


def run_taxsim(input_csv_path, output_csv_path):
    """
    Run TAXSIM on the input CSV file

    Args:
        input_csv_path: Path to the TAXSIM input CSV file
        output_csv_path: Path to save the TAXSIM output CSV file

    Returns:
        DataFrame with TAXSIM output
    """
    print(f"Running TAXSIM on: {input_csv_path}")

    # Verify input file
    input_df = pd.read_csv(input_csv_path)
    record_count = len(input_df)
    print(f"Input file has {record_count} records")
    print(f"Processing TAXSIM: {record_count} records", end="\r")

    # Format input for TAXSIM
    # TAXSIM requires a specific CSV format with header row

    # Required minimal columns
    required_columns = [
        "year",
        "state",
        "mstat",
        "pwages",
        "depx",
        "mortgage",
        "taxsimid",
        "idtl",
    ]

    # Additional columns we'll use
    additional_columns = [
        "page",
        "sage",
        "swages",
        "psemp",
        "ssemp",
        "dividends",
        "intrec",
        "stcg",
        "ltcg",
        "otherprop",
        "nonprop",
        "pensions",
        "gssi",
        "pui",
        "sui",
        "transfers",
        "rentpaid",
        "proptax",
        "otheritem",
        "childcare",
        "scorp",
    ]

    # All columns
    taxsim_columns = required_columns + additional_columns

    # Make sure all columns exist
    for col in taxsim_columns:
        if col not in input_df.columns:
            input_df[col] = 0

    # Reorder columns to match TAXSIM requirements
    ordered_df = input_df[taxsim_columns]

    formatted_input_path = str(input_csv_path).replace(".csv", "_formatted.csv")

    # Create TAXSIM input file in CSV format
    with open(formatted_input_path, "w") as f:
        # Write header line
        f.write(",".join(taxsim_columns) + "\n")

        # Write data rows in CSV format
        for _, row in ordered_df.iterrows():
            f.write(",".join(str(row[col]) for col in taxsim_columns) + "\n")

    # Determine the correct TAXSIM executable based on the OS
    system = platform.system().lower()
    if system == "darwin":
        taxsim_exe = "taxsim35-osx.exe"
    elif system == "windows":
        taxsim_exe = "taxsim-latest-windows.exe"
    elif system == "linux":
        taxsim_exe = "taxsim35-unix.exe"
    else:
        raise OSError(f"Unsupported operating system: {system}")

    # Path to TAXSIM executable
    taxsim_path = Path("resources") / "taxsim35" / taxsim_exe

    if not taxsim_path.exists():
        raise FileNotFoundError(f"TAXSIM executable not found at: {taxsim_path}")

    # Make executable
    if system != "windows":
        os.chmod(taxsim_path, 0o755)

    # Temporary output file
    raw_output_path = str(output_csv_path).replace(".csv", "_raw.txt")

    # Run TAXSIM
    if system != "windows":
        cmd = (
            f'cat "{formatted_input_path}" | "{str(taxsim_path)}" > "{raw_output_path}"'
        )
    else:
        cmd = f'cmd.exe /c "type "{formatted_input_path}" | "{str(taxsim_path)}" > "{raw_output_path}""'

    creation_flags = 0
    if system == "windows":
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags = subprocess.CREATE_NO_WINDOW
        else:
            creation_flags = 0x00000008  # DETACHED_PROCESS

    process = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        creationflags=creation_flags if system == "windows" else 0,
    )

    if process.returncode != 0:
        print(f"TAXSIM failed with error:\n{process.stderr}")
        if os.path.exists(raw_output_path):
            with open(raw_output_path, "r") as f:
                error_output = f.read()
            print(f"TAXSIM output:\n{error_output}")
        raise Exception(f"TAXSIM failed: {process.returncode}")

    # Process raw output into CSV
    try:
        # The output is in CSV format
        # First line contains column headers
        # Read directly with pandas
        output_df = pd.read_csv(raw_output_path)

        # Convert to list of dictionaries for compatibility with rest of code
        records = output_df.to_dict("records")

        # Convert to DataFrame
        output_df = pd.DataFrame(records)

        # Convert numeric columns
        for col in output_df.columns:
            if col != "state_name":
                output_df[col] = pd.to_numeric(output_df[col], errors="coerce")

        # Save to CSV
        output_df.to_csv(output_csv_path, index=False)

        # Clear the progress line and show completion message
        print("")
        print(f"TAXSIM output saved to: {output_csv_path}")

        return output_df

    except Exception as e:
        print(f"Error processing TAXSIM output: {str(e)}")
        if os.path.exists(raw_output_path):
            with open(raw_output_path, "r") as f:
                error_output = f.read()
            print(f"Raw TAXSIM output:\n{error_output}")
        raise


def run_policyengine_direct(taxsim_df):
    """
    Run PolicyEngine directly using the API

    Args:
        taxsim_df: DataFrame with TAXSIM input

    Returns:
        DataFrame with PolicyEngine output
    """
    print("Running PolicyEngine directly")

    results = []
    total_records = len(taxsim_df)

    # Process records with progress indicator
    for i, (_, row) in enumerate(taxsim_df.iterrows(), 1):
        # Show progress every 10 records, or for the first and last record
        if i % 10 == 0 or i == 1 or i == total_records:
            print(f"Processing PolicyEngine: {i}/{total_records} records", end="\r")

        # Generate household and export results
        taxsim_input = row.to_dict()
        pe_situation = generate_household(taxsim_input)
        pe_output = export_household(taxsim_input, pe_situation, False, False)
        results.append(pe_output)

    print("")  # Clear the progress line
    return pd.DataFrame(results)


def compare_results(
    taxsim_output, pe_output, taxsim_input=None, output_dir=None, year=None
):
    """
    Compare TAXSIM and PolicyEngine results

    Args:
        taxsim_output: DataFrame with TAXSIM output
        pe_output: DataFrame with PolicyEngine output
        taxsim_input: DataFrame with TAXSIM input (optional, for saving differences)
        output_dir: Directory to save output files (optional)
        year: Tax year (optional, used for naming output files)

    Returns:
        Dictionary with comparison results including match counts and percentages
    """
    print("Comparing TAXSIM and PolicyEngine results")

    # Normalize column names
    taxsim_output.columns = taxsim_output.columns.str.lower()
    pe_output.columns = pe_output.columns.str.lower()

    # Sort both DataFrames by taxsimid
    taxsim_output = taxsim_output.sort_values("taxsimid").reset_index(drop=True)
    pe_output = pe_output.sort_values("taxsimid").reset_index(drop=True)

    # Convert numeric columns to float
    numeric_columns = taxsim_output.select_dtypes(include=["number"]).columns
    for col in numeric_columns:
        if col in pe_output.columns:
            taxsim_output[col] = pd.to_numeric(taxsim_output[col], errors="coerce")
            pe_output[col] = pd.to_numeric(pe_output[col], errors="coerce")

    # Compare federal and state income taxes
    federal_tax_col = "fiitax"
    state_tax_col = "siitax"

    # Lists to store mismatched records
    federal_mismatches = []
    state_mismatches = []

    # Check if columns exist
    if (
        federal_tax_col in taxsim_output.columns
        and federal_tax_col in pe_output.columns
    ):
        federal_matches = np.isclose(
            taxsim_output[federal_tax_col],
            pe_output[federal_tax_col],
            atol=50.0,  # $50 absolute tolerance
            equal_nan=True,
        )
        federal_match_count = federal_matches.sum()
        federal_match_pct = (federal_match_count / len(taxsim_output)) * 100

        # Track federal tax mismatches
        for i, matches in enumerate(federal_matches):
            if not matches:
                record = {
                    "taxsimid": taxsim_output.iloc[i]["taxsimid"],
                    "taxsim_federal": taxsim_output.iloc[i][federal_tax_col],
                    "pe_federal": pe_output.iloc[i][federal_tax_col],
                    "difference": taxsim_output.iloc[i][federal_tax_col]
                    - pe_output.iloc[i][federal_tax_col],
                }
                federal_mismatches.append(record)
    else:
        federal_match_count = 0
        federal_match_pct = 0

    if state_tax_col in taxsim_output.columns and state_tax_col in pe_output.columns:
        state_matches = np.isclose(
            taxsim_output[state_tax_col],
            pe_output[state_tax_col],
            atol=15.0,  # $15 absolute tolerance
            equal_nan=True,
        )
        state_match_count = state_matches.sum()
        state_match_pct = (state_match_count / len(taxsim_output)) * 100

        # Track state tax mismatches
        for i, matches in enumerate(state_matches):
            if not matches:
                record = {
                    "taxsimid": taxsim_output.iloc[i]["taxsimid"],
                    "state": taxsim_output.iloc[i]["state"],
                    "taxsim_state": taxsim_output.iloc[i][state_tax_col],
                    "pe_state": pe_output.iloc[i][state_tax_col],
                    "difference": taxsim_output.iloc[i][state_tax_col]
                    - pe_output.iloc[i][state_tax_col],
                }
                state_mismatches.append(record)
    else:
        state_match_count = 0
        state_match_pct = 0

    # Create a DataFrame with all mismatches
    # If taxsim_input is provided, join it with the mismatch data
    if len(federal_mismatches) > 0 or len(state_mismatches) > 0:
        print(
            f"Found {len(federal_mismatches)} federal tax mismatches and {len(state_mismatches)} state tax mismatches"
        )

        # Create DataFrames for mismatches
        federal_mismatch_df = (
            pd.DataFrame(federal_mismatches) if federal_mismatches else pd.DataFrame()
        )
        state_mismatch_df = (
            pd.DataFrame(state_mismatches) if state_mismatches else pd.DataFrame()
        )

        # If we have both input data and an output directory, save detailed mismatch info
        if taxsim_input is not None and output_dir is not None:
            # Ensure output directory exists
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)

            # Save federal tax mismatches with all input data
            if len(federal_mismatches) > 0:
                federal_ids = federal_mismatch_df["taxsimid"].unique()
                federal_full = taxsim_input[
                    taxsim_input["taxsimid"].isin(federal_ids)
                ].copy()

                # Add TAXSIM and PolicyEngine results
                for idx, row in federal_full.iterrows():
                    taxsim_id = row["taxsimid"]
                    mismatch = federal_mismatch_df[
                        federal_mismatch_df["taxsimid"] == taxsim_id
                    ]

                    if not mismatch.empty:
                        federal_full.loc[idx, "taxsim_federal"] = mismatch.iloc[0][
                            "taxsim_federal"
                        ]
                        federal_full.loc[idx, "pe_federal"] = mismatch.iloc[0][
                            "pe_federal"
                        ]
                        federal_full.loc[idx, "federal_difference"] = mismatch.iloc[0][
                            "difference"
                        ]

                # Save to CSV
                year_suffix = f"_{year}" if year else ""
                federal_output_path = (
                    output_dir / f"federal_mismatches{year_suffix}.csv"
                )
                federal_full.to_csv(federal_output_path, index=False)
                print(f"Saved federal tax mismatches to: {federal_output_path}")

            # Save state tax mismatches with all input data
            if len(state_mismatches) > 0:
                state_ids = state_mismatch_df["taxsimid"].unique()
                state_full = taxsim_input[
                    taxsim_input["taxsimid"].isin(state_ids)
                ].copy()

                # Add TAXSIM and PolicyEngine results
                for idx, row in state_full.iterrows():
                    taxsim_id = row["taxsimid"]
                    mismatch = state_mismatch_df[
                        state_mismatch_df["taxsimid"] == taxsim_id
                    ]

                    if not mismatch.empty:
                        state_full.loc[idx, "taxsim_state"] = mismatch.iloc[0][
                            "taxsim_state"
                        ]
                        state_full.loc[idx, "pe_state"] = mismatch.iloc[0]["pe_state"]
                        state_full.loc[idx, "state_difference"] = mismatch.iloc[0][
                            "difference"
                        ]

                # Save to CSV
                year_suffix = f"_{year}" if year else ""
                state_output_path = output_dir / f"state_mismatches{year_suffix}.csv"
                state_full.to_csv(state_output_path, index=False)
                print(f"Saved state tax mismatches to: {state_output_path}")

    results = {
        "total_records": len(taxsim_output),
        "federal_match_count": federal_match_count,
        "federal_match_pct": federal_match_pct,
        "federal_mismatches": federal_mismatches,
        "state_match_count": state_match_count,
        "state_match_pct": state_match_pct,
        "state_mismatches": state_mismatches,
    }

    return results


def process_cps_h5(
    file_path, year, output_dir=None, sample_size=0, save_csv=False, use_h5=False
):
    """
    Process CPS H5 file or CSV file, run both engines, and compare results

    Args:
        file_path: Path to the H5 file or CSV file
        year: Tax year (2021, 2022, or 2023)
        output_dir: Directory to save output files (optional)
        sample_size: Number of records to sample (0 = use all)
        use_h5: Whether the input file is an H5 file (default: False)

    Returns:
        Dictionary with comparison results
    """
    if output_dir is None:
        output_dir = Path("output")
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(exist_ok=True)

    if use_h5:
        # Convert H5 to TAXSIM format
        taxsim_input_path = output_dir / f"taxsim_input_{year}.csv"
        taxsim_df = h5_to_taxsim_format(file_path, year, taxsim_input_path, sample_size)
    else:
        # Use the provided CSV directly
        taxsim_input_path = file_path
        taxsim_df = pd.read_csv(taxsim_input_path)

        # Make sure year column matches requested year
        if "year" in taxsim_df.columns and year is not None:
            taxsim_df["year"] = year

        # If we need to sample, do it here
        if sample_size > 0 and len(taxsim_df) > sample_size:
            sampled_df = taxsim_df.sample(n=sample_size, random_state=42)
            print(f"Sampled {len(sampled_df)} records from {taxsim_input_path}")

            # Save the sampled data to a temporary file
            if output_dir:
                sample_path = (
                    output_dir / f"sampled_{os.path.basename(taxsim_input_path)}"
                )
                sampled_df.to_csv(sample_path, index=False)
                taxsim_input_path = sample_path
                print(f"Saved sampled data to: {sample_path}")

            # Use the sampled dataframe for processing
            taxsim_df = sampled_df

    # Run PolicyEngine directly
    pe_output = run_policyengine_direct(taxsim_df)

    # Cleanup temporary files
    temp_files = []

    # Try running TAXSIM
    taxsim_output_path = output_dir / "temp_taxsim_output.csv"
    temp_files.append(taxsim_output_path)

    try:
        taxsim_output = run_taxsim(taxsim_input_path, taxsim_output_path)

        # Compare results and save mismatches
        comparison = compare_results(
            taxsim_output,
            pe_output,
            taxsim_input=taxsim_df,  # Pass the input data for saving mismatches
            output_dir=output_dir,  # Pass the output directory
            year=year,  # Pass the tax year for file naming
        )
        comparison["comparison_successful"] = True

        print("\nComparison Results (TAXSIM vs PolicyEngine):")
        print(f"Total Records: {comparison['total_records']}")
        print(
            f"Federal Tax Matches: {comparison['federal_match_count']} ({comparison['federal_match_pct']:.2f}%)"
        )
        print(
            f"State Tax Matches: {comparison['state_match_count']} ({comparison['state_match_pct']:.2f}%)"
        )

        # Clean up temporary files
        if not save_csv:
            for file_path in temp_files:
                if file_path.exists():
                    os.remove(file_path)

            # Clean up input file if generated from H5 and not saving CSVs
            if not save_csv and use_h5 and taxsim_input_path.exists():
                os.remove(taxsim_input_path)

        return comparison

    except Exception as e:
        print(f"\nWarning: TAXSIM execution failed: {str(e)}")

        # Return a dictionary indicating that comparison failed
        comparison = {
            "total_records": len(pe_output),
            "federal_match_count": 0,
            "federal_match_pct": 0,
            "state_match_count": 0,
            "state_match_pct": 0,
            "comparison_successful": False,
        }

        # Clean up temporary files
        if not save_csv:
            for file_path in temp_files:
                if file_path.exists():
                    os.remove(file_path)

            # Clean up input file if generated from H5 and not saving CSVs
            if not save_csv and use_h5 and taxsim_input_path.exists():
                os.remove(taxsim_input_path)

        return comparison


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Process CPS H5 file or CSV with TAXSIM and PolicyEngine"
    )
    parser.add_argument("file", help="Path to the H5 file or CSV file")
    parser.add_argument(
        "--use-h5", action="store_true", help="Flag indicating the input is an H5 file"
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract data from H5 file to CSV and exit (no comparison)",
    )
    parser.add_argument(
        "--year", type=int, default=2022, help="Tax year (2021, 2022, or 2023)"
    )
    parser.add_argument("--output-dir", help="Directory to save output files")
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Number of records to sample (0 = use all)",
    )
    parser.add_argument(
        "--save-csv", action="store_true", help="Save intermediate CSV files"
    )

    args = parser.parse_args()

    # Set up output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path("output")
    output_dir.mkdir(exist_ok=True)

    if args.extract_only:
        # Extract only mode - just convert H5 to CSV and exit
        if not args.file.endswith(".h5"):
            print("Error: --extract-only requires an H5 file input")
            sys.exit(1)

        year_str = str(args.year)
        output_csv_path = output_dir / f"taxsim_input_{year_str}.csv"
        print(f"Extracting all households from H5 file for tax year {year_str}...")

        # Convert H5 to TAXSIM format without sampling first (get all records)
        taxsim_df = h5_to_taxsim_format(args.file, args.year, None, 0)

        # Apply sampling if requested
        if args.sample > 0 and len(taxsim_df) > args.sample:
            print(f"Sampling {args.sample} records from {len(taxsim_df)} total records")
            taxsim_df = taxsim_df.sample(n=args.sample, random_state=42)
            output_csv_path = (
                output_dir / f"taxsim_input_{year_str}_sample_{args.sample}.csv"
            )

        # Save to CSV
        taxsim_df.to_csv(output_csv_path, index=False)
        print(
            f"Successfully extracted {len(taxsim_df)} tax units to: {output_csv_path}"
        )
        print(
            "Note: This CSV is ready for TAXSIM processing and can be used directly with this script."
        )
        sys.exit(0)

    # Process the file (comparison mode)
    process_cps_h5(
        args.file, args.year, args.output_dir, args.sample, args.save_csv, args.use_h5
    )
