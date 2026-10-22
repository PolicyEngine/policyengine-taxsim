"""TAXSIM input has no student status, so every person is a non-student.

The emulator does not default anyone to being a student (taxsim #532, where
a 19-year-old dependent is a non-student). PE-US's ``is_full_time_student``
reads ``is_in_k12_school``, which PE-US imputes for ages 5 to 17, so a spouse
aged 17 or younger was a full-time student. IRC 21(d)(2)
(https://www.law.cornell.edu/uscode/text/26/21#d_2) then deemed them to have
earned income for the child and dependent care credit:

  > (2) Special rule for spouse who is a student or incapable of caring for
  > himself In the case of a spouse who is a student or a qualifying
  > individual described in subsection (b)(1)(C), for purposes of paragraph
  > (1), such spouse shall be deemed for each month during which such spouse
  > is a full-time student at an educational institution, or is such a
  > qualifying individual, to be gainfully employed and to have earned income
  > of not less than— (A) $250 if subsection (c)(1) applies for the taxable
  > year, or (B) $500 if subsection (c)(2) applies for the taxable year.

So a joint return whose 17-year-old spouse earned little or nothing got a
CDCC on $3,000 or $6,000 of deemed earnings, which TAXSIM does not give.

Ground truth (evidence rule 4): every expected value below is taxsimtest
output, build cd2026081819 (resources/taxsimtest/taxsimtest-osx.exe, sha256
4a17af9c2adbea27b1e6cce240610aede264e008bcdf64b131e0c81220f62b8c), run with
idtl=2 on exactly the PROBES rows. TAXSIM-35 (resources/taxsim35/
taxsim35-osx.exe, cdate-2025Aug23) gives the same v24 on the 2021-2024 rows;
it does not run 2025. Before this change the emulator (policyengine-us
2.58.0) gave v24 of 600, 1,200, 0, 1,200, 600 and 1,500 on rows 1-6.

The records come from Tax-Calculator's PE-TAXSIM validation
(PSLmodels/Tax-Calculator taxcalc/validation/pe_taxsim), where five c-sample
units in 2022-2024 had a 17-year-old spouse and this CDCC difference.
"""

import io
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import policyengine_taxsim.runners.policyengine_runner as runner_module
from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)

TAXSIMTEST_OSX = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "taxsimtest"
    / "taxsimtest-osx.exe"
)

PROBES = (
    "taxsimid,year,state,mstat,page,sage,depx,age1,age2,pwages,swages,"
    "childcare,idtl\n"
    # Spouse 17 with no earnings, one child under 13.
    "1,2024,0,2,40,17,1,3,0,60000,0,3000,2\n"
    # Spouse 17 earning $2,000, two children under 13.
    "2,2024,0,2,40,17,2,3,8,60000,2000,7000,2\n"
    # Control: the same as row 1 with a spouse aged 40.
    "3,2024,0,2,40,40,1,3,0,60000,0,3000,2\n"
    # Both spouses 17 (Tax-Calculator c23 unit 7174 pattern).
    "4,2023,0,2,17,17,2,3,8,93000,0,6000,2\n"
    # Spouse 16 earning $1,000 (2025).
    "5,2025,0,2,40,16,1,3,0,60000,1000,3000,2\n"
    # 2021, when the CDCC was refundable.
    "6,2021,0,2,40,17,1,3,0,60000,0,3000,2\n"
)

# taxsimid -> (v24, fiitax), taxsimtest build cd2026081819.
TAXSIMTEST_EXPECTED = {
    1: (0.0, 1232.00),
    2: (400.0, -1072.98),
    3: (0.0, 1232.00),
    4: (0.0, 3396.00),
    5: (200.0, 663.00),
    6: (0.0, -4010.00),
}


def _records(csv: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(csv))


def _taxsim_input(row: pd.Series) -> dict:
    return {
        key: int(value) if float(value).is_integer() else float(value)
        for key, value in row.items()
    }


@pytest.fixture(scope="module")
def runner_result():
    result = PolicyEngineRunner(_records(PROBES)).run(show_progress=False)
    result["taxsimid"] = result["taxsimid"].astype(int)
    return result.set_index("taxsimid")


@pytest.mark.parametrize("taxsimid", sorted(TAXSIMTEST_EXPECTED))
def test_runner_matches_taxsimtest(runner_result, taxsimid):
    v24, fiitax = TAXSIMTEST_EXPECTED[taxsimid]
    row = runner_result.loc[taxsimid]
    assert row["v24"] == pytest.approx(v24, abs=0.01)
    assert row["fiitax"] == pytest.approx(fiitax, abs=0.01)


