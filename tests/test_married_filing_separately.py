"""TAXSIM mstat 6 (married filing separately).

TAXSIM-35 defines mstat 6 as one spouse's separate return (verbatim from
https://taxsim.nber.org/taxsimtest/): "6. separate (married). Note that
Married-separate is not usually desirable under US tax law." It also says
"swages must be zero for non-joint returns" and "It is an error to specify a
non-zero spouse age for an unmarried taxpayer" -- the binary rejects both.

The emulator used to build mstat 6 as a two-person household in the batch
(CLI) path, so PolicyEngine taxed it as a JOINT return, and as a plain single
filer in the single-household path. Both paths now build a single-person tax
unit whose head has ``is_separated`` and whose unit has
``cohabitating_spouses``:

- PolicyEngine-US derives filing_status SEPARATE from a separated head with no
  spouse in the unit, or HEAD_OF_HOUSEHOLD when a qualifying child lets
  IRC 7703(b) treat the filer as unmarried. taxsimtest does the same: mstat 6
  with a dependent child gets the head-of-household standard deduction,
  brackets, EITC and CTC.
- taxsimtest taxes mstat 6 Social Security with the zero base amount of
  IRC 86(c)(1)(C) ("zero in the case of a taxpayer who-- (i) is married ...
  but does not file a joint return for such year, and (ii) does not live apart
  from his spouse at all times during the taxable year"). PE-US applies that
  base to SEPARATE units only when cohabitating_spouses is set.

Every expected value below is taxsimtest output (bundled binary, build
cd2026081819, idtl=2), not a hand calculation. The mstat 1 value of the same
record is listed alongside to show what the test discriminates: each case is
one where TAXSIM's separate return differs from its single return (for the
child cases, where TAXSIM's mstat 6 result is the head-of-household result
rather than a separate return).

Known divergences deliberately not tested here (the emulator reproduces
PolicyEngine's reading of the statute, not these TAXSIM results):

- Additional Medicare Tax: taxsimtest uses the $200,000 threshold for mstat 6;
  IRC 3101(b)(2)(B) sets "in the case of a married taxpayer (as defined in
  section 7703) filing a separate return, 1/2 of the dollar amount determined
  under subparagraph (A)" ($125,000).
- 2025 senior deduction: taxsimtest allows the $6,000 to mstat 6; IRC
  151(d)(5)(C)(v) says "this subparagraph shall apply only if the taxpayer and
  the taxpayer's spouse file a joint return for the taxable year".
- Childless EITC: taxsimtest denies it for mstat 6 in 2022-2025 (and allows it
  in 2021); PE-US allows it from 2021 via
  gov.irs.credits.eitc.eligibility.separate_filer, although IRC 32(d)(2)(B)
  requires the separated filer to reside "with a qualifying child of the
  individual for more than one-half of such taxable year".
- mstat 6 with a dependent who is not a qualifying child (e.g. age 19 non-
  student or 25): taxsimtest assigns head of household; PE-US's IRC 7703(b)
  path counts only qualifying children, so PE computes SEPARATE.
- New York 2022-2025: taxsimtest returns siitax 0 (with staxbc -1e20) for
  every mstat 6 record; 2021 is computed normally.
- New Jersey property tax deduction: PE-US halves it for separate filers
  sharing a main home (cohabitating_spouses), per the 2025 NJ-1040
  instructions ("$7,500 if you and your spouse file separate returns but
  maintained the same main home"); taxsimtest does not.
"""

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.core.input_mapper import MSTAT_MARRIED_SEPARATE
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner
from policyengine_us import Microsimulation

