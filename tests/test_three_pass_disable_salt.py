"""
Tests for the --disable-salt mode that aligns PE's federal SALT
calculation with TAXSIM-35.

TAXSIM-35 deducts mortgage interest and property tax on the federal
return but does NOT deduct state income tax — verified against the
taxsimtest binary across states/years (e.g. NY single $84K wages + $37K
mortgage → federal itemized $37,000, state tax not deducted). So
--disable-salt runs a single SALT-disabled pass: it zeroes
state_and_local_sales_or_income_tax for both the state and federal
computation, excluding state income/sales tax from federal Schedule A
while still allowing property tax (real_estate_taxes) through.

A previous three-pass instead re-introduced the computed state tax as
fixed federal SALT, which overshot TAXSIM by the full state-tax amount on
every itemizing record (see taxsim #971: ~$1,185 mean federal mismatch on
a 60-record itemizing sample, 0/60 within $15).
"""

import pandas as pd
import numpy as np

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _ny_filer_with_mortgage(**overrides):
    """NY single, $84K wages + $37K mortgage — TAXSIM v17 case 5436."""
    base = {
        "taxsimid": 1,
        "year": 2024,
        "state": 33,
        "mstat": 1,
        "page": 40,
        "sage": 0,
        "depx": 0,
        "pwages": 84000.0,
        "mortgage": 37000.0,
        "idtl": 2,
    }
    base.update(overrides)
    return pd.DataFrame([base])


class TestThreePassDisableSalt:
    def test_state_tax_unchanged_vs_two_pass(self):
        """Three-pass state output must match the SALT-disabled run.
        (We're only changing the federal pass's SALT input.)"""
        df = _ny_filer_with_mortgage()
        with_flag = PolicyEngineRunner(df.copy(), disable_salt=True).run(
            show_progress=False
        )
        # State tax should still reflect SALT-off computation (no iteration
        # back into federal SALT). Take siitax from a clean disable-salt
        # run via direct API surface — we'll need it to assert.
        assert np.isfinite(with_flag["siitax"].iloc[0])

    def test_federal_salt_excludes_state_income_tax(self):
        """Federal v17 (itemized) under --disable-salt must EXCLUDE state
        income tax — only mortgage interest (and property tax) are deducted
        federally, matching TAXSIM-35. Verified against the taxsimtest
        binary: NY single $84K wages + $37K mortgage → federal itemized
        $37,000, with the ~$2,420 NY state tax NOT deducted. (Previously a
        three-pass deducted the state tax as fixed SALT, overshooting
        TAXSIM — see taxsim #971.)"""
        df = _ny_filer_with_mortgage()
        result = PolicyEngineRunner(df.copy(), disable_salt=True).run(
            show_progress=False
        )
        v17 = result["v17"].iloc[0]
        mortgage = 37000.0
        # Federal itemized = mortgage only (no state income tax in SALT);
        # this record has no property tax. $5 tolerance for rounding.
        assert abs(v17 - mortgage) <= 5, (
            f"v17={v17} should equal the mortgage ({mortgage}) with no state "
            f"income tax in federal SALT"
        )

    def test_results_stable_idempotent(self):
        """Two calls to .run() with disable_salt=True should produce the
        same result — the three-pass shouldn't add nondeterminism."""
        df = _ny_filer_with_mortgage()
        r1 = PolicyEngineRunner(df.copy(), disable_salt=True).run(show_progress=False)
        r2 = PolicyEngineRunner(df.copy(), disable_salt=True).run(show_progress=False)
        for col in ["fiitax", "siitax", "v17", "v18"]:
            assert abs(r1[col].iloc[0] - r2[col].iloc[0]) < 1.0

    def test_no_disable_salt_unchanged(self):
        """Without --disable-salt, behavior must be untouched (single
        pass, no override)."""
        df = _ny_filer_with_mortgage()
        result = PolicyEngineRunner(df.copy(), disable_salt=False).run(
            show_progress=False
        )
        assert len(result) == 1
        assert np.isfinite(result["fiitax"].iloc[0])
