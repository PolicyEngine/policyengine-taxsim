"""
Marginal rates must be computed under the same emulator overrides as the
base simulation.

``PolicyEngineRunner._compute_marginal_rates`` perturbs wages in a branch of
the configured Microsimulation and deletes every cached array that is not in
``sim.input_variables``, so the branch recomputes taxes. policyengine-core
builds ``input_variables`` once, in ``Simulation.__init__``, from the
dataset's known periods. The overrides ``_build_configured_sim`` applies
afterwards (SALT for --disable-salt, QBID W-2 wages, the rental QBID gate,
the MN CRP flag, the state SSI-supplement zeroing, MD local-tax zeroing, the
ME rent utilities flag, NY separate-payment zeroing) were missing from that
list. SSI, SNAP, TANF and WIC were not: the dataset already supplies them.
The branch deleted each missing override, so it reverted to what PE-US
computes without it: its formula, or its default for a pure input (the
rental QBID gate back to True). On PE-US 2.11.2 / policyengine-core 3.32.6:

* MD single $80k (2024) reported srate 2253.01 and MFJ $100k 2678.73: the
  county tax the base sim zeroed reappeared in the branch, divided by the
  $100 delta. srate is a percentage. (The first report, MD single $100k at
  2983.49, also sits on MD's $100k exemption step; after the fix it reports
  that step, 80.75, which TAXSIM smooths to 5.05. That is a separate issue.)
* CA single $60k wages + $20k ``otherprop`` reported frate -858: the branch
  turned the rental QBID gate back on and took a 20% QBID.
* --disable-salt itemizers reported large negative frates: the branch
  deducted state income tax that the base sim excluded.

The runner now pins each override with ``_pin_input``, which also registers
it in ``sim.input_variables``.

Ground truth for the expected rates (evidence rule 4: external, not derived
from the fix):

* NBER TAXSIM-35, the bundled ``resources/taxsim35/taxsim35-osx.exe``
  (cdate-2025Aug23), on the records below. ``test_expectations_match_taxsim35``
  re-runs it on macOS so the constants cannot drift from the binary.
* Maryland 2024 Resident Tax Booklet, p. 14 (PDF p. 22), "MARYLAND TAX
  COMPUTATION WORKSHEET SCHEDULES" (pdftotext -layout):

  > Tax Rate Schedule I
  > For taxpayers filing as Single, Married Filing Separately, or
  > as Dependent Taxpayers. [...]
  > $3,000 $100,000 $90.00 plus 4.75% of excess over $3,000
  >
  > Tax Rate Schedule II
  > For taxpayers Married Filing Jointly, Head of Household,
  > or for Qualifying Surviving Spouse. [...]
  > $3,000 $150,000 $90.00 plus 4.75% of excess over $3,000

  https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/instructions/2024/Resident-Booklet.pdf#page=22
  TAXSIM (``taxsimtest``, v36) puts these records' MD taxable income at
  $74,100 (single $80k), $88,150 (MFJ $100k) and $52,800 (itemizer), all
  inside the 4.75% rows. The records avoid MD's personal-exemption steps,
  which start above $100k FAGI for single filers ($125k, $150k) and $150k
  for joint filers ($175k, $200k). TAXSIM smooths each step and PE's $100
  difference does not.
* IRS Rev. Proc. 2023-34, sec. 3.01 ("taxable years beginning in 2024").
  Table 1 (married individuals filing joint returns), PDF p. 5:

  > Over $23,200 but not over $94,300   $2,320 plus 12% of the excess
  > over $23,200

  Table 3 (unmarried individuals), PDF p. 6:

  > Over $11,600 but not over $47,150   $1,160 plus 12% of the excess
  > over $11,600
  > Over $47,150 but not over $100,525   $5,426 plus 22% of the excess
  > over $47,150

  https://www.irs.gov/pub/irs-drop/rp-23-34.pdf#page=6
"""

import io
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

import policyengine_taxsim.runners.policyengine_runner as runner_module
from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)

YEAR = 2024
TAXSIM35_OSX = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "taxsim35"
    / "taxsim35-osx.exe"
)

_COLUMNS = (
    "taxsimid,year,state,mstat,page,sage,depx,pwages,mortgage,proptax,otherprop,idtl\n"
)

