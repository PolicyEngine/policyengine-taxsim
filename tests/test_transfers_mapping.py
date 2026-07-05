"""
Tests for mapping TAXSIM `transfers` (#19) to PolicyEngine general_assistance.

TAXSIM `transfers` is non-taxable transfer income (welfare, workers comp,
veterans benefits, child support) that affects state property-tax-rebate
eligibility but is not federally taxable. It maps to `general_assistance`,
a non-taxable input variable counted in state household-income tests (e.g.
Michigan household resources). See taxsim #455.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _row(state: int, transfers: float, extra: str = "pwages", extra_val: float = 30000.0):
    record = (
        f"taxsimid,year,state,mstat,page,sage,depx,{extra},transfers,idtl\n"
        f"1,2025,{state},1,67,0,0,{extra_val},{transfers},2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    assert idx != -1, f"No CSV output:\n{out}"
    return pd.read_csv(io.StringIO(out[idx:])).iloc[0]


def test_transfers_not_federally_taxable():
    """transfers must not change federal AGI or federal tax (state=0)."""
    r0 = _row(state=0, transfers=0)
    r5 = _row(state=0, transfers=5000)
    assert r0["fiitax"] == r5["fiitax"], "transfers changed federal tax"
    assert r0["v10"] == r5["v10"], "transfers changed federal AGI"


def test_transfers_flow_into_mi_household_resources():
    """In Michigan, transfers raise total household resources, reducing the
    refundable property-tax-rebate/home-heating credit (less negative siitax)."""
    r0 = _row(state=23, transfers=0, extra="gssi", extra_val=928.58)
    r5 = _row(state=23, transfers=5000, extra="gssi", extra_val=928.58)
    # Higher household resources -> smaller refundable credit -> siitax rises
    # toward 0 (becomes less negative).
    assert r5["siitax"] > r0["siitax"], (
        f"transfers did not reduce the MI credit: "
        f"siitax {r0['siitax']} (t=0) vs {r5['siitax']} (t=5000)"
    )
