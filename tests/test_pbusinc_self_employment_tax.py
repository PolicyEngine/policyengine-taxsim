"""
The emulator applies self-employment tax to active business income
(`pbusinc`, `sbusinc`), as NBER's input documentation describes. The
bundled taxsimtest builds do not.

Basis for the emulator's treatment:
- NBER's taxsimtest input page (https://taxsim.nber.org/taxsimtest/,
  "Date last modified: 28 February 2026", retrieved 2026-10-09), item 26,
  under "The following are for the TCJA Business Tax Deduction":
  "pbusinc and sbusinc Primary and secondary Taxpayer's active income
  eligible for the QBI deduction without phaseout and assuming
  sufficient wages paid or capital to be eligible for the full
  deduction. Subject to NIIT, SECA and Medicare additional Earnings
  Tax."
- The emulator adds `pbusinc` to `psemp` and `sbusinc` to `ssemp` in
  PolicyEngine's `self_employment_income` (variable_mappings.yaml,
  taxsim #1051), so it bears self-employment tax and the Additional
  Medicare Tax. It bears no net investment income tax. The three taxes
  NBER's sentence lists cannot all fall on the same income: 26 U.S.C.
  1411(c)(6), under "Net investment income", says "Net investment
  income shall not include any item taken into account in determining
  self-employment income for such taxable year on which a tax is
  imposed by section 1401(b)."
- The macOS builds bundled earlier (cdate-2025Jul5, cdate-2025Aug23,
  cdate-20260521) gave `pbusinc` the same 2023 row as `psemp` below.

Bundled-binary difference: the bundled builds (cd2026081819 for macOS
and Linux) apply no self-employment tax and no Additional Medicare Tax
to `pbusinc` and `sbusinc`, and apply the net investment income tax
instead. On the records below the `pbusinc` row equals the `scorp` row.
taxsimtest cd2026081819, single, age 40, idtl=2:

    year state input    amount  fiitax    fica      v10        qbid      niit     addmed
    2023 CA    psemp    100000   9226.50  14129.55   92935.23  15817.05     0.00    0.00
    2023 CA    pbusinc  100000  10469.90      0.00  100000.00  17230.00     0.00    0.00
    2024 none  psemp    300000  47044.47  29634.30  285529.58  54185.92     0.00  693.45
    2024 none  pbusinc  300000  54548.90      0.00  300000.00  57080.00  3800.00    0.00

Open question: taxsim #1254 asks TAXSIM's author whether taxsimtest
should skip SECA on `pbusinc`. He replied (2026-09-29) that with SECA on
it "there is no passthru that is free of SECA", and asked to settle "the
treatment of all relevant 7 variables" together. Until that is settled,
the emulator keeps the documented treatment. The `test_taxsimtest_*`
tests pin the binary's own behavior, so a refreshed build that changes
it gets noticed.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from policyengine_taxsim import generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "generate_docs_reference", REPO / "scripts" / "generate_docs_reference.py"
)
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

# taxsimtest cd2026081819, idtl=2, single, age 40:
# (year, state, amount) -> {input: (fiitax, fica, v10, qbid, niit, addmed)}.
CA_2023 = (2023, 5, 100_000.0)
FEDERAL_2024 = (2024, 0, 300_000.0)
TAXSIMTEST = {
    CA_2023: {
        "psemp": (9226.50, 14129.55, 92935.23, 15817.05, 0.00, 0.00),
        "pbusinc": (10469.90, 0.00, 100000.00, 17230.00, 0.00, 0.00),
    },
    FEDERAL_2024: {
        "psemp": (47044.47, 29634.30, 285529.58, 54185.92, 0.00, 693.45),
        "pbusinc": (54548.90, 0.00, 300000.00, 57080.00, 3800.00, 0.00),
    },
}
OUTPUTS = ["fiitax", "fica", "v10", "qbid", "niit", "addmed"]
SOURCES = ["psemp", "pbusinc", "scorp"]

REVISIT = (
    "The bundled taxsimtest build treats pbusinc differently from "
    "cd2026081819. Check taxsim #1254 and NBER's input page, then revisit "
    "the 'Active business income' bullet in docs/design.md, the pbusinc "
    "entry in docs/reference/input_variables.yaml (and run "
    "scripts/generate_docs_reference.py), and the notes in this module."
)


def _record(taxsimid, year, state, **amounts):
    return {
        "taxsimid": taxsimid,
        "year": year,
        "state": state,
        "mstat": 1,
        "page": 40,
        "sage": 0,
        "depx": 0,
        "psemp": 0.0,
        "ssemp": 0.0,
        "pbusinc": 0.0,
        "sbusinc": 0.0,
        "scorp": 0.0,
        "idtl": 2,
        **amounts,
    }


def _single_source_frame():
    """One record per case and source, numbered case by case."""
    return pd.DataFrame(
        [
            _record(10 * case + position, year, state, **{source: amount})
            for case, (year, state, amount) in enumerate(TAXSIMTEST, start=1)
            for position, source in enumerate(SOURCES)
        ]
    )


def _row(results, case, source):
    index = list(TAXSIMTEST).index(case) + 1
    return results.loc[10 * index + SOURCES.index(source)]


@pytest.fixture(scope="module")
def emulator():
    # taxsimtest has no wage limit on the QBI deduction, so the comparison
    # assumes enough W-2 wages (taxsim #1404).
    runner = PolicyEngineRunner(_single_source_frame(), assume_w2_wages=True)
    return runner.run(show_progress=False).set_index("taxsimid")


@pytest.fixture(scope="module")
def taxsimtest():
    return (
        TaxsimRunner(_single_source_frame())
        .run(show_progress=False)
        .set_index("taxsimid")
    )


@pytest.mark.parametrize("case", list(TAXSIMTEST))
def test_emulator_taxes_pbusinc_as_taxsimtest_taxes_psemp(emulator, case):
    """The documented treatment: `pbusinc` gets taxsimtest's `psemp` row,
    with self-employment tax, its deduction from AGI, the QBI deduction
    and, above the threshold, the Additional Medicare Tax."""
    row = _row(emulator, case, "pbusinc")
    for name, expected in zip(OUTPUTS, TAXSIMTEST[case]["psemp"]):
        assert row[name] == pytest.approx(expected, abs=1.0), (case, name)


@pytest.mark.parametrize("case", list(TAXSIMTEST))
def test_emulator_gives_pbusinc_and_psemp_the_same_result(emulator, case):
    pbusinc = _row(emulator, case, "pbusinc").drop("taxsimid", errors="ignore")
    psemp = _row(emulator, case, "psemp").drop("taxsimid", errors="ignore")
    pd.testing.assert_series_equal(pbusinc, psemp, check_names=False)


@pytest.mark.parametrize("case", list(TAXSIMTEST))
def test_taxsimtest_applies_self_employment_tax_to_psemp(taxsimtest, case):
    """The reference the emulator's `pbusinc` treatment is checked against.
    Only the taxes are pinned: the bundled Windows build is older than the
    macOS and Linux builds and differs from them in other amounts."""
    row = _row(taxsimtest, case, "psemp")
    _, fica, *_ = TAXSIMTEST[case]["psemp"]
    assert row["fica"] == pytest.approx(fica, abs=0.01)
    assert row["v10"] < case[2]
    assert row["niit"] == 0


@pytest.mark.parametrize("case", list(TAXSIMTEST))
def test_taxsimtest_applies_no_self_employment_tax_to_pbusinc(taxsimtest, case):
    """The known difference: no self-employment tax, no deduction for it
    in AGI, no Additional Medicare Tax, and the net investment income tax
    above its threshold."""
    row = _row(taxsimtest, case, "pbusinc")
    for name, expected in zip(OUTPUTS, TAXSIMTEST[case]["pbusinc"]):
        assert row[name] == pytest.approx(expected, abs=0.01), (
            f"{case} {name}: expected {expected}, got {row[name]}. {REVISIT}"
        )


@pytest.mark.parametrize("case", list(TAXSIMTEST))
def test_taxsimtest_gives_pbusinc_the_scorp_row(taxsimtest, case):
    pbusinc = _row(taxsimtest, case, "pbusinc")
    scorp = _row(taxsimtest, case, "scorp")
    for name in OUTPUTS + ["siitax", "tfica"]:
        assert pbusinc[name] == pytest.approx(scorp[name], abs=0.01), (
            f"{case} {name}: pbusinc {pbusinc[name]}, scorp {scorp[name]}. {REVISIT}"
        )


GRID_YEARS = [2021, 2022, 2023, 2024, 2025]
GRID_AMOUNTS = [1_000.0, 15_000.0, 50_000.0, 100_000.0, 200_000.0, 300_000.0, 1e6]


def test_taxsimtest_pbusinc_and_sbusinc_bear_no_self_employment_tax_in_any_year():
    """For every year the emulator computes and from $1,000 to $1 million,
    on single and joint returns: `psemp` and `ssemp` bear self-employment
    tax, `pbusinc` and `sbusinc` bear none and enter AGI in full."""
    records = []
    for year in GRID_YEARS:
        for amount in GRID_AMOUNTS:
            for column in ("psemp", "pbusinc"):
                records.append((year, {column: amount}))
            for column in ("ssemp", "sbusinc"):
                records.append((year, {"mstat": 2, "sage": 40, column: amount}))
    frame = pd.DataFrame(
        [
            _record(taxsimid, year, 0, **amounts)
            for taxsimid, (year, amounts) in enumerate(records, start=1)
        ]
    )
    results = TaxsimRunner(frame).run(show_progress=False).set_index("taxsimid")
    for taxsimid, record in frame.set_index("taxsimid").iterrows():
        row = results.loc[taxsimid]
        if record["psemp"] or record["ssemp"]:
            assert row["fica"] > 0, dict(record)
            continue
        amount = record["pbusinc"] + record["sbusinc"]
        where = f"{dict(record)}. {REVISIT}"
        assert row["fica"] == 0, where
        assert row["tfica"] == 0, where
        assert row["addmed"] == 0, where
        assert row["v10"] == pytest.approx(amount, abs=0.01), where


def _same(first: dict, second: dict) -> bool:
    return first.keys() == second.keys() and all(
        np.array_equal(first[name], second[name]) for name in first
    )


whole_dollars = st.integers(min_value=-2_000_000, max_value=2_000_000)


@settings(max_examples=60, deadline=None)
@given(
    psemp=whole_dollars,
    pbusinc=whole_dollars,
    ssemp=whole_dollars,
    sbusinc=whole_dollars,
    mstat=st.sampled_from([1, 2, 6]),
    page=st.integers(min_value=18, max_value=95),
    sage=st.integers(min_value=18, max_value=95),
    state=st.integers(min_value=1, max_value=51),
    depx=st.integers(min_value=0, max_value=3),
)
def test_pbusinc_is_interchangeable_with_psemp(
    psemp, pbusinc, ssemp, sbusinc, mstat, page, sage, state, depx
):
    """Invariant: whatever the filing status, ages and state, moving
    `pbusinc` into `psemp` and `sbusinc` into `ssemp` leaves every
    PolicyEngine input unchanged. The emulator has no other treatment of
    active business income."""
    record = {
        "year": 2023,
        "state": state,
        "mstat": mstat,
        "page": page,
        "sage": sage,
        "depx": depx,
    }
    split = generator.read_inputs(
        {
            **record,
            "psemp": psemp,
            "pbusinc": pbusinc,
            "ssemp": ssemp,
            "sbusinc": sbusinc,
        }
    )
    merged = generator.read_inputs(
        {
            **record,
            "psemp": psemp + pbusinc,
            "pbusinc": 0,
            "ssemp": ssemp + sbusinc,
            "sbusinc": 0,
        }
    )
    assert _same(split["inputs"], merged["inputs"])


@settings(max_examples=60, deadline=None)
@given(
    psemp=whole_dollars,
    pbusinc=whole_dollars,
    ssemp=whole_dollars,
    sbusinc=whole_dollars,
    mstat=st.sampled_from([1, 2]),
    year=st.sampled_from(GRID_YEARS),
)
def test_single_household_path_sums_them_like_the_runner(
    psemp, pbusinc, ssemp, sbusinc, mstat, year
):
    """generate_household (the per-record library path) and the
    Microsimulation runner both put `psemp + pbusinc` on the primary
    taxpayer and `ssemp + sbusinc` on the spouse of a joint return."""
    record = {
        "taxsimid": 1,
        "year": year,
        "state": 5,
        "mstat": mstat,
        "page": 40,
        "sage": 40 if mstat == 2 else 0,
        "psemp": psemp,
        "pbusinc": pbusinc,
        "ssemp": ssemp,
        "sbusinc": sbusinc,
    }
    people = generate_household(dict(record))["people"]
    household_path = [people["you"]["self_employment_income"][str(year)]]
    if mstat == 2:
        household_path.append(
            people["your partner"]["self_employment_income"][str(year)]
        )

    inputs = generator.read_inputs({**record, "depx": 0})["inputs"]
    roles = generator.roles(inputs)
    runner_path = [inputs["self_employment_income"][roles["head"]].sum()]
    if mstat == 2:
        runner_path.append(inputs["self_employment_income"][roles["spouse"]].sum())

    expected = [psemp + pbusinc] + ([ssemp + sbusinc] if mstat == 2 else [])
    assert household_path == expected
    assert [float(amount) for amount in runner_path] == expected


def test_design_document_quotes_these_figures():
    """docs/design.md's known-differences entry gives the 2023 figures
    pinned above and points to the open question."""
    design = (REPO / "docs" / "design.md").read_text()
    entry = next(
        line
        for line in design.splitlines()
        if line.startswith("- **Active business income")
    )
    emulator_row = TAXSIMTEST[CA_2023]["psemp"]
    binary_row = TAXSIMTEST[CA_2023]["pbusinc"]
    for amount in (emulator_row[0], emulator_row[1], binary_row[0]):
        assert f"{amount:,.2f}" in entry, amount
    assert "issues/1254" in entry
    assert "tests/test_pbusinc_self_employment_tax.py" in entry
