"""
The emulator keeps the Additional Medicare Tax (AddMed; Form 8959,
IRC § 3101(b)(2) on wages, § 1401(b)(2) on self-employment income) out
of `fiitax` in every tax year. AddMed is counted in `tfica`/`fica` and
reported in the `addmed` column instead.

Basis:
- On taxsim #416 (2025-08-20), shown AddMed inside fiitax, TAXSIM's
  author replied that it "is actually part of FICA not general
  revenue. I will fix that."
- On taxsim #1225 (2026-09-24), shown AddMed counted in both fiitax
  and tfica, he called it "an error that was present in 2000-2023"
  (AddMed itself starts in 2013), said he believed he had corrected it,
  and restated the rule: "The .009 tax on excess earnings income is in
  fica and tfica".
- The bundled taxsimtest (build cd2026081819) keeps AddMed out of
  fiitax for tax years 2024 and later and counts it in tfica in every
  year.

Bundled-binary difference: the bundled cd2026081819 predates that
correction, so for 2013-2023 it still adds AddMed to fiitax as well as
to tfica.
(NBER's taxsimtest page, "Output Results", also still lists "Additional
Medicare Tax" in the fiitax definition.) taxsimtest output, single, TX,
$400K wages, idtl=2:

    year  fiitax      v28         addmed   tfica
    2023  108847.00   107047.00   1800.00  17532.40
    2024  105264.75   105264.75   1800.00  18053.20

The emulator does not copy the 2013-2023 double count, so the expected
fiitax values below are the binary's fiitax minus its addmed for
2013-2023 and the binary's fiitax as-is from 2024. The
`test_taxsimtest_*` tests pin the binary's own behavior, so a refreshed
build that changes it gets noticed.
"""

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

# Last tax year in which taxsimtest cd2026081819 adds AddMed to fiitax.
LAST_BINARY_YEAR_WITH_ADDMED_IN_FIITAX = 2023

# taxsimtest cd2026081819, idtl=2, single, TX, $400K wages:
# year -> (fiitax, addmed, tfica).
TAXSIMTEST_SINGLE_400K_TX = {
    2021: (111951.75, 1800.00, 16453.60),
    2023: (108847.00, 1800.00, 17532.40),
    2024: (105264.75, 1800.00, 18053.20),
    2025: (104034.75, 1800.00, 18518.20),
}

# taxsimtest cd2026081819, idtl=2, CA: (taxsimid, year, mstat, pwages,
# swages) -> (fiitax, addmed).
TAXSIMTEST_CA_HIGH_WAGE = {
    (11, 2023, 1, 500_000.0, 0.0): (144747.00, 2700.00),
    (12, 2023, 2, 500_000.0, 500_000.0): (296415.00, 6750.00),
    (13, 2024, 1, 500_000.0, 0.0): (140264.75, 2700.00),
    (14, 2024, 2, 500_000.0, 500_000.0): (285321.50, 6750.00),
}

# Federal marginal rate on wages at $400K. taxsimtest cd2026081819
# returns frate = 0, so the ground truth is the binary's own +$100 wage
# difference on the same basis as fiitax above. For 2021, 2023, 2024
# and 2025 that difference is exactly 35.00 (for example 2024:
# 105299.75 - 105264.75; 2023: (108882.90 - 1800.90) - (108847.00 -
# 1800.00)). Including AddMed would give 35.90.
FRATE_SINGLE_400K = 35.0

_IDTL0_ID = 20
_NIIT_IDS = {2023: 21, 2024: 22}


def _expected_fiitax(year, fiitax, addmed):
    """The binary's fiitax without the AddMed it adds for 2013-2023."""
    if year <= LAST_BINARY_YEAR_WITH_ADDMED_IN_FIITAX:
        return fiitax - addmed
    return fiitax


def _record(taxsimid, year, **overrides):
    record = {
        "taxsimid": taxsimid,
        "year": year,
        "state": 44,  # TX: no state income tax
        "mstat": 1,
        "depx": 0,
        "page": 45,
        "sage": 0,
        "pwages": 400_000.0,
        "swages": 0.0,
        "dividends": 0.0,
        "idtl": 2,
    }
    record.update(overrides)
    return record


@pytest.fixture(scope="module")
def emulator():
    """One PolicyEngineRunner pass over every emulator case, by taxsimid."""
    records = [_record(year, year) for year in TAXSIMTEST_SINGLE_400K_TX]
    records += [
        _record(
            tid,
            year,
            state=5,
            mstat=mstat,
            sage=45 if mstat == 2 else 0,
            pwages=pwages,
            swages=swages,
        )
        for (tid, year, mstat, pwages, swages) in TAXSIMTEST_CA_HIGH_WAGE
    ]
    records.append(_record(_IDTL0_ID, 2023, idtl=0))
    records += [
        _record(tid, year, dividends=100_000.0) for year, tid in _NIIT_IDS.items()
    ]
    df = pd.DataFrame(records)
    result = PolicyEngineRunner(df.copy(), logs=False).run(show_progress=False)
    return result.set_index("taxsimid")