# (case id, record inputs, taxsimtest mstat 6 output, taxsimtest mstat 1
# output for the same record). State 0 = federal only.
TAXSIM_CASES = [
    (
        "mfs_brackets_2023",
        {"year": 2023, "state": 0, "page": 40, "pwages": 400000},
        {"v19": 107832.5, "v28": 107832.5},
        {"v19": 107047.0, "v28": 107047.0},
    ),
    (
        "mfs_top_bracket_2021",
        {"year": 2021, "state": 0, "page": 40, "pwages": 700000},
        {"v28": 222617.75},
        {"v28": 218428.75},
    ),
    (
        "mfs_brackets_2025",
        {"year": 2025, "state": 0, "page": 40, "pwages": 400000},
        {"v28": 104203.75},
        {"v28": 104034.75},
    ),
    (
        "mfs_capital_loss_limit_2024",
        {"year": 2024, "state": 0, "page": 40, "pwages": 50000, "stcg": -10000},
        {"v10": 48500.0, "v28": 3836.0},
        {"v10": 47000.0, "v28": 3656.0},
    ),
    (
        "mfs_salt_cap_2022",
        {
            "year": 2022,
            "state": 0,
            "page": 40,
            "pwages": 150000,
            "proptax": 15000,
            "mortgage": 20000,
        },
        {"v17": 25000.0, "v18": 125000.0, "v28": 23835.5},
        {"v17": 30000.0, "v18": 120000.0, "v28": 22635.5},
    ),
    (
        "mfs_aged_standard_deduction_2022",
        {"year": 2022, "state": 0, "page": 70, "pwages": 40000},
        {"v13": 14350.0, "v28": 2872.5},
        {"v13": 14700.0, "v28": 2830.5},
    ),
    (
        "mfs_niit_threshold_2023",
        {"year": 2023, "state": 0, "page": 40, "pwages": 150000, "dividends": 60000},
        {"niit": 2280.0},
        {"niit": 380.0},
    ),
    (
        "mfs_social_security_zero_base_2021",
        {"year": 2021, "state": 0, "page": 70, "gssi": 20000},
        {"v10": 8500.0, "v12": 8500.0},
        {"v10": 0.0, "v12": 0.0},
    ),
    (
        "mfs_social_security_zero_base_2024",
        {"year": 2024, "state": 0, "page": 70, "gssi": 20000, "pensions": 30000},
        {"v10": 47000.0, "v12": 17000.0, "v28": 3470.0},
        {"v10": 39600.0, "v12": 9600.0, "v28": 2534.0},
    ),
    (
        "mfs_child_head_of_household_2021",
        {
            "year": 2021,
            "state": 0,
            "page": 35,
            "depx": 1,
            "age1": 5,
            "pwages": 20000,
            "childcare": 3000,
        },
        {"v13": 18800.0, "v22": 3600.0, "v24": 1500.0, "v25": 3541.3},
        {"v13": 18800.0, "v22": 3600.0, "v24": 1500.0, "v25": 3541.3},
    ),
    (
        "mfs_child_head_of_household_2023",
        {
            "year": 2023,
            "state": 0,
            "page": 35,
            "depx": 1,
            "age1": 5,
            "pwages": 20000,
            "childcare": 3000,
        },
        {"v13": 20800.0, "v25": 3995.0},
        {"v13": 20800.0, "v25": 3995.0},
    ),
    (
        "mfs_children_head_of_household_2025",
        {
            "year": 2025,
            "state": 0,
            "page": 35,
            "depx": 2,
            "age1": 5,
            "age2": 10,
            "pwages": 40000,
        },
        {"v13": 23625.0, "v22": 1637.5, "v25": 3645.51},
        {"v13": 23625.0, "v22": 1637.5, "v25": 3645.51},
    ),
    (
        "wv_mfs_brackets_2021",
        {"year": 2021, "state": 49, "page": 40, "pwages": 60000},
        {"siitax": 3207.5},
        {"siitax": 2655.0},
    ),
    (
        "wi_mfs_brackets_2021",
        {"year": 2021, "state": 50, "page": 40, "pwages": 250000},
        {"siitax": 14694.75},
        {"siitax": 12920.74},
    ),
    (
        "nm_mfs_brackets_2023",
        {"year": 2023, "state": 32, "page": 40, "pwages": 250000},
        {"siitax": 12153.85},
        {"siitax": 11553.35},
    ),
    (
        "ks_mfs_2023",
        {"year": 2023, "state": 17, "page": 40, "pwages": 60000},
        {"siitax": 2606.25},
        {"siitax": 2634.75},
    ),
    (
        "ut_mfs_retirement_2023",
        {"year": 2023, "state": 45, "page": 70, "gssi": 20000, "pensions": 30000},
        {"siitax": 1104.85},
        {"siitax": 750.15},
    ),
    (
        "or_mfs_itemizer_2023",
        {
            "year": 2023,
            "state": 38,
            "page": 45,
            "pwages": 90000,
            "proptax": 6000,
            "mortgage": 12000,
        },
        {"siitax": 5525.25},
        {"siitax": 5096.5},
    ),
]

