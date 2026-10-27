"""
Maine's 2025 affordability payment is reported in srebate and included in siitax.

H.P. 1491 (132nd Leg.), Part T creates a one-time $300-per-adult payment
for TY2025 filers under FAGI limits, paid by the State Tax Assessor from a
Special Revenue Fund in 2026-27. PolicyEngine models it as a refundable
credit (me_affordability_payment). The emulator first zeroed it, because
neither TAXSIM nor TaxAct reported it (taxsim #1056). The current TAXSIM
executable now reports it for 2025 in `srebate` and includes it in `siitax`
(taxsim #1463), so the emulator treats it like the other one-time rebates in
ONE_TIME_REBATE_VARIABLES. The rebate-neutral total, siitax + srebate, leaves
the payment out, as before.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli

ME = 20


def _row(year: int, mstat: int, page: int, sage: int, pwages: float):
    record = (
        f"taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        f"1,{year},{ME},{mstat},{page},{sage},0,{pwages},2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    assert idx != -1, f"No CSV output:\n{out}"
    return pd.read_csv(io.StringIO(out[idx:])).iloc[0]


def test_me_2025_joint_reports_affordability_payment_in_srebate():
    """A 2025 ME joint filer under the FAGI limit gets $300 x 2 adults.

    From taxsim #1056: MFJ ages 23/24, ~$10.5K wages. The $600 is in srebate,
    and the couple's only other refundable credits (PTFC/STFC) total well
    under $600, so siitax + srebate stays above -600."""
    r = _row(year=2025, mstat=2, page=23, sage=24, pwages=10476.19)
    assert r["srebate"] == 600
    assert r["siitax"] + r["srebate"] > -600, (
        f"siitax {r['siitax']} + srebate {r['srebate']} suggests the $600 "
        f"affordability payment is counted twice or left out of srebate"
    )


def test_me_2025_single_above_fagi_limit_gets_no_payment():
    """A single filer with federal AGI of $50,000 or more is not eligible."""
    r = _row(year=2025, mstat=1, page=40, sage=0, pwages=60000)
    assert r["srebate"] == 0


def test_me_2024_has_no_affordability_payment():
    """The payment is for tax year 2025 only."""
    r = _row(year=2024, mstat=2, page=23, sage=24, pwages=10476.19)
    assert r["srebate"] == 0