# Default mode (no --disable-salt). Expected rates from taxsim35-osx.exe.
DEFAULT_RECORDS = _COLUMNS + (
    # MD single $80k: MD Schedule I 4.75% row; federal 22%.
    "1,2024,21,1,40,0,0,80000,0,0,0,2\n"
    # MD MFJ $100k: MD Schedule II 4.75% row; federal taxable $70,800
    # (taxsimtest v18), Table 1 12% row.
    "2,2024,21,2,40,40,0,100000,0,0,0,2\n"
    # CA single $60k wages + $20k otherprop: federal taxable $65,400
    # (taxsimtest v18), Table 3 22% row. Exercises the rental QBID gate.
    "3,2024,5,1,40,0,0,60000,0,0,20000,2\n"
)
DEFAULT_EXPECTED = {
    # taxsimid: (frate, srate or None when srate is not asserted)
    1: (22.0, 4.75),
    2: (12.0, 4.75),
    3: (22.0, None),
}

# --disable-salt: MD single $80k itemizer ($20k mortgage, $4k property tax).
# Federal itemized is $24,000 with no state income tax, so federal taxable
# income is $56,000 in the Table 3 22% row, and MD taxable income is
# $52,800 in the Schedule I 4.75% row. taxsim35 reports srate 4.75 for this
# record; its frate (20.95) deducts state tax at the margin, which
# --disable-salt excludes, so the federal expectation is the Table 3 rate.
DISABLE_SALT_RECORD = _COLUMNS + "4,2024,21,1,40,0,0,80000,20000,4000,0,2\n"
DISABLE_SALT_EXPECTED = {4: (22.0, 4.75)}

# Zero-wage filers with no spouse get the whole $100 wage perturbation.
# Expected rates from taxsim35-osx.exe.
ZERO_WAGE_RECORDS = (
    "taxsimid,year,state,mstat,page,sage,depx,pwages,intrec,rentpaid,idtl\n"
    # OH single, $50k interest: federal taxable $35,400, Table 3 12% row.
    "5,2024,36,1,40,0,0,0,50000,0,2\n"
    # MA low-income elderly renter (#1031).
    "6,2024,22,1,69,0,0,0,4306.37,4284.81,2\n"
)
ZERO_WAGE_EXPECTED = {5: (12.0, 2.75), 6: (0.0, 10.0)}

# One chunk that triggers every override in _build_configured_sim.
OVERRIDE_RECORDS = (
    "taxsimid,year,state,mstat,page,sage,depx,pwages,mortgage,proptax,"
    "otherprop,rentpaid,pbusinc,intrec,idtl\n"
    # MD itemizer: SALT (disable_salt) and MD local-tax zeroing.
    "1,2024,21,1,40,0,0,80000,20000,4000,0,0,0,0,2\n"
    # MN renter: mn_renters_credit_qualifying_crp.
    "2,2024,24,1,40,0,0,30000,0,0,0,12000,0,0,2\n"
    # ME elderly renter: utilities_included_in_rent.
    "3,2024,20,1,70,0,0,20000,0,0,0,12000,0,0,2\n"
    # CA otherprop: rental_income_would_be_qualified.
    "4,2024,5,1,40,0,0,60000,0,0,20000,0,0,0,2\n"
    # TX pass-through income above the QBID threshold: W-2 wages matter.
    "5,2024,44,1,40,0,0,0,0,0,0,0,300000,0,2\n"
    # MA low-income elderly renter (#1031): imputed-transfer zeroing.
    "6,2024,22,1,69,0,0,0,0,0,0,4284.81,0,4306.37,2\n"
    # NY single parent: NY separate-payment zeroing (#1158).
    "7,2024,33,1,35,0,1,25000,0,0,0,0,0,0,2\n"
)
EXPECTED_OVERRIDES = {
    "state_and_local_sales_or_income_tax",
    "w2_wages_from_qualified_business",
    "rental_income_would_be_qualified",
    "mn_renters_credit_qualifying_crp",
    "md_local_income_tax_before_refundable_credits",
    "utilities_included_in_rent",
    "ny_additional_ctc",
    "ny_inflation_refund_credit",
    "ny_supplemental_eitc",
    "ssi",
    "snap",
    "tanf",
    "wic",
}


def _records(csv: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(csv))


def _rates(csv: str, **runner_kwargs) -> pd.DataFrame:
    result = PolicyEngineRunner(_records(csv), **runner_kwargs).run(show_progress=False)
    result["taxsimid"] = result["taxsimid"].astype(int)
    return result.set_index("taxsimid")[["frate", "srate"]]