CASE_IDS = [case[0] for case in TAXSIM_CASES]

# Dollar tolerance: TAXSIM prints cents; PE rounds some state computations
# differently by a few cents (e.g. WI 2021 at $250k: 14694.66 vs 14694.75).
TOLERANCE = 1.0


def _record(taxsimid, inputs, mstat):
    record = {
        "taxsimid": taxsimid,
        "mstat": mstat,
        "sage": 0,
        "depx": 0,
        "idtl": 2,
    }
    record.update(inputs)
    return record


@pytest.fixture(scope="module")
def batch_results():
    """Run every mstat 6 case through the batch (CLI) path in one call."""
    df = pd.DataFrame(
        [
            _record(i + 1, inputs, MSTAT_MARRIED_SEPARATE)
            for i, (_, inputs, _, _) in enumerate(TAXSIM_CASES)
        ]
    ).fillna(0)
    results = PolicyEngineRunner(df, logs=False).run(show_progress=False)
    results["taxsimid"] = results["taxsimid"].astype(float).astype(int)
    return results.set_index("taxsimid")


@pytest.mark.parametrize("case", TAXSIM_CASES, ids=CASE_IDS)
def test_batch_path_matches_taxsimtest(case, batch_results):
    case_id, inputs, expected, taxsim_mstat1 = case
    row = batch_results.loc[CASE_IDS.index(case_id) + 1]
    for column, value in expected.items():
        assert abs(float(row[column]) - value) <= TOLERANCE, (
            f"{case_id} {column}: emulator {row[column]} vs taxsimtest {value} "
            f"(taxsimtest mstat 1 gives {taxsim_mstat1[column]})"
        )


@pytest.mark.parametrize("case", TAXSIM_CASES, ids=CASE_IDS)
def test_single_household_path_matches_taxsimtest(case):
    case_id, inputs, expected, _ = case
    record = _record(1, inputs, MSTAT_MARRIED_SEPARATE)
    output = export_household(
        dict(record), generate_household(dict(record)), False, False
    )
    for column, value in expected.items():
        assert abs(float(output[column]) - value) <= TOLERANCE, (
            f"{case_id} {column}: single-household path {output[column]} "
            f"vs taxsimtest {value}"
        )


def test_bundled_taxsimtest_still_produces_expected_values():
    """Guard the hard-coded expectations: the bundled binary must still
    produce them, for mstat 6 and for the mstat 1 control."""
    rows = []
    for i, (_, inputs, _, _) in enumerate(TAXSIM_CASES):
        rows.append(_record(2 * i + 1, inputs, 1))
        rows.append(_record(2 * i + 2, inputs, MSTAT_MARRIED_SEPARATE))
    df = pd.DataFrame(rows).fillna(0)
    output = TaxsimRunner(df).run(show_progress=False)
    output["taxsimid"] = output["taxsimid"].astype(float).astype(int)
    output = output.set_index("taxsimid")
    for i, (case_id, _, expected, taxsim_mstat1) in enumerate(TAXSIM_CASES):
        for column in expected:
            assert float(output.loc[2 * i + 2, column]) == pytest.approx(
                expected[column], abs=0.01
            ), f"{case_id} mstat 6 {column}"
            assert float(output.loc[2 * i + 1, column]) == pytest.approx(
                taxsim_mstat1[column], abs=0.01
            ), f"{case_id} mstat 1 {column}"