@pytest.mark.parametrize("taxsimid", sorted(TAXSIMTEST_EXPECTED))
def test_single_household_path_matches_taxsimtest(taxsimid):
    records = _records(PROBES).set_index("taxsimid", drop=False)
    taxsim_input = _taxsim_input(records.loc[taxsimid])
    situation = generate_household(dict(taxsim_input))
    out = export_household(taxsim_input, situation, False, False)
    v24, fiitax = TAXSIMTEST_EXPECTED[taxsimid]
    assert out["v24"] == pytest.approx(v24, abs=0.01)
    assert out["fiitax"] == pytest.approx(fiitax, abs=0.01)


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Expected values were taken from taxsimtest-osx.exe (cd2026081819).",
)
def test_expectations_match_taxsimtest():
    """The expected constants are the bundled taxsimtest binary's output."""
    try:
        completed = subprocess.run(
            [str(TAXSIMTEST_OSX)],
            input=_records(PROBES).to_csv(index=False),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as error:
        pytest.skip(f"taxsimtest binary cannot run here: {error}")
    assert completed.returncode == 0, completed.stderr
    taxsim = pd.read_csv(io.StringIO(completed.stdout))
    taxsim["taxsimid"] = taxsim["taxsimid"].astype(int)
    taxsim = taxsim.set_index("taxsimid")
    for taxsimid, (v24, fiitax) in TAXSIMTEST_EXPECTED.items():
        assert taxsim.loc[taxsimid, "v24"] == pytest.approx(v24, abs=0.01)
        assert taxsim.loc[taxsimid, "fiitax"] == pytest.approx(fiitax, abs=0.01)


def test_no_person_is_a_student_in_either_path():
    df = _records(PROBES)
    # The runner simulates each year separately (people differ by year).
    for year, year_df in df.groupby("year"):
        year_df = year_df.reset_index(drop=True)
        runner = PolicyEngineRunner(year_df)
        dataset = TaxsimMicrosimDataset(year_df)
        try:
            dataset.generate()
            sim = runner._build_configured_sim(dataset, year_df)
            student = sim.calculate("is_full_time_student", str(int(year)))
            # Every PROBES row is a joint return: two filers plus dependents.
            assert len(student) == 2 * len(year_df) + int(year_df["depx"].sum())
            assert not np.asarray(student).any()
            assert "is_full_time_student" in sim.input_variables
        finally:
            dataset.cleanup()

    for _, row in df.iterrows():
        situation = generate_household(_taxsim_input(row))
        year = str(int(row["year"]))
        for person in situation["people"].values():
            assert person["is_full_time_student"] == {year: False}


# Property tests. Joint returns with wages only and children under 13, so
# each spouse's earned income for IRC 21(d) is their wages. Without deemed
# income the credit is at most the applicable percentage (never above 50%)
# of the lower earner's wages.
_joint_record = st.fixed_dictionaries(
    {
        "year": st.integers(2021, 2025),
        "page": st.integers(25, 64),
        "sage": st.integers(5, 17),
        "depx": st.integers(1, 2),
        "age1": st.integers(1, 12),
        "age2": st.integers(1, 12),
        "pwages": st.integers(0, 40).map(lambda k: 5000 * k),
        "swages": st.integers(0, 8).map(lambda k: 500 * k),
        "childcare": st.integers(0, 20).map(lambda k: 500 * k),
    }
)


def _frame(records):
    rows = []
    for i, rec in enumerate(records, start=1):
        row = dict(rec, taxsimid=i, state=0, mstat=2, idtl=2)
        if row["depx"] < 2:
            row["age2"] = 0
        rows.append(row)
    return pd.DataFrame(rows)


@settings(
    max_examples=6,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(st.lists(_joint_record, min_size=1, max_size=5))
def test_minor_spouse_gets_no_deemed_earnings(records):
    """For a spouse aged 5 to 17: (1) the CDCC is at most half the lower
    earner's wages; (2) the runner and single-household paths agree; (3) the
    CDCC is the same as for an otherwise identical spouse aged 40, since only
    student status could separate them."""
    df = _frame(records)
    adult = df.assign(sage=40)

    def run(frame):
        out = PolicyEngineRunner(frame).run(show_progress=False)
        out["taxsimid"] = out["taxsimid"].astype(int)
        return out.set_index("taxsimid")

    minor_out = run(df)
    adult_out = run(adult)
    for _, rec in df.iterrows():
        taxsimid = int(rec["taxsimid"])
        v24 = float(minor_out.loc[taxsimid, "v24"])
        lower_wages = min(rec["pwages"], rec["swages"])
        assert v24 <= 0.5 * lower_wages + 0.01
        assert v24 == pytest.approx(float(adult_out.loc[taxsimid, "v24"]), abs=0.01)
        taxsim_input = _taxsim_input(rec)
        out = export_household(
            taxsim_input, generate_household(dict(taxsim_input)), False, False
        )
        assert out["v24"] == pytest.approx(v24, abs=0.01)
        assert out["fiitax"] == pytest.approx(
            float(minor_out.loc[taxsimid, "fiitax"]), abs=0.01
        )
