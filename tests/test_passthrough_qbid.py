"""Regression tests for pass-through income → QBID-bearing PolicyEngine variables.

Dan Feenberg's 2026-06-30 comparison (email to Pavel/Max) ran $100k of gross
income from five sources through the emulator for a 2025 single filer and found
the PolicyEngine column diverged from TAXSIM-35 on three of them:

  - pbusinc: mapped to the COMPUTED qualified_business_income variable, which
    the emulator dataset held as an input at 0 for every record → S-corp/QBI
    income produced zero AGI and zero tax.
  - psemp / scorp: correct AGI but NO qualified business income deduction
    (taxable 77,185 / 84,250 vs TAXSIM's 61,748 / 67,400).
  - pprofinc / intrec: already correct.

Root cause: the emulator initializes every mapped PolicyEngine variable as a
dataset input. Mapping pbusinc → qualified_business_income (a variable derived
from self_employment_income et al. via the § 199A income_definition) held that
derived value at whatever pbusinc supplied — 0 on all other records — which
zeroed the non-SSTB QBI component for psemp and scorp too. scorp additionally
mapped to the s_corp_income leaf rather than partnership_s_corp_income (the
variable actually named in the QBI income_definition).

Fix (variable_mappings.yaml + mapper code):
  - psemp/ssemp AND pbusinc/sbusinc → self_employment_income
    (active participation, SECA, QBID without the SSTB phaseout — Dan's spec
    treats businc as identical to semp).
  - scorp → partnership_s_corp_income (QBID, no SECA, NIIT-eligible).
  - pprofinc/sprofinc → sstb_self_employment_income (QBID WITH the
    § 199A(d)(3) applicable-percentage phaseout) — unchanged, already correct.

policyengine-us itself was verified correct throughout (a direct Simulation
with self_employment_income=100k gives AGI 92,935 / taxable 61,748 /
income_tax 8,499); the defect was purely in this emulator's mapping layer.

Fixes taxsim #384 (FICA and QBI income), #943 (scorp QBID), #1004 (scorp QBID),
#762 (QBID across pass-through inputs); addresses #1018 and #1003.
"""

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


# TAXSIM-35 target column from Dan's 2026-06-30 five-source comparison
# (2025 single filer, $100k of a single gross income source, state = TX so no
# state tax noise). Tuples are (AGI, taxable income, federal income tax).
# income_tax is asserted with a $1 tolerance because TAXSIM and PE round the
# half-SECA / QBID chain at different points (Dan's table shows 8,498 where PE
# gives 8,499).
DAN_FIVE_SOURCE = {
    "psemp": (92_935, 61_748, 8_499),
    "pbusinc": (92_935, 61_748, 8_499),
    "scorp": (100_000, 67_400, 9_742),
    "pprofinc": (92_935, 61_748, 8_499),
    "intrec": (100_000, 84_250, 13_449),
}

# All income columns that must be present (as 0) so each single-source record
# carries only its own income.
_INCOME_COLS = [
    "psemp",
    "ssemp",
    "pbusinc",
    "sbusinc",
    "scorp",
    "pprofinc",
    "sprofinc",
    "intrec",
]


def _single_source_frame():
    """One 2025 TX single-filer record per source, $100k of that source."""
    rows = []
    for i, src in enumerate(DAN_FIVE_SOURCE, start=1):
        rec = {
            "taxsimid": i,
            "year": 2025,
            "state": 44,  # TX — no state income tax
            "mstat": 1,
            "depx": 0,
            "page": 40,
            "sage": 0,
            "pwages": 0.0,
            "swages": 0.0,
            "idtl": 2,  # full output → exposes v10 (AGI), v18 (taxable), qbid
        }
        rec[src] = 100_000.0
        rows.append(rec)
    df = pd.DataFrame(rows)
    for col in _INCOME_COLS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)
    return df


@pytest.fixture(scope="module")
def dan_results():
    """Run all five source records once and index by taxsimid."""
    df = _single_source_frame()
    out = PolicyEngineRunner(df.copy()).run(show_progress=False)
    return out.set_index("taxsimid")


