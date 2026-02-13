import os
import platform
import subprocess
import tempfile
from pathlib import Path
import pandas as pd
from .base_runner import BaseTaxRunner
from ..core.utils import convert_taxsim32_dependents


class TaxsimRunner(BaseTaxRunner):
    """Clean TAXSIMTEST executable runner"""

    # TAXSIM column definitions based on official NBER documentation
    # https://taxsim.nber.org/taxsimtest/
    REQUIRED_COLUMNS = [
        "taxsimid",  # 1. Record ID (auto-assigned if not present)
        "year",  # 2. Tax year
        "state",  # 3. State code
        "mstat",  # 4. Marital status
        "page",  # 5. Primary taxpayer age
        "sage",  # 5. Age of secondary taxpayer
        "depx",  # 6. Number of dependents
    ]

    # Dependent ages come after depx according to official docs
    DEPENDENT_AGE_COLUMNS = [
        "age1",
        "age2",
        "age3",
        "age4",
        "age5",
        "age6",
        "age7",
        "age8",
        "age9",
        "age10",
        "age11",
    ]
    
    # TAXSIM32 format columns for dependent counts by age bracket
    TAXSIM32_COLUMNS = [
        "dep13",  # Number of dependents under 13
        "dep17",  # Number of dependents under 17 (includes under 13)
        "dep18",  # Number of dependents under 18 (includes under 17 and 13)
    ]

    # Income and deduction columns
    INCOME_COLUMNS = [
        "pwages",  # Primary wages
        "swages",  # Wage and salary income of secondary taxpayer
        "psemp",  # Primary self-employment
        "ssemp",  # Spouse self-employment
        "dividends",  # Dividend income
        "intrec",  # Interest received
        "stcg",  # Short-term capital gains
        "ltcg",  # Long-term capital gains
        "otherprop",  # Other property income
        "nonprop",  # Other non-property income
        "pensions",  # Taxable pensions
        "gssi",  # Gross social security
        "pui",  # Primary unemployment insurance
        "sui",  # Spouse unemployment insurance
        "transfers",  # Non-taxable transfers
        "rentpaid",  # Rent paid
        "proptax",  # Property taxes
        "otheritem",  # Other itemized deductions
        "childcare",  # Child care expenses
        "mortgage",  # Mortgage interest
        "scorp",  # S-Corp profits
        "idtl",  # Output control
    ]

    ALL_COLUMNS = REQUIRED_COLUMNS + DEPENDENT_AGE_COLUMNS + TAXSIM32_COLUMNS + INCOME_COLUMNS

    def __init__(self, input_df: pd.DataFrame, taxsim_path: str = None):
        super().__init__(input_df)
        self.taxsim_path = taxsim_path or self._detect_taxsim_executable()
        self._validate_executable()

    def _detect_taxsim_executable(self) -> Path:
        """Detect correct TAXSIM executable based on OS"""
        import sys

        system = platform.system().lower()

        if system == "darwin":
            exe_name = "taxsimtest-osx.exe"
        elif system == "windows":
            exe_name = "taxsimtest-windows.exe"
        elif system == "linux":
            exe_name = "taxsimtest-linux.exe"
        else:
            raise OSError(f"Unsupported operating system: {system}")

        # Try multiple locations in order of preference:
        search_paths = [
            # 1. Relative path (for running from repo during development)
            Path("resources") / "taxsimtest" / exe_name,
            # 2. Shared data location (for pip-installed packages)
            Path(sys.prefix) / "share" / "policyengine_taxsim" / "taxsimtest" / exe_name,
            # 3. User site-packages shared data
            Path(sys.base_prefix) / "share" / "policyengine_taxsim" / "taxsimtest" / exe_name,
        ]

        # Also check virtualenv locations
        if hasattr(sys, "real_prefix"):  # virtualenv
            search_paths.append(
                Path(sys.real_prefix) / "share" / "policyengine_taxsim" / "taxsimtest" / exe_name
            )

        for taxsim_path in search_paths:
            if taxsim_path.exists():
                return taxsim_path

        # If not found, return the first path (will fail in _validate_executable with clear error)
        return search_paths[0]

    def _validate_executable(self):
        """Validate TAXSIM executable exists and is executable"""
        if not self.taxsim_path.exists():
            raise FileNotFoundError(
                f"TAXSIM executable not found at: {self.taxsim_path}"
            )

        # Make executable on Unix-like systems
        if platform.system().lower() != "windows":
            os.chmod(self.taxsim_path, 0o755)

    def _format_input_for_taxsim(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format DataFrame for TAXSIM input requirements"""
        formatted_df = df.copy()

        # Convert TAXSIM32 format to individual ages for each row
        for idx, row in formatted_df.iterrows():
            row_dict = row.to_dict()
            converted_row = convert_taxsim32_dependents(row_dict)
            for key, value in converted_row.items():
                formatted_df.loc[idx, key] = value

        # Ensure all columns exist with default values
        for col in self.ALL_COLUMNS:
            if col not in formatted_df.columns:
                formatted_df[col] = 0

        # Create dynamic column list based on number of dependents
        result_rows = []

        for _, row in formatted_df.iterrows():
            depx = int(row.get("depx", 0))

            # Start with required columns
            dynamic_columns = self.REQUIRED_COLUMNS.copy()

            # Add only age columns for actual dependents (up to 11 max)
            for i in range(min(depx, 11)):
                age_col = f"age{i+1}"
                dynamic_columns.append(age_col)

            # Add income columns (but exclude TAXSIM32 columns since TAXSIM-35 uses individual ages)
            dynamic_columns.extend(self.INCOME_COLUMNS)

            # Create row data with only needed columns
            row_data = {}
            for col in dynamic_columns:
                value = row.get(col, 0)

                # Convert dependent ages of 0 to 10 for TAXSIM compatibility
                if col.startswith("age") and col[3:].isdigit() and value <= 0:
                    value = 10

                row_data[col] = value

            result_rows.append(row_data)

        # Convert to DataFrame and store dynamic columns
        if result_rows:
            result_df = pd.DataFrame(result_rows)
            self._dynamic_columns = result_df.columns.tolist()
            return result_df
        else:
            # Fallback to all columns if no data
            return formatted_df[self.ALL_COLUMNS].copy()

    def _create_taxsim_input_file(self, df: pd.DataFrame) -> str:
        """Create properly formatted TAXSIM input file"""
        formatted_df = self._format_input_for_taxsim(df)

        # Create temporary input file
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)

        # Write CSV format that TAXSIM expects
        with open(temp_file.name, "w") as f:
            # Use dynamic columns if available, otherwise fall back to ALL_COLUMNS
            columns_to_use = getattr(self, "_dynamic_columns", self.ALL_COLUMNS)

            # Write header
            f.write(",".join(columns_to_use) + "\n")

            # Write data rows
            for _, row in formatted_df.iterrows():
                # Convert each value to string, handling NaN values properly
                values = []
                for col in columns_to_use:
                    val = row[col]
                    if pd.isna(val):
                        values.append(
                            "0"
                        )  # Use 0 for NaN values instead of empty string
                    else:
                        values.append(str(val))
                f.write(",".join(values) + "\n")

        return temp_file.name

    def _execute_taxsim(self, input_file: str, output_file: str):
        """Execute TAXSIM with proper OS-specific command"""
        system = platform.system().lower()

        if system != "windows":
            cmd = f'cat "{input_file}" | "{str(self.taxsim_path)}" > "{output_file}"'
        else:
            cmd = f'cmd.exe /c "type "{input_file}" | "{str(self.taxsim_path)}" > "{output_file}""'

        # Set up Windows-specific flags
        creation_flags = 0
        if system == "windows":
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                creation_flags = 0x00000008  # DETACHED_PROCESS

        # Set up environment to include Homebrew path on macOS
        env = os.environ.copy()
        if system == "darwin":
            # Ensure Homebrew paths are included for dynamic library resolution
            homebrew_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
            current_path = env.get("PATH", "")

            # Add Homebrew paths to the beginning if not already present
            for homebrew_path in reversed(homebrew_paths):
                if homebrew_path not in current_path:
                    current_path = f"{homebrew_path}:{current_path}"

            env["PATH"] = current_path

        # Execute TAXSIM
        process = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            creationflags=creation_flags if system == "windows" else 0,
        )

        if process.returncode != 0:
            raise Exception(f"TAXSIM execution failed: {process.stderr}")

        return process

    def _parse_taxsim_output(self, output_file: str) -> pd.DataFrame:
        """Parse TAXSIM output file into DataFrame"""
        try:
            # First, try to read as CSV (for idtl values like 2)
            output_df = pd.read_csv(output_file)

            # Convert numeric columns
            for col in output_df.columns:
                if col != "state_name":  # Keep state name as string
                    output_df[col] = pd.to_numeric(output_df[col], errors="coerce")

            return output_df

        except Exception as e:
            # If CSV parsing fails, check if it's verbose output (idtl=5)
            if os.path.exists(output_file):
                with open(output_file, "r") as f:
                    raw_output = f.read()

                # Try to parse verbose output format
                try:
                    return self._parse_verbose_taxsim_output(raw_output)
                except Exception as verbose_error:
                    raise Exception(
                        f"Failed to parse TAXSIM output as both CSV and verbose format.\n"
                        f"CSV error: {e}\n"
                        f"Verbose parsing error: {verbose_error}\n"
                        f"Raw output:\n{raw_output}"
                    )
            else:
                raise Exception(f"TAXSIM output file not found: {output_file}")

    def _parse_verbose_taxsim_output(self, raw_output: str) -> pd.DataFrame:
        """Parse verbose TAXSIM output (idtl=5) into DataFrame"""
        import re

        lines = raw_output.strip().split("\n")
        records = []

        # Find the Basic Output section only
        in_basic_output = False
        basic_output_lines = []

        for line in lines:
            if "Basic Output:" in line:
                in_basic_output = True
                continue
            elif in_basic_output and ("Marginal Rates" in line or line.strip() == ""):
                # End of basic output section when we hit marginal rates or empty line
                if "Marginal Rates" in line:
                    break
            elif in_basic_output and line.strip():
                basic_output_lines.append(line)

        # Parse the basic output section
        record = {}
        for line in basic_output_lines:
            line = line.strip()
            if not line:
                continue

            # Parse key-value pairs from the basic output
            # Format: "      1. Record ID:                12323."
            match = re.match(r"\s*(\d+)\.\s*([^:]+):\s*(.+)", line)
            if match:
                field_num = int(match.group(1))
                field_name = match.group(2).strip()
                field_value = match.group(3).strip()

                # Extract numeric value, removing state name if present
                value_match = re.search(r"([\d.-]+)", field_value)
                if value_match:
                    numeric_value = float(value_match.group(1))

                    # Map to standard TAXSIM column names (only from Basic Output section)
                    if field_num == 1:  # Record ID
                        record["taxsimid"] = numeric_value
                    elif field_num == 2:  # Year
                        record["year"] = numeric_value
                    elif field_num == 3:  # State
                        record["state"] = numeric_value
                        # Extract state name if present
                        state_match = re.search(r"\d+\s+(\w+)", field_value)
                        if state_match:
                            record["state_name"] = state_match.group(1)
                    elif field_num == 4:  # Federal IIT Liability
                        record["fiitax"] = numeric_value
                    elif field_num == 5:  # State IIT Liability
                        record["siitax"] = numeric_value
                    elif field_num == 6:  # SS Payroll Tax Liability
                        record["fica"] = numeric_value

        # Now parse the Marginal Rates section
        in_marginal_rates = False
        for line in lines:
            if "Marginal Rates wrt  Earner" in line:
                in_marginal_rates = True
                continue
            elif in_marginal_rates and "Federal Tax Calculation:" in line:
                break
            elif in_marginal_rates and line.strip():
                match = re.match(r"\s*(\d+)\.\s*([^:]+):\s*(.+)", line)
                if match:
                    field_num = int(match.group(1))
                    field_value = match.group(3).strip()

                    value_match = re.search(r"([\d.-]+)", field_value)
                    if value_match:
                        numeric_value = float(value_match.group(1))

                        if field_num == 7:  # Federal Marginal Rate
                            record["frate"] = numeric_value
                        elif field_num == 8:  # State Marginal Rate
                            record["srate"] = numeric_value
                        elif field_num == 9:  # Taxpayer SS Rate
                            record["ficar"] = numeric_value

        if not record:
            raise Exception("No valid record found in verbose TAXSIM output")

        # Convert to DataFrame
        df = pd.DataFrame([record])

        # Ensure all numeric columns are properly typed
        for col in df.columns:
            if col != "state_name":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def run(self, show_progress: bool = True) -> pd.DataFrame:
        """
        Run TAXSIM on the input data

        Args:
            show_progress: Whether to show progress information

        Returns:
            DataFrame with TAXSIM results
        """
        if show_progress:
            print(f"Running TAXSIM on {len(self.input_df)} records")

        # Create temporary files
        input_file = None
        output_file = None

        try:
            # Create formatted input file
            input_file = self._create_taxsim_input_file(self.input_df)

            # Create temporary output file
            output_fd, output_file = tempfile.mkstemp(suffix=".txt")
            os.close(output_fd)  # Close file descriptor, keep filename

            # Execute TAXSIM
            if show_progress:
                print(f"Processing TAXSIM: {len(self.input_df)} records", end="\r")

            self._execute_taxsim(input_file, output_file)

            # Parse results
            results_df = self._parse_taxsim_output(output_file)

            if show_progress:
                print(f"\nTAXSIM completed successfully")

            return results_df

        finally:
            # Clean up temporary files
            for temp_file in [input_file, output_file]:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except OSError:
                        pass  # Ignore cleanup errors

    def save_results(self, output_path: str, results_df: pd.DataFrame = None):
        """Save TAXSIM results to file"""
        if results_df is None:
            results_df = self.run()

        results_df.to_csv(output_path, index=False)
        print(f"TAXSIM results saved to: {output_path}")


class TaxsimExecutionError(Exception):
    """Custom exception for TAXSIM execution errors"""

    pass
