"""
Maine's 2025 affordability payment must stay out of siitax.

H.P. 1491 (132nd Leg.), Part T creates a one-time $300-per-adult payment
for TY2025 filers under FAGI limits, paid by the State Tax Assessor from a
Special Revenue Fund in 2026-27. It is not a 1040ME line item, so neither
TAXSIM nor commercial software reports it in state liability. PolicyEngine
models it as a refundable credit (me_affordability_payment) to surface it
in tax-unit outputs; the emulator zeroes it so ME 2025 comparisons are not
off by $300-600 per record. See taxsim #1056.
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


def test_me_2025_joint_excludes_affordability_payment():
    """A 2025 ME joint filer under the FAGI limit must not receive the
    $600 ($300 x 2 adults) affordability payment through siitax.

    From taxsim #1056: MFJ ages 23/24, ~$10.5K wages. With the payment
    included, siitax carried an extra -$600; the couple's only remaining
    refundable credits (PTFC/STFC) total well under $600, so siitax must
    stay above (less negative than) -600."""
    r = _row(year=2025, mstat=2, page=23, sage=24, pwages=10476.19)
    assert r["siitax"] > -600, (
        f"siitax {r['siitax']} suggests the $600 affordability payment "
        f"is still included in ME state liability"
    )
