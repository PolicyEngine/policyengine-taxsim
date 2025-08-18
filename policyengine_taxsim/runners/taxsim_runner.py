import os
import platform
import subprocess
import tempfile
from pathlib import Path
import pandas as pd
from .base_runner import BaseTaxRunner


class TaxsimRunner(BaseTaxRunner):
    """Clean TAXSIMTEST executable runner"""

    # TAXSIM column definitions based on official NBER documentation
    # https://taxsim.nber.org/taxsimtest/
    REQUIRED_COLUMNS = [
        "taxsimid",     # 1. Case ID
        "year",         # 2. Tax year  
        "state",        # 3. State code
        "mstat",        # 4. Marital status
        "page",         # 5. Primary taxpayer age
        "sage",         # 5. Spouse age
        "depx",         # 6. Number of dependents
    ]

    # Dependent ages come after depx according to official docs
    DEPENDENT_AGE_COLUMNS = [
        "age1", "age2", "age3", "age4", "age5", "age6", 
        "age7", "age8", "age9", "age10", "age11"
    ]

    # Income and deduction columns
    INCOME_COLUMNS = [
        "pwages",       # Primary wages
        "swages",       # Spouse wages  
        "psemp",        # Primary self-employment
        "ssemp",        # Spouse self-employment
        "dividends",    # Dividend income
        "intrec",       # Interest received
        "stcg",         # Short-term capital gains
        "ltcg",         # Long-term capital gains
        "otherprop",    # Other property income
        "nonprop",      # Other non-property income
        "pensions",     # Taxable pensions
        "gssi",         # Gross social security
        "pui",          # Primary unemployment insurance
        "sui",          # Spouse unemployment insurance
        "transfers",    # Non-taxable transfers
        "rentpaid",     # Rent paid
        "proptax",      # Property taxes
        "otheritem",    # Other itemized deductions
        "childcare",    # Child care expenses
        "mortgage",     # Mortgage interest
        "scorp",        # S-Corp profits
        "idtl",         # Output control
    ]

    ALL_COLUMNS = REQUIRED_COLUMNS + DEPENDENT_AGE_COLUMNS + INCOME_COLUMNS

    def __init__(self, input_df: pd.DataFrame, taxsim_path: str = None):
        super().__init__(input_df)
        self.taxsim_path = taxsim_path or self._detect_taxsim_executable()
        self._validate_executable()

    def _detect_taxsim_executable(self) -> Path:
        """Detect correct TAXSIM executable based on OS"""
        system = platform.system().lower()

        if system == "darwin":
            exe_name = "taxsimtest-osx.exe"
        elif system == "windows":
            exe_name = "taxsimtest-windows.exe"
        elif system == "linux":
            exe_name = "taxsimtest-linux.exe"
        else:
            raise OSError(f"Unsupported operating system: {system}")

        # Look for executable in resources directory
        taxsim_path = Path("resources") / "taxsimtest" / exe_name
        return taxsim_path

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
        
        # Ensure all columns exist with default values
        for col in self.ALL_COLUMNS:
            if col not in formatted_df.columns:
                formatted_df[col] = 0
        
        # Create dynamic column list based on number of dependents
        result_rows = []
        
        for _, row in formatted_df.iterrows():
            depx = int(row.get('depx', 0))
            
            # Start with required columns
            dynamic_columns = self.REQUIRED_COLUMNS.copy()
            
            # Add only age columns for actual dependents (up to 11 max)
            for i in range(min(depx, 11)):
                age_col = f"age{i+1}"
                dynamic_columns.append(age_col)
            
            # Add income columns
            dynamic_columns.extend(self.INCOME_COLUMNS)
            
            # Create row data with only needed columns
            row_data = {}
            for col in dynamic_columns:
                row_data[col] = row.get(col, 0)
            
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
            columns_to_use = getattr(self, '_dynamic_columns', self.ALL_COLUMNS)
            
            # Write header
            f.write(",".join(columns_to_use) + "\n")

            # Write data rows
            for _, row in formatted_df.iterrows():
                f.write(",".join(str(row[col]) for col in columns_to_use) + "\n")

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

        # Execute TAXSIM
        process = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            creationflags=creation_flags if system == "windows" else 0,
        )

        if process.returncode != 0:
            raise Exception(f"TAXSIM execution failed: {process.stderr}")

        return process

    def _parse_taxsim_output(self, output_file: str) -> pd.DataFrame:
        """Parse TAXSIM output file into DataFrame"""
        try:
            # TAXSIM outputs CSV format
            output_df = pd.read_csv(output_file)

            # Convert numeric columns
            for col in output_df.columns:
                if col != "state_name":  # Keep state name as string
                    output_df[col] = pd.to_numeric(output_df[col], errors="coerce")

            return output_df

        except Exception as e:
            # If parsing fails, try to read raw output for debugging
            if os.path.exists(output_file):
                with open(output_file, "r") as f:
                    raw_output = f.read()
                raise Exception(
                    f"Failed to parse TAXSIM output: {e}\nRaw output:\n{raw_output}"
                )
            else:
                raise Exception(f"TAXSIM output file not found: {output_file}")

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