@pytest.mark.parametrize(
    "taxsimid,source",
    list(enumerate(DAN_FIVE_SOURCE, start=1)),
)
def test_dan_five_source_agi_taxable_tax(dan_results, taxsimid, source):
    """$100k of each source reproduces TAXSIM-35's AGI, taxable income, and
    federal income tax (Dan Feenberg, 2026-06-30)."""
    agi, taxable, tax = DAN_FIVE_SOURCE[source]
    row = dan_results.loc[taxsimid]
    assert row["v10"] == pytest.approx(agi, abs=1.0), f"{source}: AGI"
    assert row["v18"] == pytest.approx(taxable, abs=1.0), f"{source}: taxable income"
    assert row["fiitax"] == pytest.approx(tax, abs=1.0), f"{source}: federal income tax"


@pytest.mark.parametrize(
    "taxsimid,source,expects_qbid",
    [
        (1, "psemp", True),  # self-employment → QBID (was 0 before the fix)
        (2, "pbusinc", True),  # active QBI → QBID (was fully unmapped before)
        (3, "scorp", True),  # S-corp → QBID via partnership_s_corp_income
        (4, "pprofinc", True),  # SSTB → QBID with phaseout (below threshold here)
        (5, "intrec", False),  # interest is not QBI → no QBID
    ],
)
def test_dan_five_source_qbid_present(dan_results, taxsimid, source, expects_qbid):
    """The four pass-through sources earn a QBID; interest does not.

    Below the phaseout threshold, $100k of qualifying pass-through income minus
    the half-SECA adjustment (for the SECA-bearing sources) yields a 20 %
    deduction; the exact figures differ only by whether SECA applies."""
    qbid = dan_results.loc[taxsimid]["qbid"]
    if expects_qbid:
        assert qbid > 0, f"{source}: expected a QBI deduction, got {qbid}"
    else:
        assert qbid == pytest.approx(0.0, abs=1.0), (
            f"{source}: expected no QBID, got {qbid}"
        )


def test_scorp_has_no_seca_but_earns_qbid(dan_results):
    """S-corp income (partnership_s_corp_income) earns the QBID but is NOT
    subject to self-employment tax — matching Dan's spec (no FICA/SECA on
    scorp) and TAXSIM. fica must be 0 while qbid is positive."""
    row = dan_results.loc[3]  # scorp
    assert row["fica"] == pytest.approx(0.0, abs=1.0), "scorp should bear no SECA/FICA"
    assert row["qbid"] > 0, "scorp should still earn a QBID"


def test_self_employment_sources_bear_seca(dan_results):
    """psemp, pbusinc, and pprofinc are active-participation income subject to
    SECA, so fica (the combined employee+employer FICA/SECA column) is positive
    for each — distinguishing them from scorp/intrec."""
    for taxsimid, source in [(1, "psemp"), (2, "pbusinc"), (4, "pprofinc")]:
        assert dan_results.loc[taxsimid]["fica"] > 0, f"{source} should bear SECA"


def _run_single(record, year=2025):
    """Run one TX single-filer record and return its full-output row."""
    df = pd.DataFrame([record])
    for col in _INCOME_COLS + ["w2_wages_from_qualified_business"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)
    out = PolicyEngineRunner(df.copy()).run(show_progress=False)
    return out.iloc[0]


def test_sstb_phaseout_binds_harder_than_non_sstb():
    """Above the § 199A threshold the SSTB applicable-percentage phaseout bites
    harder than the non-SSTB wage/UBIA cap: identical dollar amounts of SSTB
    professional income (pprofinc) and active QBI (pbusinc) yield a strictly
    smaller QBID for the SSTB.

    2025 single phaseout starts at $197,300 taxable income (excl. QBID), length
    $50,000. With $260k of income and no W-2 wages/UBIA (the emulator has no
    per-record W-2 input — TAXSIM never carries one), both categories are
    reduced above the threshold, but the SSTB's applicable-percentage phaseout
    reduces it further. The emulator gives pbusinc QBID ~17,143 and pprofinc
    QBID ~5,983. This pins the ordering and the non-SSTB > SSTB gap so a future
    mapping edit cannot silently route SSTB income onto the non-phaseout path
    (or vice-versa).

    (A direct policyengine-us Simulation supplied with large
    w2_wages_from_qualified_business lifts the non-SSTB QBID to the full 45,970
    while the SSTB stays capped — confirming the phaseout is SSTB-specific — but
    the emulator cannot inject that W-2 input per record, so the values here are
    the emulator's own.)"""
    base = {
        "taxsimid": 1,
        "year": 2025,
        "state": 44,
        "mstat": 1,
        "depx": 0,
        "page": 40,
        "sage": 0,
        "pwages": 0.0,
        "swages": 0.0,
        "idtl": 2,
    }
    non_sstb = _run_single({**base, "pbusinc": 260_000.0})
    sstb = _run_single({**base, "pprofinc": 260_000.0})

    assert non_sstb["qbid"] == pytest.approx(17_143, abs=50), (
        f"non-SSTB pbusinc QBID {non_sstb['qbid']} should be ~17,143"
    )
    assert sstb["qbid"] == pytest.approx(5_983, abs=50), (
        f"SSTB pprofinc QBID {sstb['qbid']} should be the further-phased ~5,983"
    )
    # The SSTB applicable-percentage phaseout strictly reduces its deduction
    # below the non-SSTB one at the same income.
    assert sstb["qbid"] < non_sstb["qbid"]


