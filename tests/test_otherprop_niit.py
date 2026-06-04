"""
Tests for TAXSIM `otherprop` → PE-US `rental_income` routing and NIIT.

Legal anchors:
- IRC § 1411(c)(1)(A)(i): NIIT base includes "gross income from interest,
  dividends, annuities, royalties, and rents, other than such income which
  is derived in the ordinary course of a trade or business not described
  in paragraph (2)".
  https://www.law.cornell.edu/uscode/text/26/1411
- Form 8960 Line 4a: "Income From Trades/Businesses/Farming, Rental Real
  Estate, Royalties, Partnerships, S Corporations, and Trusts".
  https://www.irs.gov/instructions/i8960
- IRC § 199A(d)(1): QBID requires a "qualified trade or business";
  passive individual rental income generally does not qualify absent the
  Reg § 1.199A-1(b)(14) safe harbor, which TAXSIM input cannot signal.

TAXSIM-35 binary probe (single, age 45, otherprop=$1M, no other income,
year 2024) produces fiitax=$353,188 and niit=$30,400 (= 3.8% × ($1M −
$200K threshold)). PE-US must align via:
  variable_mappings.yaml: otherprop → rental_income
  policyengine_runner: rental_income_would_be_qualified=False for chunks
                       carrying otherprop, suppressing the QBID gate.

These tests pin both legs so a future mapping edit can't silently
re-route otherprop away from the NIIT base or re-enable auto-QBID.
"""

import pandas as pd
import pytest

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _single_otherprop_record():
    """Pure-otherprop probe: matches the TAXSIM-35 binary smoke test."""
    return pd.DataFrame(
        {
            "taxsimid": [1],
            "year": 2024,
            "state": [5],  # CA
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": 0.0,
            "swages": 0.0,
            "otherprop": [1_000_000.0],
            "idtl": 2,
        }
    )


def _mixed_record_no_otherprop():
    """Control: wages-only, no otherprop. Confirms NIIT only fires on
    investment-type income above the threshold."""
    return pd.DataFrame(
        {
            "taxsimid": [2],
            "year": 2024,
            "state": [5],
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": [1_000_000.0],
            "swages": 0.0,
            "otherprop": 0.0,
            "idtl": 2,
        }
    )


class TestOtherpropNIIT:
    """Pin the otherprop → rental_income + NIIT behavior to TAXSIM-35."""

    def test_otherprop_drives_niit_at_3_8_percent(self):
        """
        $1M of pure `otherprop`, single, age 45 must trigger NIIT of
        3.8% × ($1M − $200K single threshold) = $30,400 — matching the
        TAXSIM-35 binary and Form 8960 Line 4a.
        """
        records = _single_otherprop_record()
        runner = PolicyEngineRunner(records.copy(), logs=False)
        result = runner.run(show_progress=False)
        # NIIT column on TAXSIM v50 / PE niit output
        niit = float(result["niit"].iloc[0])
        assert niit == pytest.approx(30_400, abs=10), (
            f"Expected NIIT=$30,400 (3.8% × $800K) for $1M otherprop single, "
            f"got ${niit:.2f}. Likely cause: otherprop no longer routes to "
            f"rental_income, or rental_income dropped out of "
            f"gov.irs.investment.income.sources upstream."
        )

    def test_otherprop_does_not_trigger_qbid(self):
        """
        TAXSIM does not apply § 199A QBID to `otherprop` — only the
        explicit `pbusinc` input triggers QBID. PE-US's
        `rental_income_would_be_qualified` defaults to True, so the
        runner must override it to False when otherprop is present.
        Verify by comparing fiitax against the TAXSIM-35 binary result
        of $353,188 for a $1M otherprop single filer.
        """
        records = _single_otherprop_record()
        runner = PolicyEngineRunner(records.copy(), logs=False)
        result = runner.run(show_progress=False)
        fiitax = float(result["fiitax"].iloc[0])
        # TAXSIM-35 binary: $353,187.93. Allow $50 rounding because PE-US
        # and TAXSIM use slightly different bracket-mid points.
        assert fiitax == pytest.approx(353_188, abs=50), (
            f"Expected fiitax≈$353,188 to match TAXSIM-35 binary for $1M "
            f"otherprop single. Got ${fiitax:.2f}. Spread of >$50 typically "
            f"means PE applied QBID (~$170K reduction) on the rental_income, "
            f"indicating the QBID gate override in policyengine_runner "
            f"is not firing for this chunk."
        )

    def test_no_otherprop_no_niit_on_wages(self):
        """
        Wages-only filer should not generate NIIT regardless of size.
        Acts as a negative control on the routing: the override should
        only suppress QBID for tax units carrying otherprop, and NIIT
        should remain governed by investment-income sources.
        """
        records = _mixed_record_no_otherprop()
        runner = PolicyEngineRunner(records.copy(), logs=False)
        result = runner.run(show_progress=False)
        niit = float(result["niit"].iloc[0])
        assert niit == pytest.approx(0, abs=1), (
            f"Wages-only filer must not owe NIIT, got ${niit:.2f}. "
            f"Could indicate otherprop's QBID override is leaking and "
            f"reclassifying wages."
        )
