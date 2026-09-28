"""
Regression test for zeroing PE-imputed means-tested transfers.

TAXSIM has no input columns for SSI, SNAP, TANF, WIC or state SSI
supplements. PolicyEngine imputes these for low-income records, and they
leak into state calculations that count cash public assistance as income —
most visibly the Massachusetts Senior Circuit Breaker (MGL c.62 §6(k)),
which zeroes out the credit for a low-income elderly renter.

These are formula-based benefit variables, so zeroing them in the dataset is
silently recomputed by the Microsimulation; the runner forces them to 0 with
set_input after building the sim. See policyengine-taxsim#1031.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _siitax(record: str) -> float:
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    assert idx != -1, f"No CSV output:\n{out}"
    df = pd.read_csv(io.StringIO(out[idx:]))
    return float(df["siitax"].iloc[0])


def test_ma_senior_circuit_breaker_not_wiped_by_imputed_transfers():
    """MA single elderly renter (#1031): SSI/SNAP/state-supplement must not
    inflate the circuit-breaker income base. Credit should be ~$710.57
    (refundable → negative siitax), matching TAXSIM/TaxAct, not $0."""
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,intrec,rentpaid,idtl\n"
        "1,2025,22,1,69,0,0,4306.37,4284.81,2\n"
    )
    siitax = _siitax(record)
    assert abs(siitax - (-710.57)) < 1.0, (
        f"expected MA Senior Circuit Breaker siitax ~ -710.57, got {siitax} "
        "(imputed transfers likely leaking into ma_scb_total_income)"
    )
