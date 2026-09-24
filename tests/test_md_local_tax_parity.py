"""
Maryland county/local income tax parity with TAXSIM.

The emulator zeroes PE's MD local income tax
(``PolicyEngineRunner._build_configured_sim``) because TAXSIM's MD ``siitax``
is state-only. This module pins that premise to taxsimtest output.

TAXSIM. MD records for 2022 and later run through ``mdtax22``, whose county
block (3.2% of MD taxable income less 3.2% of the federal EITC) the published
source (build 2026092316) switches off; builds 20260521 and cd2026090910
return state-only siitax. Build cd2026081819, bundled in August 2026 (#1150),
ran the block and added about $3,000 to MD siitax at $100k.
Records for 2021 and earlier run through ``mdtax77``, which has no county tax.

Maryland. Form 502 Instruction 19 taxes Maryland taxable net income at the
rate of the county of residence (.0225 to .0320 in 2021-2024, up to .0330 in
2025) and allows a local EITC of the federal EITC times 10x the local rate.
TAXSIM input has no county, so no single rate is right; PE-US would fall back
to Allegany County. See #1062.

Expected values are siitax from taxsimtest builds 20260521 and cd2026090910,
which agree on every record here.
"""

import io

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner
from policyengine_us import Simulation

from policyengine_taxsim.cli import cli
from policyengine_taxsim.core.input_mapper import form_household_situation
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

_COLUMNS = [
    "taxsimid",
    "year",
    "state",
    "mstat",
    "page",
    "sage",
    "depx",
    "age1",
    "age2",
    "pwages",
    "idtl",
]

# taxsimid, year, mstat, page, sage, depx, age1, age2, pwages, expected siitax.
# Build cd2026081819 values are noted where its county block changes them.
MD_RECORDS = [
    (1, 2021, 1, 40, 0, 0, 0, 0, 100000, 4433.88),  # mdtax77: no county block
    (2, 2022, 1, 40, 0, 0, 0, 0, 100000, 4431.50),  # cd2026081819: 7452.30
    (3, 2022, 2, 40, 40, 0, 0, 0, 300000, 14805.75),  # cd2026081819: 24250.55
    (4, 2023, 1, 40, 0, 0, 0, 0, 100000, 4424.38),  # cd2026081819: 7440.38
    (5, 2024, 1, 40, 0, 0, 0, 0, 100000, 4417.25),  # cd2026081819: 7428.45
    (6, 2024, 2, 40, 40, 0, 0, 0, 100000, 4134.63),  # cd2026081819: 6955.43
    # Local EITC and poverty credits would offset part of a county tax.
    (7, 2024, 1, 40, 0, 2, 8, 5, 45000, 236.21),  # cd2026081819: 1122.04
    (8, 2024, 2, 40, 40, 0, 0, 0, 20000, 0.00),  # cd2026081819: 304.91
    (9, 2025, 1, 40, 0, 0, 0, 0, 100000, 4386.38),  # cd2026081819: 7376.78
    (10, 2025, 2, 40, 40, 0, 0, 0, 100000, 4075.25),  # cd2026081819: 6856.05
]

# Bundled builds known to run TAXSIM's MD county block. The binary guard
# xfails on these and fails on any other build that does the same.
_COUNTY_BLOCK_BUILDS = frozenset({"cd2026081819"})
_COUNTY_BLOCK_RATE = 0.032


def _records_csv() -> str:
    lines = [",".join(_COLUMNS)]
    for *inputs, _ in MD_RECORDS:
        tid, year, mstat, page, sage, depx, age1, age2, pwages = inputs
        row = [tid, year, 21, mstat, page, sage, depx, age1, age2, pwages, 2]
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines) + "\n"


def _expected() -> pd.Series:
    return pd.Series({r[0]: r[-1] for r in MD_RECORDS}, name="siitax")


def _by_taxsimid(df: pd.DataFrame) -> pd.DataFrame:
    df = df[pd.to_numeric(df["taxsimid"], errors="coerce").notna()].copy()
    df["taxsimid"] = df["taxsimid"].astype(float).astype(int)
    return df.set_index("taxsimid")


