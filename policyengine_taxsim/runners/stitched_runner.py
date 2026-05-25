"""Runner that stitches PolicyEngine (2021+) and TAXSIM (pre-2021) results."""

import logging
import pandas as pd

from .base_runner import BaseTaxRunner
from .policyengine_runner import PolicyEngineRunner

logger = logging.getLogger(__name__)


class StitchedRunner(BaseTaxRunner):
    """Routes rows to PolicyEngine or TAXSIM based on tax year.

    Years >= pe_min_year (default 2021) are processed by PolicyEngineRunner.
    Earlier years are processed by TaxsimRunner (local binary) or
    RemoteTaxsimRunner (NBER web service). Results are merged and
    returned in the original taxsimid order.
    """

    PE_MIN_YEAR = 2021

    # kwargs that only PolicyEngineRunner understands
    _PE_ONLY_KWARGS = {"logs", "disable_salt", "assume_w2_wages"}

    def __init__(
        self,
        input_df: pd.DataFrame,
        pe_min_year=None,
        use_remote_taxsim=False,
        **kwargs,
    ):
        super().__init__(input_df)
        self.pe_min_year = pe_min_year if pe_min_year is not None else self.PE_MIN_YEAR
        self.use_remote_taxsim = use_remote_taxsim
        self._pe_kwargs = kwargs

    def _make_taxsim_runner(self, df):
        """Create the appropriate TAXSIM runner (local or remote)."""
        if self.use_remote_taxsim:
            from .remote_taxsim_runner import RemoteTaxsimRunner

            return RemoteTaxsimRunner(df)
        else:
            from .taxsim_runner import TaxsimRunner

            return TaxsimRunner(df)

    def run(self, show_progress: bool = True, on_progress=None) -> pd.DataFrame:
        import numpy as np

        years = self.input_df["year"].astype(int)
        pe_mask = years >= self.pe_min_year
        taxsim_mask = ~pe_mask

        # Warn if PE-only kwargs are set but some rows go to TAXSIM
        if taxsim_mask.any():
            active_pe_kwargs = {
                k for k, v in self._pe_kwargs.items() if k in self._PE_ONLY_KWARGS and v
            }
            if active_pe_kwargs:
                logger.warning(
                    "%s only apply to PolicyEngine rows (year >= %d); "
                    "%d row(s) routed to TAXSIM will ignore these settings.",
                    ", ".join(sorted(active_pe_kwargs)),
                    self.pe_min_year,
                    taxsim_mask.sum(),
                )

        # Capture original positional indices so we can restore input order
        # without relying on taxsimid being unique (panel and multi-state
        # workflows legitimately reuse taxsimid).
        input_df = self.input_df.reset_index(drop=True)
        pe_subset = input_df[pe_mask.to_numpy()]
        taxsim_subset = input_df[taxsim_mask.to_numpy()]

        frames = []
        frame_positions = []

        if not pe_subset.empty:
            pe_runner = PolicyEngineRunner(pe_subset, **self._pe_kwargs)
            frames.append(
                pe_runner.run(show_progress=show_progress, on_progress=on_progress)
            )
            # PolicyEngineRunner emits rows sorted by year ascending
            # (stable within a year), so the original positions follow the
            # same stable sort key.
            frame_positions.append(
                pe_subset.sort_values("year", kind="mergesort").index.to_numpy()
            )

        if not taxsim_subset.empty:
            taxsim_runner = self._make_taxsim_runner(taxsim_subset)
            frames.append(taxsim_runner.run(show_progress=show_progress))
            frame_positions.append(taxsim_subset.index.to_numpy())

        if not frames:
            return pd.DataFrame(columns=self.input_df.columns)

        result = pd.concat(frames, ignore_index=True)
        positions = np.concatenate(frame_positions)
        result = result.iloc[np.argsort(positions, kind="mergesort")].reset_index(
            drop=True
        )
        return result
