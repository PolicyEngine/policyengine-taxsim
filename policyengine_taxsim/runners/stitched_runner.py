"""Runner that stitches PolicyEngine (2021+) and TAXSIM (pre-2021) results."""

import pandas as pd

from .base_runner import BaseTaxRunner
from .policyengine_runner import PolicyEngineRunner
from .taxsim_runner import TaxsimRunner


class StitchedRunner(BaseTaxRunner):
    """Routes rows to PolicyEngine or TAXSIM based on tax year.

    Years >= pe_min_year (default 2021) are processed by PolicyEngineRunner.
    Earlier years are processed by TaxsimRunner. Results are merged and
    returned in the original taxsimid order.
    """

    PE_MIN_YEAR = 2021

    def __init__(self, input_df: pd.DataFrame, pe_min_year=None, **kwargs):
        super().__init__(input_df)
        self.pe_min_year = pe_min_year if pe_min_year is not None else self.PE_MIN_YEAR
        self._pe_kwargs = kwargs

    def run(self, show_progress: bool = True) -> pd.DataFrame:
        years = self.input_df["year"].astype(int)
        pe_mask = years >= self.pe_min_year
        taxsim_mask = ~pe_mask

        frames = []

        if pe_mask.any():
            pe_runner = PolicyEngineRunner(
                self.input_df[pe_mask], **self._pe_kwargs
            )
            frames.append(pe_runner.run(show_progress=show_progress))

        if taxsim_mask.any():
            taxsim_runner = TaxsimRunner(self.input_df[taxsim_mask])
            frames.append(taxsim_runner.run(show_progress=show_progress))

        result = pd.concat(frames, ignore_index=True)

        # Restore original taxsimid order
        original_order = self.input_df["taxsimid"].tolist()
        result = result.set_index("taxsimid").loc[original_order].reset_index()
        return result
