"""
Federal SALT state-income-tax component: liability alignment (taxsim #1058).

The TAXSIM-35 binary deducts the state income-tax *liability* as the state
component of the federal SALT itemized deduction. PolicyEngine would
otherwise deduct its imputed ``state_withheld_income_tax`` (withholding runs
~19% above the actual liability), which overstates PE's federal itemized
deduction and is the dominant driver of federal mismatches vs the binary.

The runner (``PolicyEngineRunner._run_chunk``) fixes this with a two-sim flow:
pass 1 computes ``state_income_tax`` (the liability); pass 2 pins
``state_withheld_income_tax`` to that liability so
``state_and_local_sales_or_income_tax`` uses the liability. Two sims are
required because computing the liability in a single sim caches the federal
SALT/itemized chain, so a later ``set_input`` on the withholding would not
recompute the federal side.

Because the state liability does not depend on withholding, the state tax
(``siitax``) is identical between the two passes — only the federal side
moves. These records exercise that: a large interest income + $50k mortgage
so the filer itemizes and the state-tax component of SALT actually binds.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _run(record: str) -> pd.DataFrame:
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    assert idx != -1, f"No CSV output:\n{out}"
    return pd.read_csv(io.StringIO(out[idx:]))


def test_ny_974_fiitax_matches_binary_liability():
    """NY MFJ (#974): $210,165 interest + $50k mortgage, both spouses 45.

    With the SALT liability alignment, PE's federal itemized deduction uses
    the state income-tax *liability* (9,739.81), not the higher imputed
    withholding, so ``fiitax`` equals the TAXSIM-35 binary value 22,921.64
    exactly (pre-fix PE reported 22,751.44). ``siitax`` is unchanged."""
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,intrec,mortgage,idtl\n"
        "1,2025,33,2,45,45,0,210165.44,50000,2\n"
    )
    df = _run(record)
    fiitax = float(df["fiitax"].iloc[0])
    siitax = float(df["siitax"].iloc[0])
    assert abs(fiitax - 22921.64) < 2.0, (
        f"NY fiitax should match binary liability value 22921.64, got {fiitax}"
    )
    assert abs(siitax - 9739.81) < 1.0, (
        f"NY siitax (state liability) should be unchanged at 9739.81, got {siitax}"
    )


def test_ca_fiitax_moves_toward_binary():
    """CA MFJ: $168,341 interest + $50k mortgage, both spouses 45.

    The liability alignment raises ``fiitax`` from the pre-fix 14,219.18
    (imputed withholding in SALT) toward the binary by reducing the federal
    itemized deduction to the state liability. ``siitax`` is unchanged."""
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,intrec,mortgage,idtl\n"
        "1,2025,5,2,45,45,0,168340.64,50000,2\n"
    )
    df = _run(record)
    fiitax = float(df["fiitax"].iloc[0])
    siitax = float(df["siitax"].iloc[0])
    # Pre-fix (imputed withholding in SALT) was 14,219.18; the fix moves it up.
    assert fiitax > 14500.0, (
        f"CA fiitax should rise above the pre-fix 14219.18 toward the binary, "
        f"got {fiitax}"
    )
    assert abs(fiitax - 14998.48) < 2.0, (
        f"CA fiitax should be the liability-aligned 14998.48, got {fiitax}"
    )
    assert abs(siitax - 3929.35) < 1.0, (
        f"CA siitax (state liability) should be unchanged at 3929.35, got {siitax}"
    )
