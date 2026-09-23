"""TAXSIM `mstat` 8: dependent taxpayer ("Typically a child with income").

The emulator used to treat mstat 8 as single, so a dependent filer got the
full standard deduction, the EITC and the 2021 recovery rebate. It now flags
the filer with PolicyEngine's `claimed_as_dependent_on_another_return`, which
limits the standard deduction to the dependent amount (IRC § 63(c)(5)), and
denies the two credits whose PolicyEngine formulas do not check it:

- EITC: IRC § 32(c)(1)(A)(ii)(III), a filer without a qualifying child must
  not be "a dependent for whom a deduction is allowable under section 151 to
  another taxpayer".
- 2021 recovery rebate: IRC § 6428B(c)(2) excludes "any individual who is a
  dependent of another taxpayer".

BLS's CE NTAXI files still code about 4.6% of 2021-2023 tax units as
FILESTAT 8.

Ground truth is the bundled taxsimtest binary. Records use wages or interest
in years where taxsimtest's dependent standard deduction matches the IRS
amounts; see `test_dependent_standard_deduction_follows_irs_amounts` for the
years where it does not.

Only federal outputs are compared. State treatment of dependent filers is
left to PolicyEngine's state models and can differ from taxsimtest: e.g.
Pennsylvania, where taxsimtest charges record 1 $92.10 (3.07% of $3,000, no
Tax Forgiveness) and PolicyEngine grants full forgiveness.
"""

import pandas as pd
import pytest

from policyengine_taxsim.core.input_mapper import generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

PA, TX = 39, 44

_COLUMNS = ["taxsimid", "year", "state", "mstat", "page", "pwages", "intrec"]
_RECORDS = [
    # 2021 dependents: no recovery rebate, no childless EITC.
    (1, 2021, PA, 8, 17, 3_000, 0),
    (2, 2021, PA, 8, 19, 15_000, 0),
    (3, 2021, PA, 8, 20, 30_000, 0),
    (4, 2021, TX, 8, 45, 60_000, 0),
    (5, 2021, TX, 8, 16, 0, 5_000),
    # Later years: earned-income-limited standard deduction.
    (6, 2023, PA, 8, 17, 8_000, 0),
    (7, 2025, TX, 8, 16, 0, 5_000),
    (8, 2025, TX, 8, 19, 15_000, 0),
    # Controls: the same 2021 filers as mstat 1.
    (9, 2021, PA, 1, 19, 15_000, 0),
    (10, 2021, TX, 1, 16, 0, 5_000),
]
_IDS = [r[0] for r in _RECORDS]


def _frame(records=_RECORDS):
    df = pd.DataFrame(records, columns=_COLUMNS)
    df["sage"] = 0
    df["depx"] = 0
    df["idtl"] = 2
    return df


def _by_id(result):
    result = result.copy()
    result["taxsimid"] = result["taxsimid"].astype(float).astype(int)
    return result.set_index("taxsimid")


@pytest.fixture(scope="module")
def taxsim():
    return _by_id(TaxsimRunner(_frame()).run(show_progress=False))


@pytest.fixture(scope="module")
def emulator():
    return _by_id(PolicyEngineRunner(_frame(), logs=False).run(show_progress=False))


@pytest.mark.parametrize("taxsimid", _IDS)
def test_emulator_matches_binary(taxsim, emulator, taxsimid):
    for col in ["fiitax", "v13", "v18", "v25"]:
        assert emulator.loc[taxsimid, col] == pytest.approx(
            taxsim.loc[taxsimid, col], abs=1.0
        ), (
            f"record {taxsimid} {col}: emulator {emulator.loc[taxsimid, col]:.2f} "
            f"vs taxsimtest {taxsim.loc[taxsimid, col]:.2f}"
        )


def test_dependent_filer_loses_rebate_and_eitc(taxsim, emulator):
    # Same 19-year-old with $15K of wages in 2021: as a dependent (record 2)
    # no $1,400 rebate and no $983.33 childless EITC; as single (record 9)
    # both.
    for frame in (taxsim, emulator):
        assert frame.loc[2, "v25"] == pytest.approx(0, abs=0.01)
        assert frame.loc[9, "v25"] == pytest.approx(983.33, abs=0.01)
        assert frame.loc[2, "fiitax"] - frame.loc[9, "fiitax"] == pytest.approx(
            1_400 + 983.33, abs=1.0
        )


def test_dependent_standard_deduction_is_limited(taxsim, emulator):
    # 2021: greater of $1,100 or earned income + $350, capped at $12,550.
    for frame in (taxsim, emulator):
        assert frame.loc[1, "v13"] == pytest.approx(3_350, abs=0.01)
        assert frame.loc[5, "v13"] == pytest.approx(1_100, abs=0.01)
        assert frame.loc[3, "v13"] == pytest.approx(12_550, abs=0.01)


def test_dependent_standard_deduction_follows_irs_amounts():
    """Known divergence: taxsimtest's dependent minimum lags the IRS amount
    by a year in 2022-2024 ($1,100 in 2022 and 2023, $1,350 in 2024). The
    IRS minimums are $1,150 (Rev. Proc. 2021-45), $1,250 (Rev. Proc.
    2022-38) and $1,300 (Rev. Proc. 2023-34); PolicyEngine follows them."""
    records = [
        (1, 2022, TX, 8, 16, 0, 5_000),
        (2, 2023, TX, 8, 16, 0, 5_000),
        (3, 2024, TX, 8, 16, 0, 5_000),
    ]
    out = _by_id(
        PolicyEngineRunner(_frame(records), logs=False).run(show_progress=False)
    )
    assert list(out["v13"]) == pytest.approx([1_150, 1_250, 1_300], abs=0.01)


def test_single_household_path_flags_dependent_filer():
    situation = generate_household(
        {
            "taxsimid": 1,
            "year": 2021,
            "state": PA,
            "mstat": 8,
            "page": 19,
            "depx": 0,
            "pwages": 15_000,
            "idtl": 0,
        }
    )
    you = situation["people"]["you"]
    unit = situation["tax_units"]["your tax unit"]
    assert you["claimed_as_dependent_on_another_return"] == {"2021": True}
    assert unit["eitc_eligible"] == {"2021": False}
    assert unit["rrc_arpa"] == {"2021": 0}
