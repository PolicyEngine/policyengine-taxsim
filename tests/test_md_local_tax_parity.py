"""
Maryland county/local income tax parity with TAXSIM.

TAXSIM's Maryland `siitax` is state-only: it applies no county tax when the
input carries no locality. PolicyEngine applies MD's residence-based county
tax (~2.25-3.20%) to every MD resident, over-stating MD siitax vs TAXSIM.
Since the TAXSIM input has no county, the emulator zeros PE's MD local income
tax to match TAXSIM's coverage. MD is the only state affected (every other
local-income-tax state needs a locality that PE isn't given). See #1062.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _siitax(state: int, wage: int = 100000):
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        f"1,2025,{state},1,40,0,0,{wage},2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    return pd.read_csv(io.StringIO(out[idx:]))["siitax"].iloc[0]


def test_md_siitax_excludes_county_tax():
    """MD (SOI 21) siitax should be state-only — the ~3% county tax is zeroed
    to match TAXSIM (which applies no county tax absent a locality)."""
    md = _siitax(21, 100000)
    # State-only MD tax on $100k single (2025) ~= $4,386; with the county tax
    # it would be ~$7,200. Assert it's the state-only figure.
    assert 4000 < md < 5000, (
        f"MD siitax {md} looks like it still includes the county tax "
        "(state-only expected ~$4,386)"
    )
