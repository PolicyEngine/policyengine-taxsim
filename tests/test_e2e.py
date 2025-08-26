import unittest
import os
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
import platform
import sys


class E2ETest(unittest.TestCase):

    def setUp(self) -> None:
        import importlib.resources as pkg_resources
        import policyengine_taxsim
        from importlib.metadata import distribution

        self.SINGLE_HOUSEHOLD_INPUT = "taxsim_input_single_household.csv"
        self.JOINT_HOUSEHOLD_INPUT = "taxsim_input_joint_household.csv"
        self.HOUSEHOLD_WITH_DEPENDENT_INPUT = "taxsim_input_with_1_dep.csv"
        self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_INPUT = (
            "taxsim_input_with_1_dep_single_parent.csv"
        )

        self.SINGLE_HOUSEHOLD_PE_TAXSIM_OUTPUT = (
            "policyengine_taxsim_single_household_output.csv"
        )
        self.SINGLE_HOUSEHOLD_TAXSIM35_OUTPUT = "taxsim35_single_household_output.csv"

        self.JOINT_HOUSEHOLD_PE_TAXSIM_OUTPUT = (
            "policyengine_taxsim_joint_household_output.csv"
        )
        self.JOINT_HOUSEHOLD_TAXSIM35_OUTPUT = "taxsim35_joint_household_output.csv"

        self.HOUSEHOLD_WITH_DEPENDENT_PE_TAXSIM_OUTPUT = (
            "policyengine_taxsim_household_with_dependent_output.csv"
        )
        self.HOUSEHOLD_WITH_DEPENDENT_TAXSIM35_OUTPUT = (
            "taxsim35_household_with_dependent_output.csv"
        )

        self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_PE_TAXSIM_OUTPUT = (
            "policyengine_taxsim_household_with_dependent_single_parent_output.csv"
        )
        self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_TAXSIM35_OUTPUT = (
            "taxsim35_household_with_dependent_single_parent_output.csv"
        )

        # Get the correct path to shared data
        dist = distribution("policyengine-taxsim")
        # Print for debugging
        print(f"Distribution location: {dist.locate_file('share')}")

        # Try different methods to locate the file
        possible_paths = [
            Path(dist.locate_file("share")) / "policyengine_taxsim" / "taxsim35",
            Path(sys.prefix) / "share" / "policyengine_taxsim" / "taxsim35",
            Path(policyengine_taxsim.__file__).parent.parent
            / "share"
            / "policyengine_taxsim"
            / "taxsim35",
        ]

        # Find the first path that exists and contains our files
        for path in possible_paths:
            if (path / self.SINGLE_HOUSEHOLD_INPUT).exists():
                self.taxsim_dir = path
                break
        else:
            print("Searched in the following locations:")
            for path in possible_paths:
                print(f"  {path}")
            raise FileNotFoundError("Could not find taxsim directory")

        self.output_dir = Path.cwd() / "output"
        self.output_dir.mkdir(exist_ok=True)

        # Get CLI path
        self.cli_path = Path(policyengine_taxsim.__file__).parent / "cli.py"

        # Determine the correct TAXSIM executable based on the OS
        system = platform.system().lower()
        if system == "darwin":
            self.taxsim_exe = "taxsim35-osx.exe"
        elif system == "windows":
            self.taxsim_exe = "taxsim-latest-windows.exe"
        elif system == "linux":
            self.taxsim_exe = "taxsim35-unix.exe"
        else:
            raise OSError(f"Unsupported operating system: {system}")

        self.input_file_single_household = self.taxsim_dir / self.SINGLE_HOUSEHOLD_INPUT
        self.input_file_joint_household = self.taxsim_dir / self.JOINT_HOUSEHOLD_INPUT
        self.input_file_household_with_dependent = (
            self.taxsim_dir / self.HOUSEHOLD_WITH_DEPENDENT_INPUT
        )
        self.input_file_household_with_dependent_single_parent = (
            self.taxsim_dir / self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_INPUT
        )

        if self.input_file_single_household.exists():
            print(
                f"Input File is Readable: {os.access(self.input_file_single_household, os.R_OK)}"
            )

    def generate_pe_taxsim_output(self, cmd):
        creation_flags = 0
        if platform.system().lower() == "windows":
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                # For Python < 3.11 on Windows
                # DETACHED_PROCESS = 0x00000008
                creation_flags = 0x00000008
        process = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            creationflags=creation_flags,
        )
        print(f"PolicyEngine TAXSIM CLI output:\n{process.stdout}")
        if process.returncode != 0:
            print(f"PolicyEngine TAXSIM CLI failed with error:\n{process.stderr}")
            raise Exception(f"PolicyEngine TAXSIM CLI failed: {process.returncode}")

    def generate_taxsim35_output(self, taxsim35_input_file, output_file):
        import tempfile
        import shutil

        taxsim_path = self.taxsim_dir / self.taxsim_exe

        # Create a temporary directory for execution
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy executable and input to temp directory
            temp_exe = Path(temp_dir) / self.taxsim_exe
            temp_input = Path(temp_dir) / "input.csv"

            shutil.copy2(taxsim_path, temp_exe)
            shutil.copy2(taxsim35_input_file, temp_input)

            if platform.system().lower() != "windows":
                os.chmod(temp_exe, 0o755)
                cmd = f'cat "{str(temp_input)}" | "{str(temp_exe)}" > "{str(output_file)}"'
            else:
                # Windows specific handling
                cmd = f'cmd.exe /c "type "{str(temp_input)}" | "{str(temp_exe)}" > "{str(output_file)}""'

            creation_flags = 0
            if platform.system().lower() == "windows":
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    creation_flags = subprocess.CREATE_NO_WINDOW
                else:
                    # For Python < 3.11 on Windows
                    # DETACHED_PROCESS = 0x00000008
                    creation_flags = 0x00000008

            process = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                creationflags=(
                    creation_flags if platform.system().lower() == "windows" else 0
                ),
            )

            print(f"TAXSIM35 output:\n{process.stdout}")
            if process.returncode != 0:
                print(f"TAXSIM35 failed with error:\n{process.stderr}")
                raise Exception(f"TAXSIM35 failed: {process.returncode}")

    def test_generate_policyengine_taxsim_single_household_output(self):
        output_file = self.output_dir / self.SINGLE_HOUSEHOLD_PE_TAXSIM_OUTPUT

        # Use list form and absolute paths
        cmd = [
            sys.executable,
            str(self.cli_path.absolute()),
            "policyengine",
            str(self.input_file_single_household.absolute()),
            "-o",
            str(output_file.absolute()),
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(cmd)}")

        self.generate_pe_taxsim_output(cmd)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_generate_taxsim35_single_household_output(self):

        output_file = self.output_dir / self.SINGLE_HOUSEHOLD_TAXSIM35_OUTPUT

        self.generate_taxsim35_output(self.input_file_single_household, output_file)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_match_single_household_output(self):
        taxsim35_csv = pd.read_csv(
            self.output_dir / self.SINGLE_HOUSEHOLD_TAXSIM35_OUTPUT
        )
        pe_taxsim_csv = pd.read_csv(
            self.output_dir / self.SINGLE_HOUSEHOLD_PE_TAXSIM_OUTPUT
        )
        input_csv = pd.read_csv(self.input_file_single_household)

        # Ensure both DataFrames have the same columns
        common_columns = set(taxsim35_csv.columns) & set(pe_taxsim_csv.columns)
        taxsim35_csv = taxsim35_csv[list(common_columns)]
        pe_taxsim_csv = pe_taxsim_csv[list(common_columns)]

        # Ensure both DataFrames have the same column names
        taxsim35_csv.columns = taxsim35_csv.columns.str.lower()
        pe_taxsim_csv.columns = pe_taxsim_csv.columns.str.lower()

        # Sort both DataFrames by taxsimid to ensure rows are in the same order
        taxsim35_csv = taxsim35_csv.sort_values("taxsimid").reset_index(drop=True)
        pe_taxsim_csv = pe_taxsim_csv.sort_values("taxsimid").reset_index(drop=True)
        input_csv = input_csv.sort_values("taxsimid").reset_index(drop=True)

        # Convert numeric columns to float
        numeric_columns = taxsim35_csv.select_dtypes(include=["number"]).columns
        for col in numeric_columns:
            taxsim35_csv[col] = pd.to_numeric(taxsim35_csv[col], errors="coerce")
            pe_taxsim_csv[col] = pd.to_numeric(pe_taxsim_csv[col], errors="coerce")

        # Compare
        standard_output_cols = ["year", "fiitax", "siitax"]
        full_output_cols = standard_output_cols + [
            "tfica" "v10",  # state_agi
            "v13",
            "v18",
            "v19",
            "v26",
            "v28",
            "v34",
            "v45",
        ]

        # Determine which columns to check based on idtl value
        columns_to_check = (
            full_output_cols if (input_csv["idtl"] == 2).any() else standard_output_cols
        )

        # Compare all relevant columns at once
        comparison_results = {}
        for col in columns_to_check:
            if col in common_columns:
                # matches = (taxsim35_csv[col] == pe_taxsim_csv[col]).all()
                matches = np.isclose(
                    taxsim35_csv[col],
                    pe_taxsim_csv[col],
                    rtol=0.01,  # relative tolerance (0.001%)
                    atol=0.1,  # absolute tolerance
                ).all()
                comparison_results[col] = matches
                if not matches:
                    print(f"Mismatch in column {col}:")
                    print(f"TAXSIM35 values: {taxsim35_csv[col].values}")
                    print(f"PolicyEngine values: {pe_taxsim_csv[col].values}")

        # Assert all columns match
        all_matched = all(comparison_results.values())
        self.assertTrue(
            all_matched,
            f"Columns with missmatches: {[col for col, matched in comparison_results.items() if not matched]}",
        )

    def test_generate_policyengine_taxsim_joint_household_output(self):
        output_file = self.output_dir / self.JOINT_HOUSEHOLD_PE_TAXSIM_OUTPUT

        # Use list form and absolute paths
        cmd = [
            sys.executable,
            str(self.cli_path.absolute()),
            "policyengine",
            str(self.input_file_joint_household.absolute()),
            "-o",
            str(output_file.absolute()),
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(cmd)}")

        self.generate_pe_taxsim_output(cmd)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_generate_taxsim35_joint_household_output(self):

        output_file = self.output_dir / self.JOINT_HOUSEHOLD_TAXSIM35_OUTPUT
        self.generate_taxsim35_output(self.input_file_joint_household, output_file)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_match_joint_household_output(self):
        taxsim35_csv = pd.read_csv(
            self.output_dir / self.JOINT_HOUSEHOLD_TAXSIM35_OUTPUT
        )
        pe_taxsim_csv = pd.read_csv(
            self.output_dir / self.JOINT_HOUSEHOLD_PE_TAXSIM_OUTPUT
        )
        input_csv = pd.read_csv(self.input_file_joint_household)

        print("Input CSV:")
        print(input_csv)
        print("\nTAXSIM35 output:")
        print(taxsim35_csv)
        print("\nPolicyEngine TAXSIM output:")
        print(pe_taxsim_csv)

        # Ensure both DataFrames have the same columns
        common_columns = set(taxsim35_csv.columns) & set(pe_taxsim_csv.columns)
        taxsim35_csv = taxsim35_csv[list(common_columns)]
        pe_taxsim_csv = pe_taxsim_csv[list(common_columns)]

        # Ensure both DataFrames have the same column names
        taxsim35_csv.columns = taxsim35_csv.columns.str.lower()
        pe_taxsim_csv.columns = pe_taxsim_csv.columns.str.lower()

        # Sort both DataFrames by taxsimid to ensure rows are in the same order
        taxsim35_csv = taxsim35_csv.sort_values("taxsimid").reset_index(drop=True)
        pe_taxsim_csv = pe_taxsim_csv.sort_values("taxsimid").reset_index(drop=True)
        input_csv = input_csv.sort_values("taxsimid").reset_index(drop=True)

        # Convert numeric columns to float
        numeric_columns = taxsim35_csv.select_dtypes(include=["number"]).columns
        for col in numeric_columns:
            taxsim35_csv[col] = pd.to_numeric(taxsim35_csv[col], errors="coerce")
            pe_taxsim_csv[col] = pd.to_numeric(pe_taxsim_csv[col], errors="coerce")

        # Compare
        standard_output_cols = [
            "year",
            # "fiitax",
            "siitax",
        ]
        full_output_cols = standard_output_cols + [
            # "tfica"
            # "v10",  # state_agi
            # "v13",
            # "v18",
            # "v19",
            # "v26",
            # "v28",
            # "v34",
            # "v45",
        ]

        # Determine which columns to check based on idtl value
        columns_to_check = (
            full_output_cols if (input_csv["idtl"] == 2).any() else standard_output_cols
        )

        # Compare all relevant columns at once
        comparison_results = {}
        for col in columns_to_check:
            if col in common_columns:
                matches = (taxsim35_csv[col] == pe_taxsim_csv[col]).all()
                comparison_results[col] = matches
                if not matches:
                    print(f"Mismatch in column {col}:")
                    print(f"TAXSIM35 values: {taxsim35_csv[col].values}")
                    print(f"PolicyEngine values: {pe_taxsim_csv[col].values}")

        # Assert all columns match
        all_matched = all(comparison_results.values())
        self.assertTrue(
            all_matched,
            f"Columns with missmatches: {[col for col, matched in comparison_results.items() if not matched]}",
        )

    def test_generate_policyengine_taxsim_household_with_dependent_output(self):
        output_file = self.output_dir / self.HOUSEHOLD_WITH_DEPENDENT_PE_TAXSIM_OUTPUT

        # Use list form and absolute paths
        cmd = [
            sys.executable,
            str(self.cli_path.absolute()),
            "policyengine",
            str(self.input_file_household_with_dependent.absolute()),
            "-o",
            str(output_file.absolute()),
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(cmd)}")

        self.generate_pe_taxsim_output(cmd)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_generate_taxsim35_household_with_dependent_output(self):
        output_file = self.output_dir / self.HOUSEHOLD_WITH_DEPENDENT_TAXSIM35_OUTPUT
        self.generate_taxsim35_output(
            self.input_file_household_with_dependent, output_file
        )

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_match_household_with_dependent_output(self):
        taxsim35_csv = pd.read_csv(
            self.output_dir / self.HOUSEHOLD_WITH_DEPENDENT_TAXSIM35_OUTPUT
        )
        pe_taxsim_csv = pd.read_csv(
            self.output_dir / self.HOUSEHOLD_WITH_DEPENDENT_PE_TAXSIM_OUTPUT
        )
        input_csv = pd.read_csv(self.input_file_household_with_dependent)

        print("Input CSV:")
        print(input_csv)
        print("\nTAXSIM35 output:")
        print(taxsim35_csv)
        print("\nPolicyEngine TAXSIM output:")
        print(pe_taxsim_csv)

        # Ensure both DataFrames have the same columns
        common_columns = set(taxsim35_csv.columns) & set(pe_taxsim_csv.columns)
        taxsim35_csv = taxsim35_csv[list(common_columns)]
        pe_taxsim_csv = pe_taxsim_csv[list(common_columns)]

        # Ensure both DataFrames have the same column names
        taxsim35_csv.columns = taxsim35_csv.columns.str.lower()
        pe_taxsim_csv.columns = pe_taxsim_csv.columns.str.lower()

        # Sort both DataFrames by taxsimid to ensure rows are in the same order
        taxsim35_csv = taxsim35_csv.sort_values("taxsimid").reset_index(drop=True)
        pe_taxsim_csv = pe_taxsim_csv.sort_values("taxsimid").reset_index(drop=True)
        input_csv = input_csv.sort_values("taxsimid").reset_index(drop=True)

        # Convert numeric columns to float
        numeric_columns = taxsim35_csv.select_dtypes(include=["number"]).columns
        for col in numeric_columns:
            taxsim35_csv[col] = pd.to_numeric(taxsim35_csv[col], errors="coerce")
            pe_taxsim_csv[col] = pd.to_numeric(pe_taxsim_csv[col], errors="coerce")

        # Compare
        standard_output_cols = [
            "year",
            # "fiitax",
            "siitax",
        ]
        full_output_cols = standard_output_cols + [
            # "tfica"
            # "v10",  # state_agi
            # "v13",
            # "v18",
            # "v19",
            # "v26",
            # "v28",
            # "v34",
            # "v45",
        ]

        # Determine which columns to check based on idtl value
        columns_to_check = (
            full_output_cols if (input_csv["idtl"] == 2).any() else standard_output_cols
        )

        # Compare all relevant columns at once
        comparison_results = {}
        for col in columns_to_check:
            if col in common_columns:
                matches = (taxsim35_csv[col] == pe_taxsim_csv[col]).all()
                comparison_results[col] = matches
                if not matches:
                    print(f"Mismatch in column {col}:")
                    print(f"TAXSIM35 values: {taxsim35_csv[col].values}")
                    print(f"PolicyEngine values: {pe_taxsim_csv[col].values}")

        # Assert all columns match
        all_matched = all(comparison_results.values())
        self.assertTrue(
            all_matched,
            f"Columns with missmatches: {[col for col, matched in comparison_results.items() if not matched]}",
        )

    def test_generate_policyengine_taxsim_household_with_dependent_single_parent_output(
        self,
    ):
        output_file = (
            self.output_dir
            / self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_PE_TAXSIM_OUTPUT
        )

        # Use list form and absolute paths
        cmd = [
            sys.executable,
            str(self.cli_path.absolute()),
            "policyengine",
            str(self.input_file_household_with_dependent_single_parent.absolute()),
            "-o",
            str(output_file.absolute()),
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(cmd)}")

        self.generate_pe_taxsim_output(cmd)

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_generate_taxsim35_household_with_dependent_single_parent_output(self):
        output_file = (
            self.output_dir
            / self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_TAXSIM35_OUTPUT
        )
        self.generate_taxsim35_output(
            self.input_file_household_with_dependent_single_parent, output_file
        )
        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_match_household_with_dependent_single_parent_output(self):
        taxsim35_csv = pd.read_csv(
            self.output_dir
            / self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_TAXSIM35_OUTPUT
        )
        pe_taxsim_csv = pd.read_csv(
            self.output_dir
            / self.HOUSEHOLD_WITH_DEPENDENT_SINGLE_PARENT_PE_TAXSIM_OUTPUT
        )
        input_csv = pd.read_csv(self.input_file_household_with_dependent_single_parent)

        print("Input CSV:")
        print(input_csv)
        print("\nTAXSIM35 output:")
        print(taxsim35_csv)
        print("\nPolicyEngine TAXSIM output:")
        print(pe_taxsim_csv)

        # Ensure both DataFrames have the same columns
        common_columns = set(taxsim35_csv.columns) & set(pe_taxsim_csv.columns)
        taxsim35_csv = taxsim35_csv[list(common_columns)]
        pe_taxsim_csv = pe_taxsim_csv[list(common_columns)]

        # Ensure both DataFrames have the same column names
        taxsim35_csv.columns = taxsim35_csv.columns.str.lower()
        pe_taxsim_csv.columns = pe_taxsim_csv.columns.str.lower()

        # Sort both DataFrames by taxsimid to ensure rows are in the same order
        taxsim35_csv = taxsim35_csv.sort_values("taxsimid").reset_index(drop=True)
        pe_taxsim_csv = pe_taxsim_csv.sort_values("taxsimid").reset_index(drop=True)
        input_csv = input_csv.sort_values("taxsimid").reset_index(drop=True)

        # Convert numeric columns to float
        numeric_columns = taxsim35_csv.select_dtypes(include=["number"]).columns
        for col in numeric_columns:
            taxsim35_csv[col] = pd.to_numeric(taxsim35_csv[col], errors="coerce")
            pe_taxsim_csv[col] = pd.to_numeric(pe_taxsim_csv[col], errors="coerce")

        # Compare
        standard_output_cols = [
            "year",
            # "fiitax",
            "siitax",
        ]
        full_output_cols = standard_output_cols + [
            # "tfica"
            # "v10",  # state_agi
            # "v13",
            # "v18",
            # "v19",
            # "v26",
            # "v28",
            # "v34",
            # "v45",
        ]

        # Determine which columns to check based on idtl value
        columns_to_check = (
            full_output_cols if (input_csv["idtl"] == 2).any() else standard_output_cols
        )

        # Compare all relevant columns at once
        comparison_results = {}
        for col in columns_to_check:
            if col in common_columns:
                matches = (taxsim35_csv[col] == pe_taxsim_csv[col]).all()
                comparison_results[col] = matches
                if not matches:
                    print(f"Mismatch in column {col}:")
                    print(f"TAXSIM35 values: {taxsim35_csv[col].values}")
                    print(f"PolicyEngine values: {pe_taxsim_csv[col].values}")

        # Assert all columns match
        all_matched = all(comparison_results.values())
        self.assertTrue(
            all_matched,
            f"Columns with mismatches: {[col for col, matched in comparison_results.items() if not matched]}",
        )


if __name__ == "__main__":
    unittest.main()