@pytest.fixture(scope="module")
def emulator_siitax() -> pd.Series:
    result = CliRunner().invoke(cli, [], input=_records_csv())
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output[result.output.find("taxsimid,") :]
    return _by_taxsimid(pd.read_csv(io.StringIO(out)))["siitax"].astype(float)


@pytest.mark.parametrize("record", MD_RECORDS, ids=lambda r: f"id{r[0]}-{r[1]}")
def test_emulator_md_siitax_is_state_only(emulator_siitax, record):
    """Emulator MD siitax matches TAXSIM's state-only siitax."""
    taxsimid, year, *_, expected = record
    assert emulator_siitax[taxsimid] == pytest.approx(expected, abs=1.0), (
        f"MD {year} record {taxsimid}: emulator siitax "
        f"{emulator_siitax[taxsimid]} vs TAXSIM {expected}. A gap near 3% of "
        "MD taxable income means PE's county tax is no longer zeroed."
    )


@pytest.mark.parametrize(
    "record", [MD_RECORDS[4], MD_RECORDS[5]], ids=["single", "joint"]
)
def test_single_household_path_md_siitax_is_state_only(record):
    """The single-household path (used for --logs YAML tests) zeroes MD county
    tax too, so its situations reproduce the batch path's state-only siitax."""
    taxsimid, year, mstat, page, sage, depx, _, _, pwages, expected = record
    taxsim_vars = {
        "taxsimid": taxsimid,
        "year": year,
        "state": 21,
        "mstat": mstat,
        "page": page,
        "sage": sage,
        "depx": depx,
        "pwages": pwages,
    }
    situation = form_household_situation(year, "MD", taxsim_vars)
    tax_unit = situation["tax_units"]["your tax unit"]
    assert tax_unit["md_local_income_tax_before_credits"] == {str(year): 0}
    siitax = Simulation(situation=situation).calculate("state_income_tax", year)[0]
    assert siitax == pytest.approx(expected, abs=1.0)


def test_single_household_path_leaves_other_states_alone():
    taxsim_vars = {"taxsimid": 1, "year": 2024, "state": 47, "mstat": 1}
    taxsim_vars.update({"page": 40, "depx": 0, "pwages": 100000})
    situation = form_household_situation(2024, "VA", taxsim_vars)
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "md_local_income_tax_before_credits" not in tax_unit


def test_bundled_taxsim_md_siitax_is_state_only():
    """The bundled binary still reports state-only MD siitax, the premise of
    the emulator's county-tax zeroing."""
    records = pd.read_csv(io.StringIO(_records_csv()))
    runner = TaxsimRunner(records)
    out = _by_taxsimid(runner.run(show_progress=False))
    build = getattr(runner, "binary_build_date", "unknown")

    expected = _expected()
    siitax = out["siitax"].reindex(expected.index).astype(float)
    if np.allclose(siitax, expected, rtol=0, atol=0.02):
        return

    # The county block's signature: 3.2% of MD taxable income (v36) less
    # 3.2% of the federal EITC (v25), for 2022+ records only.
    year = records.set_index("taxsimid")["year"].reindex(expected.index)
    county_tax = _COUNTY_BLOCK_RATE * (out["v36"] - out["v25"]).reindex(expected.index)
    with_county = expected + np.where(year >= 2022, county_tax, 0.0)
    runs_county_block = np.allclose(siitax, with_county, rtol=0, atol=0.02)

    table = pd.DataFrame(
        {"year": year, "taxsim": siitax, "state_only": expected}
    ).to_string()
    if runs_county_block and build in _COUNTY_BLOCK_BUILDS:
        pytest.xfail(
            f"Bundled TAXSIM build {build} runs the MD county block (#1150); "
            "later builds switch it off (#1206)."
        )
    if runs_county_block:
        pytest.fail(
            f"Bundled TAXSIM build {build} adds 3.2% MD county tax to siitax. "
            "The emulator zeroes MD local tax because TAXSIM's MD siitax is "
            "state-only. Check whether the bundled binary is stale "
            "(resources/taxsimtest/README.md) or NBER switched the county "
            "block back on; if the latter, revisit the MD zeroing in "
            f"PolicyEngineRunner._build_configured_sim.\n{table}"
        )
    pytest.fail(
        f"Bundled TAXSIM build {build} MD siitax differs from the pinned "
        f"state-only values, and not by the county block.\n{table}"
    )
