"""
Tests for the income-scaled match tolerance in the comparator.

The flat $15 absolute tolerance flags negligible differences on
extreme-magnitude records (e.g. large S-corp income/losses), where PE and
TAXSIM agree to a tiny fraction of income. `relative_tolerance` lets a record
match within max($15, relative_tolerance * |AGI|). Default 0.0 preserves the
absolute-only behavior.
"""

import pandas as pd

from policyengine_taxsim.comparison.comparator import (
    TaxComparator,
    ComparisonConfig,
)


def _frames(taxsimid, agi, fiitax_t, fiitax_p):
    tx = pd.DataFrame(
        {"taxsimid": taxsimid, "v10": agi, "fiitax": fiitax_t, "siitax": 0.0}
    )
    pe = pd.DataFrame(
        {"taxsimid": taxsimid, "v10": agi, "fiitax": fiitax_p, "siitax": 0.0}
    )
    return tx, pe


def test_default_absolute_tolerance_flags_large_dollar_diff():
    """With default (absolute-only) tolerance, a $500 diff is a mismatch."""
    tx, pe = _frames([1], [10_000_000], [1_000_000], [1_000_500])
    r = TaxComparator(tx, pe, ComparisonConfig()).compare()
    assert r.federal_match_percentage == 0.0


def test_income_scaled_tolerance_absorbs_negligible_diff():
    """A $500 diff on $10M AGI is 0.005% — within a 0.1% income-scaled
    tolerance, so it matches; a genuinely large diff still fails."""
    # negligible: $500 on $10M
    tx, pe = _frames([1], [10_000_000], [1_000_000], [1_000_500])
    r = TaxComparator(
        tx, pe, ComparisonConfig(relative_tolerance=0.001)
    ).compare()
    assert r.federal_match_percentage == 100.0

    # material: $50k diff on $10M (0.5%) exceeds the 0.1% floor -> mismatch
    tx2, pe2 = _frames([1], [10_000_000], [1_000_000], [1_050_000])
    r2 = TaxComparator(
        tx2, pe2, ComparisonConfig(relative_tolerance=0.001)
    ).compare()
    assert r2.federal_match_percentage == 0.0


def test_absolute_floor_preserved_for_small_income():
    """The $15 absolute floor still applies for low-AGI records (the scaled
    tolerance never lowers it below $15)."""
    # $20 diff on $1,000 AGI: 0.1% of AGI = $1, so floor stays $15 -> mismatch
    tx, pe = _frames([1], [1_000], [100], [120])
    r = TaxComparator(
        tx, pe, ComparisonConfig(relative_tolerance=0.001)
    ).compare()
    assert r.federal_match_percentage == 0.0
