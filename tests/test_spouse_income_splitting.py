"""Regression tests for 50/50 spouse income splitting in PolicyEngineRunner.

Household-aggregate TAXSIM inputs (intrec, dividends, ltcg, stcg, pensions,
gssi, scorp) have no per-spouse pair field. For MFJ, the runner allocates
these evenly between spouses so that per-person state rules (e.g. DE age 60+
exclusion, DE pension exclusion) apply to both spouses. See issues #665
and #838.

Pension and Social Security income use an age-aware rule: split only when
both spouses are 60 or older; otherwise the full amount stays with the
primary filer to preserve state per-person elderly exclusions (CO, GA, MD,
NJ, etc.). See issue #924.
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


def test_pension_splits_when_both_spouses_are_55_plus():
    """Pension: when both spouses ≥ 55 (CO's threshold), allocate 50/50
    so each spouse claims the per-person CO pension subtraction. See
    taxsim issue #933: CO joint, page=58, sage=56 — both qualify for
    CO's 55-64 $20K subtraction. Pre-fix PE put pension on primary
    only, giving $20K total subtraction; correct behavior splits 50/50
    so each spouse claims $20K = $40K total (matching TaxAct)."""
    df = pd.DataFrame([_base_mfj_record(page=58, sage=56, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


def test_pension_goes_to_primary_when_primary_is_older():
    """Pension: mixed-age, primary older — keep full pension on primary
    so they claim the per-person elderly exclusion. Splitting 50/50 would
    push half onto the under-60 spouse and lose half the exclusion
    (see #838 validation)."""
    df = pd.DataFrame([_base_mfj_record(page=70, sage=50, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [40000.0, 0.0])


def test_pension_goes_to_spouse_when_spouse_is_older():
    """Pension: mixed-age, spouse older — assign full pension to spouse
    so the qualifying filer claims the exclusion. See taxsim issue #774:
    IA pension subtraction is age-55+, and with page=54 / sage=55 the
    older spouse should hold the pension."""
    df = pd.DataFrame([_base_mfj_record(page=54, sage=55, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [0.0, 40000.0])


def test_pension_splits_when_both_spouses_under_threshold():
    """Pension: when both spouses are on the same (younger) side of the
    eligibility line, split 50/50 — matching TAXSIM (which splits the
    household pension column) and giving age-independent per-person
    exclusions (KY, OK) to both spouses. See taxsim #965 (KY) / #966 (OK):
    both filers age 45, where dumping pension on the primary denied the
    spouse's exclusion. Verified against the NBER binary."""
    df = pd.DataFrame([_base_mfj_record(page=45, sage=45, pensions=30000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [15000.0, 15000.0])


def test_pension_routes_to_older_spouse_when_straddling_ga_age_62():
    """Pension, per-state age: Georgia's retirement exclusion qualifies at
    62 (not the 55 default). A GA 65/61 couple are both ≥55 but straddle
    GA's 62 gate, so the pension routes entirely to the 65-year-old; a 50/50
    split would strand the 61-year-old's half, which GA cannot exclude under
    62 (taxsim #1027). state=11 is GA."""
    df = pd.DataFrame([_base_mfj_record(state=11, page=65, sage=61, pensions=77954)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [77954.0, 0.0])


def test_pension_splits_for_ga_couple_both_over_62():
    """Pension, per-state age: a GA couple both ≥62 are on the qualifying
    side of GA's 62 gate, so split 50/50."""
    df = pd.DataFrame([_base_mfj_record(state=11, page=66, sage=64, pensions=80000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [40000.0, 40000.0])


def test_pension_splits_for_ga_couple_55_to_61_both_below_62():
    """Pension, per-state age: a GA couple both in 55-61 are both below
    GA's 62 gate (same, non-qualifying side), so split 50/50 — neither
    qualifies for GA's exclusion regardless of allocation."""
    df = pd.DataFrame([_base_mfj_record(state=11, page=60, sage=58, pensions=80000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [40000.0, 40000.0])


def test_pension_splits_for_ky_mixed_age_independent_exclusion():
    """Pension, age-independent state: Kentucky's $31,110 retirement exclusion
    is per-person with no age requirement (split age 0), so a mixed-age couple
    still splits 50/50. Routing to the older spouse would strand the younger
    spouse's exclusion — TAXSIM and TaxAct give both (taxsim #965, #1026).
    state=18 is KY."""
    df = pd.DataFrame([_base_mfj_record(state=18, page=59, sage=37, pensions=71414.92)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [35707.46, 35707.46])


def test_pension_splits_for_ok_mixed_age_independent_exclusion():
    """Pension, age-independent state: Oklahoma's $10,000 retirement exclusion
    is per-person with no age requirement (split age 0), so a mixed-age couple
    splits 50/50 rather than routing to the older spouse (taxsim #966).
    state=37 is OK."""
    df = pd.DataFrame([_base_mfj_record(state=37, page=59, sage=37, pensions=40000)])
    values = _run_allocation(df, "taxable_private_pension_income")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


def test_gssi_ignores_per_state_pension_age_for_ga_straddle():
    """gssi: the per-state pension age (GA 62) applies to the pension field
    only, NOT to Social Security. A GA 65/61 couple straddles GA's 62
    pension gate, so the *pension* routes to the older spouse — but SS is
    exempt regardless of age, so gssi still splits 50/50 on the default 55
    gate. Routing gssi on the 62 gate over-excluded SS and diverged from
    TAXSIM (eCPS regression record #27269, GA 68/60)."""
    df = pd.DataFrame([_base_mfj_record(state=11, page=65, sage=61, gssi=40000)])
    values = _run_allocation(df, "social_security_retirement")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


def test_gssi_splits_when_both_spouses_are_60_plus():
    """gssi: when both spouses ≥ 60, allocate 50/50 so both qualify
    for state per-person SS exclusions."""
    df = pd.DataFrame([_base_mfj_record(page=65, sage=65, gssi=40000)])
    values = _run_allocation(df, "social_security_retirement")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


def test_gssi_goes_to_older_spouse_for_mixed_age_couple():
    """gssi: mixed-age (primary 75, spouse 40), keep full SS on the older
    primary so age-based state exclusions (CO, MD) reach the qualifying
    filer. See taxsim issue #924."""
    df = pd.DataFrame([_base_mfj_record(page=75, sage=40, gssi=40000)])
    values = _run_allocation(df, "social_security_retirement")
    np.testing.assert_allclose(values, [40000.0, 0.0])


def test_gssi_goes_to_spouse_when_spouse_is_older():
    """gssi: mixed-age, spouse older — assign all SS to spouse so they
    claim the age-based subtraction."""
    df = pd.DataFrame([_base_mfj_record(page=40, sage=75, gssi=40000)])
    values = _run_allocation(df, "social_security_retirement")
    np.testing.assert_allclose(values, [0.0, 40000.0])


def test_gssi_splits_when_both_spouses_under_threshold():
    """gssi: when both spouses are on the same (younger) side of the
    eligibility line, split 50/50 — matching TAXSIM. Mirrors the pension
    rule (see taxsim #924 for the mixed-age -> older convention)."""
    df = pd.DataFrame([_base_mfj_record(page=45, sage=45, gssi=40000)])
    values = _run_allocation(df, "social_security_retirement")
    np.testing.assert_allclose(values, [20000.0, 20000.0])


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