def test_sstb_qbid_fully_eliminated_far_above_threshold():
    """Far above the phaseout band ($300k single), SSTB professional income is
    fully phased out — QBID drops to 0 — confirming the § 199A(d)(3) SSTB
    treatment reaches complete elimination. pprofinc → sstb_self_employment_income
    is the mapping under test."""
    base = {
        "taxsimid": 1,
        "year": 2025,
        "state": 44,
        "mstat": 1,
        "depx": 0,
        "page": 40,
        "sage": 0,
        "pwages": 0.0,
        "swages": 0.0,
        "idtl": 2,
    }
    sstb = _run_single({**base, "pprofinc": 300_000.0})
    assert sstb["qbid"] == pytest.approx(0.0, abs=1.0), (
        f"SSTB QBID {sstb['qbid']} should be fully phased out at $300k"
    )


def test_pbusinc_and_psemp_are_identical():
    """Per Dan's spec, active QBI (businc) is identical to self-employment
    (semp): same active participation, SECA, and QBID-without-phaseout. $100k
    of each must produce the same AGI, taxable income, tax, QBID, and FICA."""
    psemp = _run_single(
        {
            "taxsimid": 1,
            "year": 2025,
            "state": 44,
            "mstat": 1,
            "depx": 0,
            "page": 40,
            "sage": 0,
            "pwages": 0.0,
            "swages": 0.0,
            "idtl": 2,
            "psemp": 100_000.0,
        }
    )
    pbusinc = _run_single(
        {
            "taxsimid": 1,
            "year": 2025,
            "state": 44,
            "mstat": 1,
            "depx": 0,
            "page": 40,
            "sage": 0,
            "pwages": 0.0,
            "swages": 0.0,
            "idtl": 2,
            "pbusinc": 100_000.0,
        }
    )
    for col in ["v10", "v18", "fiitax", "qbid", "fica"]:
        assert psemp[col] == pytest.approx(pbusinc[col], abs=1.0), f"mismatch on {col}"


def test_pbusinc_spouse_routes_to_spouse():
    """MFJ: sbusinc/ssemp populate the spouse's self_employment_income while
    psemp/pbusinc populate the primary's. A record with only sbusinc set must
    put the income on the spouse, not the primary, so per-person SECA and QBID
    are computed correctly."""
    from policyengine_taxsim.runners.policyengine_runner import (
        TaxsimMicrosimDataset,
    )
    from policyengine_us import Microsimulation

    df = pd.DataFrame(
        [
            {
                "taxsimid": 1,
                "year": 2025,
                "state": 44,
                "mstat": 2,
                "depx": 0,
                "page": 45,
                "sage": 45,
                "pwages": 0.0,
                "swages": 0.0,
                "idtl": 2,
                "sbusinc": 80_000.0,
            }
        ]
    )
    for col in _INCOME_COLS:
        if col not in df.columns:
            df[col] = 0.0
    ds = TaxsimMicrosimDataset(df)
    ds.generate()
    sim = Microsimulation(dataset=ds)
    se = np.array(sim.calculate("self_employment_income", 2025))
    # Two people: primary (index 0) gets 0, spouse (index 1) gets 80k.
    assert len(se) == 2
    np.testing.assert_allclose(se, [0.0, 80_000.0])
