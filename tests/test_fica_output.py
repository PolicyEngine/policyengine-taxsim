"""
Regression test for the `fica` output column.

TAXSIM's `fica` column is the *combined* employee + employer FICA (OASDI +
HI, including Additional Medicare Tax); `tfica` is the employee-only half.
The `fica` column was mapped to the `na_pe` sentinel (always 0.0) even after
the PolicyEngine-US `taxsim_fica` variable shipped, so the emulator emitted
0.0 for FICA. This maps `fica -> taxsim_fica` so the combined amount is
emitted. See policyengine-taxsim#21.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _fica_columns(pwages: int = 10000):
    """Run a single-earner record and return (fica, tfica) from CSV output."""
    record = (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        f"1,2025,0,1,40,0,0,{pwages},2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    # The CSV header line begins with "taxsimid," (a tqdm progress bar may
    # be prepended to the same physical line, so split on that prefix).
    for line in result.output.splitlines():
        idx = line.find("taxsimid,")
        if idx != -1:
            header = line[idx:]
            data_start = result.output.index(header) + len(header)
            data_line = result.output[data_start:].splitlines()[1]
            df = pd.read_csv(io.StringIO(header + "\n" + data_line))
            return df["fica"].iloc[0], df["tfica"].iloc[0]
    raise AssertionError(f"No CSV header found in output:\n{result.output}")


def test_fica_is_combined_employee_and_employer():
    """$10,000 wages → employee 7.65% ($765) + employer 7.65% ($765) = $1,530."""
    fica, tfica = _fica_columns(pwages=10000)
    assert fica == 1530.0, f"expected combined FICA 1530.0, got {fica}"


def test_tfica_is_employee_half():
    """tfica is the employee-only half ($765) — regression guard."""
    _, tfica = _fica_columns(pwages=10000)
    assert tfica == 765.0, f"expected employee FICA 765.0, got {tfica}"


def test_fica_is_not_zeroed():
    """`fica` must not regress to the old na_pe sentinel (0.0)."""
    fica, _ = _fica_columns(pwages=10000)
    assert fica != 0.0, "fica regressed to na_pe sentinel (0.0)"
