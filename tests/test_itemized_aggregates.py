"""TAXSIM `otheritem` and `mortgage` itemized-deduction aggregates.

TAXSIM-35 takes two lump-sum itemized-deduction inputs besides `proptax`:

- `otheritem` (#22): documented as "Other Itemized deductions that are a
  preference for the Alternative Minimum Tax" (other state and local taxes,
  the preference share of medical expenses, interest other than on the own
  residence, miscellaneous deductions).
- `mortgage` (#24): documented as "Deductions not included above and not a
  preference for the AMT" (home mortgage interest, deductible medical
  expenses, motor vehicle taxes, charitable contributions, casualty losses).

Ground truth is the bundled `taxsimtest` binary, not the documentation. On
the federal return the binary treats the two columns identically: each is
deducted in full on Schedule A (no AGI floor, outside the SALT cap), and
neither is added back to AMT income (v26), in every tax year the emulator
covers. The emulator therefore sums both into PolicyEngine's
`deductible_mortgage_interest`, which flows through `interest_deduction` with
no floor or cap and is not an AMT add-back.

Before this change the emulator ignored `otheritem` entirely (taxsim #484).
BLS's Consumer Expenditure Survey fills `otheritem` for roughly half of its
tax units (Curtin 2017, "Calculating Inputs for the NBER TAXSIM model, using
the CE PUMD"), so dropping it overstated federal and state tax for
itemizers.

Most records use Pennsylvania (SOI 39): PA has no state itemized deductions
and a flat rate, so the federal comparison is not confounded by state
itemized-deduction or sales-tax differences, and the emulator reproduces the
binary to the cent there.
"""

import pandas as pd
import pytest

from policyengine_taxsim.core.input_mapper import generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

PA = 39
CA = 5

# (taxsimid, year, state, mstat, page, sage, pwages, proptax, mortgage,
#  otheritem). Records come in pairs that move the same dollars between
# `mortgage` and `otheritem`.
_RECORDS = [
    # Single, $200K wages, $100K deduction: large enough that an AMT add-back
    # of `otheritem` would trigger AMT (AMTI $200K vs regular taxable $94K).
    (1, 2023, PA, 1, 45, 0, 200_000, 0, 100_000, 0),
    (2, 2023, PA, 1, 45, 0, 200_000, 0, 0, 100_000),
    # Single, $500K wages, $200K deduction.
    (3, 2024, PA, 1, 50, 0, 500_000, 0, 200_000, 0),
    (4, 2024, PA, 1, 50, 0, 500_000, 0, 0, 200_000),
    # Joint, property tax above the $10K SALT cap, so any SALT treatment of
    # `otheritem` would be capped away. Record 5 is the no-deduction baseline.
    (5, 2022, PA, 2, 40, 38, 120_000, 15_000, 0, 0),
    (6, 2022, PA, 2, 40, 38, 120_000, 15_000, 0, 30_000),
    (7, 2022, PA, 2, 40, 38, 120_000, 15_000, 30_000, 0),
    # Low income: $3K stays below the standard deduction; $20K itemizes.
    (8, 2021, PA, 1, 30, 0, 40_000, 0, 0, 3_000),
    (9, 2021, PA, 1, 30, 0, 40_000, 0, 0, 20_000),
    # 2025 ($40K OBBBA SALT cap) and 2026, mixing both inputs.
    (10, 2025, PA, 2, 66, 64, 300_000, 30_000, 20_000, 25_000),
    (11, 2025, PA, 2, 66, 64, 300_000, 30_000, 45_000, 0),
    (12, 2026, PA, 2, 50, 50, 400_000, 20_000, 10_000, 30_000),
    (13, 2026, PA, 2, 50, 50, 400_000, 20_000, 40_000, 0),
    # California married itemizer: $150K wages, $6K property tax, $18K
    # mortgage, then $6K `otheritem` (record 15) or the same $6K moved into
    # `mortgage` (record 16).
    (14, 2023, CA, 2, 45, 45, 150_000, 6_000, 18_000, 0),
    (15, 2023, CA, 2, 45, 45, 150_000, 6_000, 18_000, 6_000),
    (16, 2023, CA, 2, 45, 45, 150_000, 6_000, 24_000, 0),
]

_PAIRS = [(1, 2), (3, 4), (6, 7), (10, 11), (12, 13), (15, 16)]
_PA_IDS = [r[0] for r in _RECORDS if r[2] == PA]

_FEDERAL = ["fiitax", "v18", "v19", "v26", "v27", "v28"]