def test_mfs_marginal_rate_uses_separate_brackets(batch_results):
    """frate is computed on a wage-perturbation branch of the simulation; the
    separate-return status must survive into that branch. taxsimtest's own
    finite difference for this record (v28 107832.50 at $400,000 wages,
    107869.50 at $400,100) is a 37% marginal rate; a single filer at the same
    wages is in the 35% bracket (107047.00 -> 107082.00)."""
    row = batch_results.loc[CASE_IDS.index("mfs_brackets_2023") + 1]
    assert float(row["frate"]) == pytest.approx(37.0, abs=0.01)


def _people_by_unit(sim, variable, year):
    values = np.asarray(sim.calculate(variable, year))
    unit_ids = np.asarray(sim.calculate("person_tax_unit_id", year))
    return [values[unit_ids == u].tolist() for u in np.unique(unit_ids)]


def test_batch_dataset_builds_separate_filer_without_spouse():
    """A mixed chunk: mstat 6 rows get a single-person unit (plus dependents)
    flagged is_separated/cohabitating_spouses; mstat 1 and 2 are unchanged."""
    year = 2023
    df = pd.DataFrame(
        [
            # single with a child -> head of household
            {"taxsimid": 1, "mstat": 1, "page": 35, "depx": 1, "age1": 5},
            # joint, no dependents
            {"taxsimid": 2, "mstat": 2, "page": 50, "sage": 48, "depx": 0},
            # separate with a child and a 25-year-old dependent
            {"taxsimid": 3, "mstat": 6, "page": 45, "depx": 2, "age1": 5, "age2": 25},
            # separate, no dependents
            {"taxsimid": 4, "mstat": 6, "page": 40, "depx": 0},
        ]
    )
    df["year"] = year
    df["state"] = 44
    df["pwages"] = 50000
    df["idtl"] = 2
    df = df.fillna(0)
    runner = PolicyEngineRunner(df, logs=False)
    chunk = runner._ensure_required_columns(df.copy())
    dataset = TaxsimMicrosimDataset(chunk)
    dataset.generate()
    try:
        sim = Microsimulation(dataset=dataset)
        assert _people_by_unit(sim, "is_tax_unit_spouse", year) == [
            [False, False],
            [False, True],
            [False, False, False],
            [False],
        ]
        assert _people_by_unit(sim, "is_separated", year) == [
            [False, False],
            [False, False],
            [True, False, False],
            [True],
        ]
        assert _people_by_unit(sim, "age", year) == [
            [35, 5],
            [50, 48],
            [45, 5, 25],
            [40],
        ]
        assert np.asarray(sim.calculate("cohabitating_spouses", year)).tolist() == [
            False,
            False,
            True,
            True,
        ]
        assert np.asarray(sim.calculate("filing_status", year)).tolist() == [
            "HEAD_OF_HOUSEHOLD",
            "JOINT",
            "HEAD_OF_HOUSEHOLD",
            "SEPARATE",
        ]
    finally:
        dataset.cleanup()


@pytest.mark.parametrize(
    "depx,expected_members,expected_status",
    [
        (0, ["you"], "SEPARATE"),
        (1, ["you", "your first dependent"], "HEAD_OF_HOUSEHOLD"),
    ],
)
def test_single_household_builds_separate_filer_without_spouse(
    depx, expected_members, expected_status
):
    from policyengine_us import Simulation

    record = {
        "taxsimid": 1,
        "year": 2023,
        "state": 44,
        "mstat": MSTAT_MARRIED_SEPARATE,
        "page": 40,
        "depx": depx,
        "age1": 5,
        "pwages": 50000,
    }
    situation = generate_household(record)
    tax_unit = situation["tax_units"]["your tax unit"]
    assert tax_unit["members"] == expected_members
    assert tax_unit["cohabitating_spouses"] == {"2023": True}
    assert "your partner" not in situation["people"]
    assert situation["people"]["you"]["is_separated"] == {"2023": True}
    sim = Simulation(situation=situation)
    assert sim.calculate("filing_status", 2023).decode_to_str().tolist() == [
        expected_status
    ]
