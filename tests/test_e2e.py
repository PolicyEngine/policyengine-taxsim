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
        self.project_root = Path(__file__).parent.parent
        self.taxsim_dir = self.project_root / "resources" / "taxsim35"
        self.output_dir = self.project_root / "output"
        self.output_dir.mkdir(exist_ok=True)

        # Determine the correct TAXSIM executable based on the OS
        system = platform.system().lower()
        if system == "darwin":
            self.taxsim_exe = "taxsim35-osx.exe"
        elif system == "windows":
            self.taxsim_exe = "taxsim35-windows.exe"
        elif system == "linux":
            self.taxsim_exe = "taxsim35-unix.exe"
        else:
            raise OSError(f"Unsupported operating system: {system}")

        self.input_file = self.taxsim_dir / "taxsim_input.csv"

    def test_generate_policyengine_taxsim(self):
        output_file = self.output_dir / "policyengine_taxsim_output.csv"

        cmd = f"{sys.executable} {self.project_root}/policyengine_taxsim/cli.py {self.input_file} -o {output_file}"
        process = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )

        print(f"PolicyEngine TAXSIM CLI output:\n{process.stdout}")
        if process.returncode != 0:
            print(
                f"PolicyEngine TAXSIM CLI failed with error:\n{process.stderr}"
            )
            raise Exception(
                f"PolicyEngine TAXSIM CLI failed: {process.returncode}"
            )

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_generate_taxsim_output(self):
        output_file = self.output_dir / "taxsim35_output.csv"

        taxsim_path = self.taxsim_dir / self.taxsim_exe

        if platform.system().lower() != "windows":
            # Make the file executable on Unix-like systems
            os.chmod(taxsim_path, 0o755)

        cmd = f"{taxsim_path} < {self.input_file} > {output_file}"
        process = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )

        print(f"TAXSIM35 output:\n{process.stdout}")
        if process.returncode != 0:
            print(f"TAXSIM35 failed with error:\n{process.stderr}")
            raise Exception(f"TAXSIM35 failed: {process.returncode}")

        self.assertTrue(output_file.is_file())
        print(f"Content of {output_file}:")
        with open(output_file, "r") as f:
            print(f.read())

    def test_match_both_output(self):
        taxsim35_csv = pd.read_csv(self.output_dir / "taxsim35_output.csv")
        pe_taxsim_csv = pd.read_csv(
            self.output_dir / "policyengine_taxsim_output.csv"
        )

        print("TAXSIM35 output:")
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
        taxsim35_csv = taxsim35_csv.sort_values("taxsimid").reset_index(
            drop=True
        )
        pe_taxsim_csv = pe_taxsim_csv.sort_values("taxsimid").reset_index(
            drop=True
        )

        # Convert numeric columns to float
        numeric_columns = taxsim35_csv.select_dtypes(
            include=["number"]
        ).columns
        for col in numeric_columns:
            taxsim35_csv[col] = pd.to_numeric(
                taxsim35_csv[col], errors="coerce"
            )
            pe_taxsim_csv[col] = pd.to_numeric(
                pe_taxsim_csv[col], errors="coerce"
            )

        # Compare numeric columns with a small tolerance
        is_close = np.allclose(
            taxsim35_csv[numeric_columns],
            pe_taxsim_csv[numeric_columns],
            rtol=1e-5,
            atol=1e-8,
            equal_nan=True,
        )

        # Compare non-numeric columns exactly
        non_numeric_columns = taxsim35_csv.select_dtypes(
            exclude=["number"]
        ).columns
        is_exact = (
            (
                taxsim35_csv[non_numeric_columns]
                == pe_taxsim_csv[non_numeric_columns]
            )
            .all()
            .all()
        )

        is_matched = is_close and is_exact

        if not is_matched:
            print("\nDifferences found:")
            for col in common_columns:
                if not np.allclose(
                    taxsim35_csv[col],
                    pe_taxsim_csv[col],
                    rtol=1e-5,
                    atol=1e-8,
                    equal_nan=True,
                ):
                    print(f"\nDifferences in {col}:")
                    print(
                        pd.DataFrame(
                            {
                                "TAXSIM35": taxsim35_csv[col],
                                "PolicyEngine": pe_taxsim_csv[col],
                                "Difference": taxsim35_csv[col]
                                - pe_taxsim_csv[col],
                            }
                        )
                    )

        self.assertTrue(is_matched, "Outputs do not match")


if __name__ == "__main__":
    unittest.main()