def _input_frame():
    columns = [
        "taxsimid",
        "year",
        "state",
        "mstat",
        "page",
        "sage",
        "pwages",
        "proptax",
        "mortgage",
        "otheritem",
    ]
    df = pd.DataFrame(_RECORDS, columns=columns)
    df["depx"] = 0
    df["idtl"] = 2
    return df


def _by_id(result):
    result = result.copy()
    result["taxsimid"] = result["taxsimid"].astype(float).astype(int)
    return result.set_index("taxsimid")


@pytest.fixture(scope="module")
def taxsim():
    """Bundled taxsimtest binary output for the records (ground truth)."""
    return _by_id(TaxsimRunner(_input_frame()).run(show_progress=False))


@pytest.fixture(scope="module")
def emulator():
    return _by_id(
        PolicyEngineRunner(_input_frame(), logs=False).run(show_progress=False)
    )


class TestBinaryPremise:
    """Pin the taxsimtest behavior the mapping relies on, so a future binary
    that starts treating `otheritem` differently (e.g. as the AMT preference
    its documentation describes) fails loudly here."""

    @pytest.mark.parametrize("pair", _PAIRS)
    def test_otheritem_and_mortgage_are_interchangeable(self, taxsim, pair):
        a, b = pair
        for col in _FEDERAL + ["v17", "siitax"]:
            assert taxsim.loc[a, col] == pytest.approx(taxsim.loc[b, col], abs=0.01), (
                f"taxsimtest {col} differs for records {a} vs {b}"
            )

    def test_otheritem_is_not_an_amt_add_back(self, taxsim):
        # $200K AGI less $100K `otheritem`: AMTI stays $100K and no AMT.
        assert taxsim.loc[2, "v26"] == pytest.approx(100_000, abs=0.01)
        assert taxsim.loc[2, "v27"] == pytest.approx(0, abs=0.01)

    def test_otheritem_is_outside_the_salt_cap(self, taxsim):
        # $15K property tax caps SALT at $10K; the $30K of `otheritem`
        # is deducted on top of it.
        assert taxsim.loc[6, "v17"] == pytest.approx(40_000, abs=0.01)


class TestEmulatorMatchesBinary:
    @pytest.mark.parametrize("taxsimid", _PA_IDS)
    def test_federal_and_state_tax_match(self, taxsim, emulator, taxsimid):
        for col in _FEDERAL + ["siitax"]:
            assert emulator.loc[taxsimid, col] == pytest.approx(
                taxsim.loc[taxsimid, col], abs=1.0
            ), (
                f"record {taxsimid} {col}: emulator "
                f"{emulator.loc[taxsimid, col]:.2f} vs taxsimtest "
                f"{taxsim.loc[taxsimid, col]:.2f}"
            )

    @pytest.mark.parametrize("pair", _PAIRS)
    def test_otheritem_and_mortgage_are_interchangeable(self, emulator, pair):
        a, b = pair
        for col in _FEDERAL + ["v17", "siitax", "v35"]:
            assert emulator.loc[a, col] == pytest.approx(
                emulator.loc[b, col], abs=0.01
            ), f"emulator {col} differs for records {a} vs {b}"

    def test_otheritem_reduces_federal_tax_like_taxsim(self, taxsim, emulator):
        """The California example: $6K of `otheritem` cuts federal tax from
        $17,455 to $16,135 in taxsimtest. Before this change the emulator
        left it at $17,455."""
        for taxsimid in (14, 15):
            assert emulator.loc[taxsimid, "fiitax"] == pytest.approx(
                taxsim.loc[taxsimid, "fiitax"], abs=1.0
            )
        assert emulator.loc[15, "fiitax"] < emulator.loc[14, "fiitax"] - 1_000

    def test_otheritem_reduces_california_tax(self, taxsim, emulator):
        # taxsimtest lets `otheritem` reduce CA tax (as it does `mortgage`);
        # so must the emulator.
        assert taxsim.loc[15, "siitax"] < taxsim.loc[14, "siitax"]
        assert emulator.loc[15, "siitax"] < emulator.loc[14, "siitax"]


class TestSingleHouseholdPath:
    def test_both_aggregates_go_to_the_head(self):
        situation = generate_household(
            {
                "taxsimid": 1,
                "year": 2023,
                "state": CA,
                "mstat": 2,
                "page": 45,
                "sage": 45,
                "depx": 0,
                "pwages": 150_000,
                "mortgage": 18_000,
                "otheritem": 6_000,
                "idtl": 2,
            }
        )
        people = situation["people"]
        assert people["you"]["deductible_mortgage_interest"] == {"2023": 24_000}
        assert "deductible_mortgage_interest" not in people["your partner"]
