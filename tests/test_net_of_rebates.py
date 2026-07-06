"""
Tests for rebate-aware state tax comparison (--net-of-rebates).

TAXSIM includes one-time state rebates in `siitax` in the payout year and
reports them in the `srebate` output column; PolicyEngine books them to the
liability year inside `state_income_tax`. Scoring `siitax + srebate` on both
sides removes this timing-convention difference without changing either
engine (see taxsim #1068, convention #716). The emulator emits PE's one-time
rebates in `srebate` via the state_variables mapping in
variable_mappings.yaml.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli
from policyengine_taxsim.comparison.comparator import (
    TaxComparator,
    ComparisonConfig,
)


def _frames(siitax_t, srebate_t, siitax_p, srebate_p):
    ids = list(range(1, len(siitax_t) + 1))
    tx = pd.DataFrame(
        {
            "taxsimid": ids,
            "fiitax": 100.0,
            "siitax": siitax_t,
            "srebate": srebate_t,
        }
    )
    pe = pd.DataFrame(
        {
            "taxsimid": ids,
            "fiitax": 100.0,
            "siitax": siitax_p,
            "srebate": srebate_p,
        }
    )
    return tx, pe


def test_rebate_timing_difference_mismatches_by_default():
    """TAXSIM siitax includes a $250 payout-year rebate that PE booked to a
    different year: raw siitax differs by $250 -> mismatch by default."""
    tx, pe = _frames([-500.0], [250.0], [-250.0], [0.0])
    r = TaxComparator(tx, pe, ComparisonConfig()).compare()
    assert r.state_match_percentage == 0.0


def test_net_of_rebates_matches_rebate_timing_difference():
    """Under net_of_rebates the same record matches:
    -500 + 250 == -250 + 0."""
    tx, pe = _frames([-500.0], [250.0], [-250.0], [0.0])
    r = TaxComparator(tx, pe, ComparisonConfig(net_of_rebates=True)).compare()
    assert r.state_match_percentage == 100.0


def test_net_of_rebates_still_flags_real_differences():
    """net_of_rebates is not a blanket pass: a genuine $200 liability gap
    remains a mismatch (-500 + 250 = -250 vs -50 + 0 = -50)."""
    tx, pe = _frames([-500.0], [250.0], [-50.0], [0.0])
    r = TaxComparator(tx, pe, ComparisonConfig(net_of_rebates=True)).compare()
    assert r.state_match_percentage == 0.0


def test_net_of_rebates_treats_missing_srebate_as_zero():
    """A PE frame without an srebate column is treated as srebate=0."""
    tx, pe = _frames([-500.0], [250.0], [-250.0], [0.0])
    pe = pe.drop(columns=["srebate"])
    r = TaxComparator(tx, pe, ComparisonConfig(net_of_rebates=True)).compare()
    assert r.state_match_percentage == 100.0


def test_net_of_rebates_does_not_touch_federal():
    """The flag only adjusts the state comparison; a federal gap still
    mismatches and a federal match still matches."""
    tx, pe = _frames([-500.0], [250.0], [-250.0], [0.0])
    tx["fiitax"] = 100.0
    pe["fiitax"] = 400.0
    r = TaxComparator(tx, pe, ComparisonConfig(net_of_rebates=True)).compare()
    assert r.federal_match_percentage == 0.0
    assert r.state_match_percentage == 100.0


def test_emulator_emits_me_2021_relief_rebate_in_srebate():
    """A ME 2021 record (SOI 20) should emit srebate ~= $850
    (me_relief_rebate), which PE books to the 2021 liability year. The same
    record in 2022 should emit srebate = 0: PE's rebate variables can stay
    nonzero after the one-time year, so srebate is gated by the years the
    rebate sits in the state's credit lists (i.e. the years PE actually
    nets it into siitax)."""
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        "1,2021,20,1,40,0,0,30000,2\n"
        "2,2022,20,1,40,0,0,30000,2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    df = pd.read_csv(io.StringIO(out[idx:]))
    # CliRunner interleaves progress lines with the CSV; keep data rows only.
    df = df[pd.to_numeric(df["taxsimid"], errors="coerce").notna()]
    df["taxsimid"] = df["taxsimid"].astype(float).astype(int)
    df = df.set_index("taxsimid")
    df["srebate"] = df["srebate"].astype(float)
    assert abs(df.loc[1, "srebate"] - 850.0) <= 1.0, (
        f"ME 2021 srebate {df.loc[1, 'srebate']} != 850"
    )
    assert df.loc[2, "srebate"] == 0.0, (
        f"ME 2022 srebate {df.loc[2, 'srebate']} should be 0 "
        "(rebate booked to 2021 only)"
    )
