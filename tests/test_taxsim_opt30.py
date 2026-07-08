"""
Test for the --taxsim-opt30 compare flag.

TAXSIM option 30=1 switches the binary into its PSL-conformance test mode
(sets opt 27/88/91: rebates booked in the eligible year like PolicyEngine,
no smoothing, no federal-state iteration, plus per-state concessions). NBER
tests PolicyEngine records in this mode; default mode books one-time rebates
in the payout year instead. See taxsim #1068.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _run_compare(tmp_path, extra_args):
    """Run compare on a VA 2021 record whose $500 rebate timing differs
    between TAXSIM's default (payout year) and PSL (eligible year) modes."""
    input_csv = tmp_path / "va21.csv"
    input_csv.write_text(
        "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        "1,2021,47,2,45,45,0,60000,2\n"
    )
    out_dir = tmp_path / "out"
    result = CliRunner().invoke(
        cli,
        ["compare", str(input_csv), "--output-dir", str(out_dir)] + extra_args,
    )
    assert result.exit_code == 0, f"compare failed: {result.output}\n{result.exception}"
    df = pd.read_csv(out_dir / "comparison_results_2021.csv")
    taxsim = df[df.source == "taxsim"].iloc[0]
    pe = df[df.source == "policyengine"].iloc[0]
    return result.output, taxsim, pe


def test_opt30_aligns_rebate_timing(tmp_path):
    """With --taxsim-opt30 the binary books VA's 2021-liability rebate in
    2021 (like PolicyEngine), so the two engines agree exactly."""
    output, taxsim, pe = _run_compare(tmp_path, ["--taxsim-opt30"])
    assert "opt(30)=1" in output
    # Binary books the $500 rebate in the eligible year -> matches PE.
    assert abs(taxsim["siitax"] - pe["siitax"]) < 1.0, (
        f"opt30 run should align: TAXSIM {taxsim['siitax']} vs PE {pe['siitax']}"
    )
    assert taxsim["srebate"] > 400  # the rebate is reported in-year
