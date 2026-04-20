"""Regression tests for 50/50 spouse income splitting in PolicyEngineRunner.

Household-aggregate TAXSIM inputs (intrec, dividends, ltcg, stcg, pensions,
gssi, scorp) have no per-spouse pair field. For MFJ, the runner allocates
these evenly between spouses so that per-person state rules (e.g. DE age 60+
exclusion, DE pension exclusion) apply to both spouses. See issues #665
and #838.

Pension income uses an age-aware rule: split only when both spouses are
60 or older; otherwise the full amount stays with the primary filer to
preserve state per-person elderly exclusions (GA, MD, NJ, etc.).
"""

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)
from policyengine_us import Microsimulation


def _run_allocation(df, pe_var, year=2024):
    """Return the per-person values of a PE variable after dataset build."""
    ds = TaxsimMicrosimDataset(df)
    ds.generate()
    sim = Microsimulation(dataset=ds)
    return sim.calculate(pe_var, year).values


def _base_mfj_record(taxsimid=1, **overrides):
    record = {
        "taxsimid": taxsimid,
        "year": 2024,
        "state": 44,  # TX — no state tax noise
        "mstat": 2,
        "pwages": 0,
        "swages": 0,
        "page": 45,
        "sage": 45,
        "depx": 0,
        "idtl": 2,
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    "taxsim_field,pe_var,amount",
    [
        ("intrec", "taxable_interest_income", 100000),
        ("dividends", "qualified_dividend_income", 80000),
        ("ltcg", "long_term_capital_gains", 60000),
        ("stcg", "short_term_capital_gains", 30000),
        ("gssi", "social_security_retirement", 40000),
        ("scorp", "partnership_s_corp_income", 50000),
    ],
)
def test_mfj_household_income_splits_between_spouses(taxsim_field, pe_var, amount):
    """MFJ: household aggregate income should be $amount/2 on each spouse."""
    df = pd.DataFrame([_base_mfj_record(**{taxsim_field: amount})])
    values = _run_allocation(df, pe_var)
    # Two people (primary + spouse). Each should get half.
    assert len(values) == 2
    np.testing.assert_allclose(values, [amount / 2, amount / 2])


@pytest.mark.parametrize(
    "taxsim_field,pe_var,amount",
    [
        ("intrec", "taxable_interest_income", 100000),
        ("pensions", "taxable_private_pension_income", 50000),
        ("gssi", "social_security_retirement", 40000),
    ],
)
def test_single_filer_household_income_stays_on_primary(taxsim_field, pe_var, amount):
    """Single: household income stays fully on the primary (no spouse exists)."""
    df = pd.DataFrame(
        [
            {
                "taxsimid": 1,
                "year": 2024,
                "state": 44,
                "mstat": 1,
                "pwages": 0,
                "swages": 0,
                "page": 45,
                "sage": 0,
                "depx": 0,
                taxsim_field: amount,
                "idtl": 2,
            }
        ]
    )
    values = _run_allocation(df, pe_var)
    assert len(values) == 1
    assert values[0] == amount


def test_pension_splits_when_both_spouses_are_60_plus():
    """Pension: when both spouses ≥ 60, allocate 50/50 so both qualify
    for state per-person elderly pension exclusions."""
    df = pd.DataFrame([_base_mfj_record(page=65, sage=65, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


def test_pension_stays_on_primary_for_mixed_age_couple():
    """Pension: when only one spouse is 60+, keep full pension on primary
    so the qualifying spouse claims the per-person exclusion. Splitting
    50/50 would push half the pension onto the under-60 spouse and
    eliminate half the exclusion (see #838 validation)."""
    df = pd.DataFrame([_base_mfj_record(page=70, sage=50, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [40000.0, 0.0])


def test_pension_stays_on_primary_when_both_under_60():
    """Pension: when neither spouse is 60+, state elderly exclusions
    do not apply. Keep on primary to match pre-fix behavior for the
    non-elderly case."""
    df = pd.DataFrame([_base_mfj_record(page=45, sage=45, pensions=30000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [30000.0, 0.0])


def test_de_elderly_pension_matches_issue_838():
    """End-to-end: DE elderly couple with pension income should produce
    a state tax close to TAXSIM after the 50/50 split. Issue #838 reported
    a $848 siitax where TAXSIM gave $386; after the fix PE gives ~$276."""
    df = pd.DataFrame(
        [
            {
                "taxsimid": 838,
                "year": 2024,
                "state": 8,  # DE
                "mstat": 2,
                "pwages": 0,
                "swages": 20000,
                "page": 65,
                "sage": 65,
                "depx": 2,
                "age1": 8,
                "age2": 12,
                "pensions": 44000,
                "idtl": 2,
            }
        ]
    )
    result = PolicyEngineRunner(df).run()
    siitax = result["siitax"].iloc[0]
    # Pre-fix was $848; TAXSIM is $386. Guard against a regression
    # past $500 (well below the pre-fix value) without pinning to an
    # exact number that may drift with policyengine-us releases.
    assert siitax < 500, (
        f"DE elderly pension siitax {siitax} looks like the split regressed"
    )