def _assert_rates(result, expected, context):
    for taxsimid, (frate, srate) in expected.items():
        got = result.loc[taxsimid]
        assert got["frate"] == pytest.approx(frate, abs=0.01), (
            f"{context} record {taxsimid}: frate {got['frate']} != {frate}"
        )
        if srate is not None:
            assert got["srate"] == pytest.approx(srate, abs=0.01), (
                f"{context} record {taxsimid}: srate {got['srate']} != {srate}"
            )


@pytest.fixture(scope="module")
def default_rates():
    return _rates(DEFAULT_RECORDS)


def test_md_srate_is_state_only_bracket_rate(default_rates):
    """MD srate is the 4.75% state bracket rate, not the county tax the base
    sim zeroed divided by the $100 delta (previously 2253.01 and 2678.73)."""
    for taxsimid in (1, 2):
        srate = default_rates.loc[taxsimid, "srate"]
        assert 0 < srate < 10, f"MD record {taxsimid}: srate {srate} is not sane"
    _assert_rates(default_rates, DEFAULT_EXPECTED, "default")


def test_rental_qbid_gate_holds_in_mtr_branch(default_rates):
    """CA otherprop frate stays at the 22% bracket rate; the branch must not
    re-enable QBID on rental income (previously -858)."""
    _assert_rates(default_rates, {3: DEFAULT_EXPECTED[3]}, "default")


def test_disable_salt_itemizer_rates():
    """Under --disable-salt the branch keeps state income tax out of federal
    Schedule A, so frate is the 22% bracket rate (previously -1291.23)."""
    result = _rates(DISABLE_SALT_RECORD, disable_salt=True)
    _assert_rates(result, DISABLE_SALT_EXPECTED, "disable_salt")


def _taxsim35(csv):
    try:
        completed = subprocess.run(
            [str(TAXSIM35_OSX)],
            input=_records(csv).to_csv(index=False),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as error:
        pytest.skip(f"taxsim35 binary cannot run here: {error}")
    assert completed.returncode == 0, completed.stderr
    taxsim = pd.read_csv(io.StringIO(completed.stdout))
    taxsim["taxsimid"] = taxsim["taxsimid"].astype(int)
    return taxsim.set_index("taxsimid")


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Expected rates were taken from taxsim35-osx.exe (cdate-2025Aug23); "
    "the unix/windows taxsim35 builds are not confirmed to be the same build.",
)
def test_expectations_match_taxsim35():
    """The expected constants are the bundled TAXSIM-35 binary's output."""
    for csv, expected in (
        (DEFAULT_RECORDS, DEFAULT_EXPECTED),
        (ZERO_WAGE_RECORDS, ZERO_WAGE_EXPECTED),
    ):
        taxsim = _taxsim35(csv)
        for taxsimid, (frate, srate) in expected.items():
            assert taxsim.loc[taxsimid, "frate"] == pytest.approx(frate, abs=0.01)
            if srate is not None:
                assert taxsim.loc[taxsimid, "srate"] == pytest.approx(srate, abs=0.01)
    # The --disable-salt record: TAXSIM's srate is the expectation; its frate
    # includes the state-tax deduction --disable-salt excludes (see above).
    taxsim = _taxsim35(DISABLE_SALT_RECORD)
    assert taxsim.loc[4, "srate"] == pytest.approx(
        DISABLE_SALT_EXPECTED[4][1], abs=0.01
    )


def test_zero_wage_single_gets_full_delta():
    """A zero-wage filer with no spouse used to get half the $100
    perturbation while the rate divided by the full $100, halving frate and
    srate (OH: 6.0 / 1.375; MA: srate 5.0)."""
    _assert_rates(_rates(ZERO_WAGE_RECORDS), ZERO_WAGE_EXPECTED, "zero-wage")


def test_single_household_path_zero_wage_single():
    """The single-household path (export_household) splits the same way."""
    row = _records(ZERO_WAGE_RECORDS).iloc[0]
    taxsim_input = {
        key: int(value) if float(value).is_integer() else float(value)
        for key, value in row.items()
    }
    situation = generate_household(dict(taxsim_input))
    out = export_household(taxsim_input, situation, False, False)
    frate, srate = ZERO_WAGE_EXPECTED[5]
    assert out["frate"] == pytest.approx(frate, abs=0.05)
    assert out["srate"] == pytest.approx(srate, abs=0.05)