@pytest.mark.parametrize("year", sorted(TAXSIMTEST_SINGLE_400K_TX))
def test_fiitax_excludes_addmed_in_every_year(emulator, year):
    fiitax, addmed, tfica = TAXSIMTEST_SINGLE_400K_TX[year]
    row = emulator.loc[year]
    expected = _expected_fiitax(year, fiitax, addmed)
    assert row["fiitax"] == pytest.approx(expected, abs=1.0), (
        f"{year}: expected fiitax {expected:.2f} (taxsimtest {fiitax:.2f}"
        f"{f' minus addmed {addmed:.2f}' if expected != fiitax else ''}), "
        f"got {row['fiitax']:.2f}. A gap of {addmed:.0f} means AddMed "
        "leaked into fiitax."
    )
    # AddMed is still reported: in its own column and inside tfica.
    assert row["addmed"] == pytest.approx(addmed, abs=0.5)
    assert row["tfica"] == pytest.approx(tfica, abs=0.5)
    assert row["frate"] == pytest.approx(FRATE_SINGLE_400K, abs=0.05)


@pytest.mark.parametrize(("case", "binary"), list(TAXSIMTEST_CA_HIGH_WAGE.items()))
def test_high_wage_ca_fiitax_excludes_addmed(emulator, case, binary):
    taxsimid, year, mstat, _, _ = case
    fiitax, addmed = binary
    expected = _expected_fiitax(year, fiitax, addmed)
    row = emulator.loc[taxsimid]
    assert row["fiitax"] == pytest.approx(expected, abs=1.0), (
        f"{year} mstat {mstat}: expected fiitax {expected:.2f}, got {row['fiitax']:.2f}"
    )
    assert row["addmed"] == pytest.approx(addmed, abs=0.5)


def test_idtl0_fiitax_matches_idtl2_without_addmed_column(emulator):
    """taxsimtest's fiitax does not depend on idtl, and it prints
    `addmed` only in the idtl=2 CSV."""
    fiitax, addmed, _ = TAXSIMTEST_SINGLE_400K_TX[2023]
    row = emulator.loc[_IDTL0_ID]
    assert row["fiitax"] == pytest.approx(fiitax - addmed, abs=1.0)
    assert pd.isna(row["addmed"])


@pytest.mark.parametrize("year", sorted(_NIIT_IDS))
def test_niit_stays_in_fiitax(emulator, year):
    """fiitax keeps the net investment income tax in every year. The
    binary decomposes $400K wages + $100K dividends in TX the same way:
    2023 fiitax 127626.57 = v28 122047.00 + niit 3779.57 + addmed 1800;
    2024 fiitax 124043.87 = v28 120264.75 + niit 3779.12."""
    row = emulator.loc[_NIIT_IDS[year]]
    assert row["niit"] > 0
    assert row["fiitax"] - row["v28"] == pytest.approx(row["niit"], abs=1.0)
    assert row["addmed"] == pytest.approx(1800.0, abs=0.5)


@pytest.mark.parametrize("year", [2023, 2024])
def test_single_household_path_matches_runner(year):
    """export_household (the per-record library/CLI path) uses the same
    fiitax and frate definitions as the Microsimulation runner. Its frate
    used to add AddMed's 0.9-point step in every year."""
    fiitax, addmed, _ = TAXSIMTEST_SINGLE_400K_TX[year]
    taxsim_input = _record(1, year)
    situation = generate_household(dict(taxsim_input))
    out = export_household(taxsim_input, situation, False, False)
    assert out["fiitax"] == pytest.approx(
        _expected_fiitax(year, fiitax, addmed), abs=1.0
    )
    assert out["addmed"] == pytest.approx(addmed, abs=0.5)
    assert out["frate"] == pytest.approx(FRATE_SINGLE_400K, abs=0.05)


def _run_taxsimtest(years):
    df = pd.DataFrame([_record(year, year) for year in years])
    return TaxsimRunner(df).run(show_progress=False).set_index("taxsimid")


def test_taxsimtest_keeps_addmed_out_of_2024_plus_fiitax():
    """Guards the convention the emulator follows against the bundled
    binary: from 2024 taxsimtest reports AddMed in addmed and tfica but
    not in fiitax. If a refreshed binary fails this, revisit the fiitax
    note in PolicyEngineRunner._extract_vectorized_results."""
    out = _run_taxsimtest([2024, 2025])
    for year in (2024, 2025):
        fiitax, addmed, tfica = TAXSIMTEST_SINGLE_400K_TX[year]
        row = out.loc[year]
        assert row["addmed"] == pytest.approx(addmed, abs=0.01)
        assert row["tfica"] == pytest.approx(tfica, abs=0.01)
        assert row["fiitax"] == pytest.approx(row["v28"], abs=0.01), (
            f"taxsimtest {year}: fiitax {row['fiitax']} != v28 {row['v28']}; "
            "the binary now puts AddMed in 2024+ fiitax."
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Bundled taxsimtest cd2026081819 predates the correction reported on "
        "taxsim #1225 and still adds AddMed to 2013-2023 fiitax as well as "
        "tfica. Once a refreshed binary passes, remove this marker and the "
        "bundled-binary notes in this module, tests/test_performance.py, the "
        "README and PolicyEngineRunner."
    ),
)
def test_taxsimtest_keeps_addmed_out_of_2013_2023_fiitax():
    out = _run_taxsimtest([2021, 2023])
    for year in (2021, 2023):
        row = out.loc[year]
        assert row["fiitax"] == pytest.approx(row["v28"], abs=0.01)
