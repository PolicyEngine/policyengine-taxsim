"""
Test that PE's `fiitax` output does NOT include the Additional
Medicare Tax (Form 8959, IRC § 3101(b)(2) / § 1401(b)(2)).

NBER TAXSIM-35 (`taxsimtest`) reports AddMed in a separate `addmed`
column rather than rolling it into `fiitax`. This matches Form 1040
Line 23 / Schedule 2 Line 11: Additional Medicare Tax is "Other
Taxes", distinct from regular income tax on Line 16.

Reference:
- IRC § 3101(b)(2): 0.9% Additional Medicare Tax on wages above
  threshold.
- IRC § 1401(b)(2): 0.9% Additional Medicare Tax on self-employment
  earnings above threshold.
- Form 8959: Additional Medicare Tax computation.
- Form 1040 Line 23 / Schedule 2 Line 11: AddMed reported under
  "Other Taxes", not regular income tax.

NBER `taxsimtest` smoke test (single $500K wages, no other income,
year 2024):
  fiitax  = $140,264.75   (= income_tax only)
  addmed  = $2,355.75     (separate column)
  v28     = $140,264.75   (income tax before NIIT / AddMed)

If we incorrectly add `additional_medicare_tax` to `fiitax`, PE
overshoots TAXSIM by exactly the AddMed amount. This was the source
of ~$412K (95%) of the residual federal mismatch in the eCPS n=2000
TY 2025 comparison before this fix.
"""

import pandas as pd
import pytest

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _high_wage_single():
    """Single filer, $500K wages — clearly above the $200K AddMed
    threshold but with no investment income (NIIT=0) so the only
    difference between including / excluding AddMed in fiitax is
    the AddMed amount itself."""
    return pd.DataFrame(
        {
            "taxsimid": [1],
            "year": 2024,
            "state": [5],  # CA
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": [500_000.0],
            "swages": 0.0,
            "idtl": 2,
        }
    )


def _high_wage_mfj():
    """MFJ filer, $1M total wages — above the $250K AddMed
    threshold so we expect a meaningful AddMed component."""
    return pd.DataFrame(
        {
            "taxsimid": [2],
            "year": 2024,
            "state": [5],
            "mstat": 2,
            "depx": 0,
            "page": 45,
            "sage": 45,
            "pwages": [500_000.0],
            "swages": [500_000.0],
            "idtl": 2,
        }
    )


class TestAddMedExcludedFromFiitax:
    def test_single_500k_fiitax_excludes_addmed(self):
        """
        Single $500K wages 2024: NBER TAXSIM-35 `taxsimtest` reports
        fiitax = $140,264.75. If PE's fiitax incorrectly added the
        $2,700 AddMed, the result would round to ~$142,965 — well
        outside any sane tolerance.
        """
        records = _high_wage_single()
        runner = PolicyEngineRunner(records.copy(), logs=False)
        result = runner.run(show_progress=False)
        fiitax = float(result["fiitax"].iloc[0])
        assert fiitax == pytest.approx(140_265, abs=200), (
            f"Expected fiitax≈$140,265 (matching NBER TAXSIM-35 `taxsimtest`), "
            f"got ${fiitax:.2f}. A spread of ~$2,700 over target indicates "
            f"PE is incorrectly adding Additional Medicare Tax to fiitax. "
            f"Per Form 1040 Line 23 / Schedule 2 Line 11, AddMed is an "
            f"`Other Tax` and must flow through the `addmed` / `v44` "
            f"output columns, not fiitax."
        )

    def test_mfj_1m_fiitax_excludes_addmed(self):
        """
        MFJ $1M total wages 2024: NBER TAXSIM-35 `taxsimtest` reports
        fiitax = $285,321.50. If AddMed were incorrectly added to
        PE's fiitax, it would land several thousand above target.
        """
        records = _high_wage_mfj()
        runner = PolicyEngineRunner(records.copy(), logs=False)
        result = runner.run(show_progress=False)
        fiitax = float(result["fiitax"].iloc[0])
        assert fiitax == pytest.approx(285_321, abs=300), (
            f"Expected fiitax≈$285,321 for MFJ $1M wages 2024, got "
            f"${fiitax:.2f}. Several thousand over target means AddMed "
            f"has been re-added to fiitax."
        )
