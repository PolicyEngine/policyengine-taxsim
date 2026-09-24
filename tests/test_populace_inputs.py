"""The Populace benchmark inputs and the converter that builds them.

The converter tests use a synthetic simulation, so they run without the
Populace H5 or a PolicyEngine model. The committed-file tests check
populace_households.csv against its provenance JSON.
"""

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


convert = _load("convert_h5_to_taxsim", "scripts/convert_h5_to_taxsim.py")
refresh = _load("refresh_dashboard", "scripts/refresh_dashboard.py")

POPULACE_CSV = ROOT / "populace_households.csv"
POPULACE_JSON = ROOT / "populace_households.json"


class _Result:
    def __init__(self, values):
        self.values = np.asarray(values)


class Sim:
    """A synthetic simulation: person arrays and tax-unit arrays by name."""

    def __init__(self, people, units, households):
        self.people = people
        self.units = units
        self.households = households

    def calculate(self, variable, period):
        for table in (self.people, self.units, self.households):
            if variable in table:
                return _Result(table[variable])
        return _Result(np.zeros(len(self.people["age"])))


def two_unit_household():
    """One Texas household with two tax units.

    Unit 10: a married couple with an infant and a 7-year-old; the infant has
    interest income and the 7-year-old is listed first. Unit 20: the couple's
    adult child, filing alone and paying half the household's rent.
    """
    people = {
        "person_tax_unit_id": [10, 10, 10, 10, 20],
        "person_household_id": [1, 1, 1, 1, 1],
        "is_tax_unit_head": [True, False, False, False, True],
        "is_tax_unit_spouse": [False, True, False, False, False],
        "is_tax_unit_dependent": [False, False, True, True, False],
        "age": [45.6, 43.2, 7.0, 0.4, 22.0],
        "employment_income": [80_000.0, 30_000.0, 0.0, 0.0, 25_000.0],
        "taxable_interest_income": [100.0, 50.0, 0.0, 999.0, 5.0],
        "non_qualified_dividend_income": [10.0, 0.0, 0.0, 0.0, 0.0],
        "social_security": [0.0, 0.0, 0.0, 4_000.0, 0.0],
        "taxable_pension_income": [1_000.0, 0.0, 0.0, 0.0, 0.0],
        "taxable_retirement_distributions": [0.0, 500.0, 0.0, 0.0, 0.0],
        "unemployment_compensation": [0.0, 2_000.0, 0.0, 0.0, 0.0],
        "real_estate_taxes": [6_000.0, 0.0, 0.0, 0.0, 0.0],
        "deductible_mortgage_interest": [9_000.0, 3_000.0, 0.0, 0.0, 0.0],
        "non_mortgage_interest": [0.0, 250.0, 0.0, 0.0, 0.0],
        "rent": [0.0, 0.0, 0.0, 0.0, 6_000.0],
        "veterans_benefits": [0.0, 0.0, 0.0, 0.0, 1_200.0],
        "partnership_s_corp_income": [-5_000.0, 0.0, 0.0, 0.0, 0.0],
    }
    units = {
        "tax_unit_id": [20, 10],
        "medical_expense_deduction": [0.0, 1_500.0],
        "charitable_deduction": [300.0, 2_000.0],
        "casualty_loss_deduction": [0.0, 0.0],
        "tax_unit_childcare_expenses": [0.0, 4_000.0],
        "filing_status": ["SINGLE", "JOINT"],
    }
    households = {"household_id": [1], "state_fips": [48]}
    return Sim(people, units, households)


@pytest.fixture
def converted():
    return convert.extract_taxsim_csv(two_unit_household(), 2024).set_index("taxsimid")


def test_one_row_per_tax_unit_in_taxsim_column_order(converted):
    assert list(converted.index) == [10, 20]
    assert list(converted.reset_index().columns) == refresh.INPUT_COLUMNS
    assert (converted["state"] == 44).all()  # Texas
    assert converted.loc[10, "mstat"] == 2 and converted.loc[20, "mstat"] == 1


def test_incomes_are_the_filers_not_the_dependents(converted):
    couple = converted.loc[10]
    assert (couple["pwages"], couple["swages"]) == (80_000, 30_000)
    assert (couple["pui"], couple["sui"]) == (0, 2_000)
    # The infant's interest and Social Security belong to the infant's return.
    assert couple["intrec"] == 160  # interest plus non-qualified dividends
    assert couple["gssi"] == 0
    assert couple["pensions"] == 1_500  # pensions plus IRA distributions
    assert couple["scorp"] == -5_000
    assert couple["nonprop"] == 0