class _RecordingMicrosimulation(runner_module.Microsimulation):
    """Records every variable set_input'd after construction, i.e. each
    override _build_configured_sim applies through sim.set_input (directly
    or via _pin_input)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_after_init = set()

    def set_input(self, variable_name, period, value):
        recorded = getattr(self, "set_after_init", None)
        if recorded is not None:
            recorded.add(variable_name)
        return super().set_input(variable_name, period, value)


def test_every_override_survives_mtr_branch(monkeypatch):
    """Every variable _build_configured_sim sets after construction is a
    registered input and keeps its value in the MTR branch; in particular
    --disable-salt's zero SALT."""
    df = _records(OVERRIDE_RECORDS)
    runner = PolicyEngineRunner(df, disable_salt=True, assume_w2_wages=True)
    monkeypatch.setattr(runner_module, "Microsimulation", _RecordingMicrosimulation)

    dataset = TaxsimMicrosimDataset(df)
    try:
        dataset.generate()
        # _simulate passes zero_salt=True for --disable-salt (and state-0) runs.
        sim = runner._build_configured_sim(dataset, df, zero_salt=True)
        overrides = set(sim.set_after_init)

        present = {
            name
            for name in EXPECTED_OVERRIDES
            if name in sim.tax_benefit_system.variables
        }
        assert present <= overrides, (
            f"chunk did not trigger overrides {sorted(present - overrides)}"
        )
        missing = overrides - set(sim.input_variables)
        assert not missing, (
            f"overrides not registered in sim.input_variables: {sorted(missing)}"
        )

        branches = []
        get_branch = type(sim).get_branch

        def capture_branch(self, name="branch", clone_system=False):
            branch = get_branch(self, name, clone_system)
            if name == "mtr_wage_perturbation":
                branches.append(branch)
            return branch

        monkeypatch.setattr(type(sim), "get_branch", capture_branch)
        year = str(YEAR)
        rates = runner._compute_marginal_rates(sim, year, df)
        assert len(branches) == 1

        branch = branches[0]
        for name in sorted(overrides):
            np.testing.assert_array_equal(
                np.asarray(branch.calculate(name, year)),
                np.asarray(sim.calculate(name, year)),
                err_msg=f"{name} changed in the MTR branch",
            )
        np.testing.assert_array_equal(
            np.asarray(branch.calculate("state_and_local_sales_or_income_tax", year)),
            0,
            err_msg="--disable-salt SALT override lost in the MTR branch",
        )
        # Each tax unit's wage perturbation adds up to the full $100 delta,
        # including zero-wage filers with no spouse (TX, MA records).
        added = np.asarray(branch.calculate("employment_income", year)) - np.asarray(
            sim.calculate("employment_income", year)
        )
        per_unit = np.asarray(sim.map_result(added, "person", "tax_unit", how="sum"))
        np.testing.assert_allclose(per_unit, 100.0, atol=0.02)
        # MD itemizer (first tax unit) under the fix: the same rates as the
        # standalone --disable-salt record above.
        assert rates["frate"][0] == pytest.approx(DISABLE_SALT_EXPECTED[4][0], abs=0.01)
        assert rates["srate"][0] == pytest.approx(DISABLE_SALT_EXPECTED[4][1], abs=0.01)
    finally:
        dataset.cleanup()


# ---------------------------------------------------------------------------
# Invariant: the branch computes what a full rebuild computes.
#
# For every tax unit, frate and srate must equal the finite difference
# 100 * (tax(w + share * $100) - tax(w)) / $100 between the configured sim and
# a second sim that _build_configured_sim builds independently from inputs
# with the perturbed wages. The rebuild re-applies every override, so any
# override the branch drops, and any perturbation that does not add up to the
# full $100, breaks the equality. Notches do not: both sims cross them alike.
# The shares follow TAXSIM's weighted-average earnings rule, written out
# independently of the runner: proportional to wages, else 50/50 for a
# couple, else all to the head.
# ---------------------------------------------------------------------------

