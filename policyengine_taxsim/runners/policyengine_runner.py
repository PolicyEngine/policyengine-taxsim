import pandas as pd
from pathlib import Path
from io import StringIO
from .base_runner import BaseTaxRunner

# Import the core PolicyEngine functions
try:
    from ..core.input_mapper import generate_household
    from ..core.output_mapper import export_household
except ImportError:
    from policyengine_taxsim.core.input_mapper import generate_household
    from policyengine_taxsim.core.output_mapper import export_household


class PolicyEngineRunner(BaseTaxRunner):
    """PolicyEngine tax calculator runner - preserves cli.py logic"""
    
    def __init__(self, input_df: pd.DataFrame, logs: bool = False, disable_salt: bool = False):
        super().__init__(input_df)
        self.logs = logs
        self.disable_salt = disable_salt
    
    def run(self, show_progress: bool = True) -> pd.DataFrame:
        """
        Run PolicyEngine on all records and return DataFrame
        
        This version returns a standardized DataFrame for comparison purposes.
        """
        if show_progress:
            print(f"Running PolicyEngine on {len(self.input_df)} records")
        
        results = []
        total_records = len(self.input_df)
        
        for i, (_, row) in enumerate(self.input_df.iterrows(), 1):
            # Show progress
            if show_progress and (i % 10 == 0 or i == 1 or i == total_records):
                print(f"Processing PolicyEngine: {i}/{total_records} records", end="\r")
            
            # Process record (same as vectorized_validation.py)
            taxsim_input = row.to_dict()
            pe_situation = generate_household(taxsim_input)
            pe_output = export_household(taxsim_input, pe_situation, self.logs, self.disable_salt)
            results.append(pe_output)
        
        if show_progress:
            print("")  # Clear progress line
        
        return pd.DataFrame(results)
    
    def run_original_format(self):
        """
        Run PolicyEngine with original cli.py output format
        
        This preserves the exact behavior of the original cli.py
        """
        # Process each row (exact logic from cli.py)
        idtl_0_results = []
        idtl_2_results = []
        idtl_5_results = ""
        
        for _, row in self.input_df.iterrows():
            taxsim_input = row.to_dict()
            pe_situation = generate_household(taxsim_input)
            
            taxsim_output = export_household(
                taxsim_input, pe_situation, self.logs, self.disable_salt
            )
            
            idtl = taxsim_input.get("idtl", 2)  # Default to 2 if not specified
            if idtl == 0:
                idtl_0_results.append(taxsim_output)
            elif idtl == 2:
                idtl_2_results.append(taxsim_output)
            else:
                idtl_5_results += taxsim_output
        
        # Format output (exact logic from cli.py)
        idtl_0_output = self._to_csv_str(idtl_0_results)
        idtl_2_output = self._to_csv_str(idtl_2_results)
        
        output_str = ""
        if idtl_0_output:
            output_str += idtl_0_output
        if idtl_2_output:
            output_str += f"\n{idtl_2_output}"
        if idtl_5_results:
            output_str += f"\n{idtl_5_results}"
        
        print(output_str)
    
    def _to_csv_str(self, results):
        """Original to_csv_str function from cli.py"""
        if len(results) == 0 or results is None:
            return ""
        
        df = pd.DataFrame(results)
        content = df.to_csv(index=False, float_format="%.1f", lineterminator="\n")
        cleaned_df = pd.read_csv(StringIO(content))
        return cleaned_df.to_csv(index=False, lineterminator="\n")