def test_expenses_are_not_shared_across_tax_units(converted):
    assert converted.loc[10, "rentpaid"] == 0
    assert converted.loc[20, "rentpaid"] == 6_000
    assert converted.loc[10, "proptax"] == 6_000
    assert converted.loc[20, "proptax"] == 0
    assert converted.loc[20, "transfers"] == 1_200


def test_itemized_inputs_follow_taxsimtest_definitions(converted):
    couple = converted.loc[10]
    # mortgage: deductible mortgage interest + medical above the floor +
    # charitable after limits + casualty losses.
    assert couple["mortgage"] == 9_000 + 3_000 + 1_500 + 2_000
    # otheritem: interest other than on the residence.
    assert couple["otheritem"] == 250
    assert converted.loc[20, "mortgage"] == 300
    assert couple["childcare"] == 4_000


def test_dependent_ages_youngest_first_with_infants_coded_one(converted):
    couple = converted.loc[10]
    assert couple["depx"] == 2
    assert (couple["age1"], couple["age2"]) == (1, 7)
    assert np.isnan(couple["age3"])
    assert (couple["page"], couple["sage"]) == (45, 43)


def test_units_without_a_filer_are_dropped():
    sim = two_unit_household()
    sim.people["person_tax_unit_id"].append(30)
    sim.people["person_household_id"].append(1)
    sim.people["is_tax_unit_head"].append(False)
    sim.people["is_tax_unit_spouse"].append(False)
    sim.people["is_tax_unit_dependent"].append(True)
    for name, values in sim.people.items():
        if len(values) < 6:
            values.append(16.0 if name == "age" else 0.0)
    sim.units["tax_unit_id"].append(30)
    for name, values in sim.units.items():
        if len(values) < 3:
            values.append("HEAD_OF_HOUSEHOLD" if name == "filing_status" else 0.0)
    df = convert.extract_taxsim_csv(sim, 2024)
    assert list(df["taxsimid"]) == [10, 20]
    assert df.attrs["droppedNoFiler"] == 1
    assert df.attrs["filingStatus"] == {"JOINT": 1, "SINGLE": 1}


UNIT_DEDUCTIONS = (
    "medical_expense_deduction",
    "charitable_deduction",
    "casualty_loss_deduction",
    "tax_unit_childcare_expenses",
)


class RecordingSim(Sim):
    """A synthetic simulation whose set_input overrides calculate."""

    def __init__(self, *args):
        super().__init__(*args)
        self.inputs = {}

    def set_input(self, variable, period, values):
        self.inputs[variable] = np.asarray(values)
        table = self.units if variable == "filing_status" else self.people
        table[variable] = list(values)


def test_source_roles_replace_age_based_roles():
    """A 50-year-old head with a 20-year-old student dependent.

    policyengine-us's age rule makes the 20-year-old a spouse and the return
    joint; the build says the student is a dependent on a single return.
    """
    people = {
        "person_id": [101, 102],
        "person_tax_unit_id": [7, 7],
        "person_household_id": [1, 1],
        "is_tax_unit_head": [True, False],
        "is_tax_unit_spouse": [False, True],  # age-based inference
        "is_tax_unit_dependent": [False, False],
        "age": [50.0, 20.0],
        "employment_income": [170_000.0, 7_000.0],
    }
    units = {"tax_unit_id": [7], "filing_status": ["JOINT"]}
    for name in UNIT_DEDUCTIONS:
        units[name] = [0.0]
    sim = RecordingSim(people, units, {"household_id": [1], "state_fips": [6]})
    roles = {
        "person_id": np.array([102, 101]),  # any order; aligned by id
        "role": np.array(["DEPENDENT", "HEAD"]),
        "tax_unit_id": np.array([7]),
        "filing_status": np.array(["HEAD_OF_HOUSEHOLD"]),
    }
    convert.pin_source_roles(sim, 2024, roles)
    assert sim.inputs["is_tax_unit_spouse"].tolist() == [False, False]
    assert sim.inputs["is_tax_unit_dependent"].tolist() == [False, True]
    row = convert.extract_taxsim_csv(sim, 2024).iloc[0]
    assert (row["mstat"], row["swages"], row["depx"], row["age1"]) == (1, 0, 1, 20)
    assert row["pwages"] == 170_000


def test_incomplete_source_roles_are_rejected():
    sim = RecordingSim(
        {"person_id": [1, 2], "age": [40.0, 10.0]},
        {"tax_unit_id": [5]},
        {},
    )
    roles = {
        "person_id": np.array([1]),
        "role": np.array(["HEAD"]),
        "tax_unit_id": np.array([5]),
        "filing_status": np.array(["SINGLE"]),
    }
    with pytest.raises(ValueError, match="do not cover"):
        convert.pin_source_roles(sim, 2024, roles)