DELTA = 100.0
_RECORD_FIELDS = (
    "state,mstat,page,sage,depx,pwages,swages,mortgage,proptax,otherprop,"
    "rentpaid,pbusinc,intrec"
).split(",")
# Every override path plus zero-wage singles and couples, the MD exemption
# step, and a NY single parent (separate payments).
FIXED_CHUNK = [
    dict(zip(_RECORD_FIELDS, values))
    for values in (
        (21, 1, 40, 0, 0, 80000, 0, 20000, 4000, 0, 0, 0, 0),
        (24, 1, 40, 0, 0, 30000, 0, 0, 0, 0, 12000, 0, 0),
        (20, 1, 70, 0, 0, 20000, 0, 0, 0, 0, 12000, 0, 0),
        (5, 1, 40, 0, 0, 60000, 0, 0, 0, 20000, 0, 0, 0),
        (44, 1, 40, 0, 0, 0, 0, 0, 0, 0, 0, 300000, 0),
        (22, 1, 69, 0, 0, 0, 0, 0, 0, 0, 4284.81, 0, 4306.37),
        (33, 1, 35, 0, 1, 25000, 0, 0, 0, 0, 0, 0, 0),
        (21, 2, 45, 43, 2, 60000, 40000, 15000, 5000, 0, 0, 0, 0),
        (36, 1, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 50000),
        (36, 2, 66, 64, 0, 0, 0, 0, 0, 0, 0, 0, 50000),
        (21, 1, 40, 0, 0, 100000, 0, 0, 0, 0, 0, 0, 0),
    )
]


def _money(high):
    return st.one_of(st.just(0), st.integers(1_000, high))


@st.composite
def _taxsim_record(draw):
    married = draw(st.booleans())
    return {
        # AR, CA, ME, MD, MA, MN, NY, OH, TX: every state-scoped override.
        "state": draw(st.sampled_from([4, 5, 20, 21, 22, 24, 33, 36, 44])),
        "mstat": 2 if married else 1,
        "page": draw(st.integers(25, 75)),
        "sage": draw(st.integers(25, 75)) if married else 0,
        "depx": draw(st.integers(0, 2)),
        "pwages": draw(_money(250_000)),
        "swages": draw(_money(150_000)) if married else 0,
        "mortgage": draw(_money(30_000)),
        "proptax": draw(_money(10_000)),
        "otherprop": draw(_money(30_000)),
        "rentpaid": draw(_money(20_000)),
        "pbusinc": draw(_money(400_000)),
        "intrec": draw(_money(60_000)),
    }


def _chunk(records, year):
    df = pd.DataFrame(records, columns=_RECORD_FIELDS)
    df.insert(0, "taxsimid", range(1, len(df) + 1))
    df.insert(1, "year", year)
    df["idtl"] = 2
    return df


def _with_perturbed_wages(df):
    total = df["pwages"] + df["swages"]
    married = df["mstat"] == 2
    safe_total = total.where(total > 0, 1)
    p_share = np.where(total > 0, df["pwages"] / safe_total, np.where(married, 0.5, 1))
    s_share = np.where(total > 0, df["swages"] / safe_total, np.where(married, 0.5, 0))
    out = df.copy()
    out["pwages"] = df["pwages"] + DELTA * p_share
    out["swages"] = df["swages"] + DELTA * s_share
    return out


def _configured_sim(runner, df):
    dataset = TaxsimMicrosimDataset(df)
    dataset.generate()
    sim = runner._build_configured_sim(dataset, df)
    return sim, dataset


@settings(
    max_examples=3,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(
    records=st.lists(_taxsim_record(), min_size=3, max_size=8),
    year=st.sampled_from([2022, 2023, 2024]),
    disable_salt=st.booleans(),
    assume_w2_wages=st.booleans(),
)
@example(records=FIXED_CHUNK, year=2024, disable_salt=True, assume_w2_wages=True)
@example(records=FIXED_CHUNK, year=2024, disable_salt=False, assume_w2_wages=False)
def test_mtr_equals_finite_difference_of_rebuilt_sim(
    records, year, disable_salt, assume_w2_wages
):
    period = str(year)
    flags = dict(disable_salt=disable_salt, assume_w2_wages=assume_w2_wages)
    df = _chunk(records, year)
    perturbed = _with_perturbed_wages(df)
    runner = PolicyEngineRunner(df, **flags)
    sim, dataset = _configured_sim(runner, df)
    sim_up, dataset_up = _configured_sim(
        PolicyEngineRunner(perturbed, **flags), perturbed
    )
    try:
        rates = runner._compute_marginal_rates(sim, period, df)
        for rate, tax in (("frate", "income_tax"), ("srate", "state_income_tax")):
            base = runner._calc_tax_unit(sim, tax, period)
            up = runner._calc_tax_unit(sim_up, tax, period)
            np.testing.assert_allclose(
                rates[rate],
                100.0 * (up - base) / DELTA,
                atol=0.05,
                err_msg=f"{rate} != finite difference of {tax} ({flags}, {year})",
            )
    finally:
        dataset.cleanup()
        dataset_up.cleanup()