def test_negative_mortgage_is_rejected():
    sim = two_unit_household()
    sim.units["charitable_deduction"] = [-1_000.0, 0.0]
    with pytest.raises(ValueError, match="Negative mortgage"):
        convert.extract_taxsim_csv(sim, 2024)


def test_uncertified_model_is_refused(monkeypatch):
    monkeypatch.setattr(
        convert,
        "installed_versions",
        lambda packages: {"policyengine-us": "2.6.17", "policyengine-core": "3.32.6"},
    )
    with pytest.raises(RuntimeError, match="certified for"):
        convert.require_certified_model()


def test_coverage_counts_match_the_ecps_definitions():
    df = pd.read_csv(ROOT / "cps_households.csv")
    stats = convert.coverage(df)
    # The Enhanced CPS benchmark's published top-income coverage.
    assert stats["records"] == 111_347
    assert stats["totalIncomeAtLeast1M"] == 11_454
    assert stats["totalIncomeAtLeast10M"] == 6_867
    assert stats["maxTotalIncome"] == pytest.approx(348_046_180, abs=1)
    assert stats["longTermGainsNonzero"] == 34_552
    assert stats["scorpNonzero"] == 26_162
    assert all(stats["nonzero"][c] == 0 for c in convert.ITEMIZED_COLUMNS)


# The committed Populace inputs.


@pytest.fixture(scope="module")
def provenance():
    return json.loads(POPULACE_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def populace():
    return pd.read_csv(POPULACE_CSV)


def test_provenance_describes_the_committed_csv(provenance, populace):
    digest = hashlib.sha256(POPULACE_CSV.read_bytes()).hexdigest()
    assert provenance["outputSha256"] == digest
    assert (
        provenance["records"]
        == len(populace)
        == refresh.DATASETS["populace"]["records"]
    )
    build = convert.POPULACE_BUILD
    for key in ("buildId", "hfRepo", "hfRevision", "hfCommit", "h5File", "h5Sha256"):
        assert provenance[key] == build[key]
    assert provenance["conversionModel"] == build["certifiedModel"]
    assert provenance["rolesFrom"].startswith("tax_unit_role_input")
    assert provenance["droppedNoFiler"] == 0
    assert (populace["mstat"] == 2).sum() == provenance["filingStatus"]["JOINT"]
    # Regenerate the inputs whenever the converter changes.
    converter = ROOT / "scripts/convert_h5_to_taxsim.py"
    assert (
        provenance["converterSha256"]
        # Git may check the script out with CRLF line endings on Windows.
        == hashlib.sha256(converter.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )
    assert provenance["coverage"] == convert.coverage(populace)


def test_populace_inputs_cover_every_state_including_alabama(populace):
    with POPULACE_CSV.open(newline="") as f:
        assert csv.DictReader(f).fieldnames == refresh.INPUT_COLUMNS
    assert set(populace["state"]) == set(range(1, 52))
    assert (populace["state"] == 1).sum() > 1_000  # Alabama is SOI 1
    assert refresh.check_source(POPULACE_CSV) == len(populace)


def test_populace_inputs_test_itemized_deductions(populace):
    for column in convert.ITEMIZED_COLUMNS:
        assert (populace[column] > 0).sum() > 10_000, column
    assert (populace["mortgage"] >= 0).all()
    assert populace["taxsimid"].is_unique and (populace["taxsimid"] > 0).all()
    assert populace["mstat"].isin([1, 2]).all()


def test_documented_coverage_matches_the_inputs(provenance):
    """The dashboard's coverage table quotes these counts; keep them current."""
    docs = (ROOT / "dashboard/src/components/DocumentationContent.jsx").read_text(
        encoding="utf-8"
    )
    populace = provenance["coverage"]
    ecps = convert.coverage(pd.read_csv(ROOT / "cps_households.csv"))
    rows = {
        "Records (tax units)": "records",
        "Total income of $1 million or more": "totalIncomeAtLeast1M",
        "Total income of $10 million or more": "totalIncomeAtLeast10M",
        "Long-term capital gains": "longTermGainsNonzero",
        "S-corp or partnership income": "scorpNonzero",
    }
    for label, key in rows.items():
        assert f"['{label}', '{populace[key]:,}', '{ecps[key]:,}']" in docs, label
    for column, label in (
        ("proptax", "Property tax (proptax)"),
        ("mortgage", "Mortgage and other non-AMT deductions (mortgage)"),
        ("otheritem", "AMT-preference deductions (otheritem)"),
    ):
        row = f"['{label}', '{populace['nonzero'][column]:,}', '{ecps['nonzero'][column]:,}']"
        assert row in docs, label
    largest = [
        f"${stats['maxTotalIncome'] / 1e6:.1f} million" for stats in (populace, ecps)
    ]
    assert f"['Largest total income', '{largest[0]}', '{largest[1]}']" in docs
