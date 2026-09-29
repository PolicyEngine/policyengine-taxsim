"""statefip (FIPS) input handling, matching TAXSIM-35's check.for rules."""

import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.core.utils import FIPS_TO_SOI_MAP
from policyengine_taxsim.runners.base_runner import BaseTaxRunner
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.runners.stitched_runner import StitchedRunner


class InputRunner(BaseTaxRunner):
    def run(self, show_progress=True):
        return self.input_df


# TAXSIM's ifip2irs table (staten.for), FIPS 0-56; 0 marks codes that are not
# a state or DC.
TAXSIM_IFIP2IRS = [
    0, 1, 2, 0, 3, 4, 5, 0, 6, 7,
    8, 9, 10, 11, 0, 12, 13, 14, 15, 16,
    17, 18, 19, 20, 21, 22, 23, 24, 25, 26,
    27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
    37, 38, 39, 0, 40, 41, 42, 43, 44, 45,
    46, 47, 0, 48, 49, 50, 51,
]  # fmt: skip


def test_fips_map_matches_taxsim():
    expected = {fips: soi for fips, soi in enumerate(TAXSIM_IFIP2IRS) if soi}
    assert FIPS_TO_SOI_MAP == expected


@pytest.mark.parametrize(
    "fips,soi", [(48, 44), (12, 10), (6, 5), (1, 1), (11, 9), (56, 51)]
)
def test_fips_without_state(fips, soi):
    result = InputRunner(pd.DataFrame({"year": [2025], "statefip": [fips]}))
    assert result.input_df.state.tolist() == [soi]


def test_mixed_rows_and_missing_values():
    data = pd.DataFrame(
        {
            "year": [2025] * 4,
            "state": [0, None, 5, 0],
            "statefip": [48, 12, 0, None],
        }
    )
    original = data.copy()
    result = InputRunner(data)
    assert result.input_df.state.tolist() == [44, 10, 5, 0]
    pd.testing.assert_frame_equal(data, original)


@pytest.mark.parametrize("state", [5, -1])
def test_state_and_statefip_both_nonzero_rejected(state):
    # TAXSIM error 21: "State and statefip both nonzero."
    data = pd.DataFrame(
        {
            "taxsimid": [7, 8],
            "year": [2025] * 2,
            "state": [0, state],
            "statefip": [6, 6],
        }
    )
    with pytest.raises(ValueError, match="Record 8: .*both nonzero"):
        InputRunner(data)


@pytest.mark.parametrize("fips", [6.5, -1, 3, 7, 14, 43, 52, 72, 99, float("inf")])
def test_invalid_fips_rejected(fips):
    with pytest.raises(ValueError, match="valid US state FIPS"):
        InputRunner(pd.DataFrame({"year": [2025], "statefip": [fips]}))


def test_converted_input_can_be_validated_again():
    # StitchedRunner, sample() and filter_by_year() build new runners from
    # input_df, so the conversion must not leave state and statefip both set.
    converted = InputRunner(pd.DataFrame({"year": [2025], "statefip": [6]})).input_df
    assert "statefip" not in converted.columns
    assert InputRunner(converted).input_df.state.tolist() == [5]


def test_stitched_runner_passes_soi_state_to_policyengine():
    seen = []

    def fake_run(self, show_progress=True, on_progress=None):
        seen.append(self.input_df.state.tolist())
        return self.input_df[["taxsimid", "year"]].assign(fiitax=0.0, siitax=0.0)

    with patch.object(PolicyEngineRunner, "run", fake_run):
        StitchedRunner(pd.DataFrame({"year": [2024], "statefip": [6]})).run(
            show_progress=False
        )
    assert seen == [[5]]


def test_numeric_strings():
    result = InputRunner(
        pd.DataFrame({"year": [2025], "state": ["0"], "statefip": ["06"]})
    )
    assert result.input_df.state.tolist() == [5]


def test_single_household_path_uses_statefip():
    base = dict(taxsimid=1, year=2024, mstat=1, page=40, pwages=80000, idtl=2)
    by_fips = dict(base, statefip=6)
    by_soi = dict(base, state=5)
    assert generate_household(dict(by_fips)) == generate_household(dict(by_soi))
    # The same record can go through both steps without a state/statefip clash.
    fips_output = export_household(by_fips, generate_household(by_fips), False, False)
    soi_output = export_household(by_soi, generate_household(by_soi), False, False)
    assert by_fips == dict(base, statefip=6)
    assert fips_output["state"] == 5
    assert fips_output["siitax"] == soi_output["siitax"]


@pytest.fixture
def api():
    with patch.dict(sys.modules, {"modal": MagicMock()}):
        sys.modules.pop("policyengine_taxsim.api", None)
        import policyengine_taxsim.api as module

        yield module
    sys.modules.pop("policyengine_taxsim.api", None)


def test_api_accepts_statefip(api):
    df, warnings = api._validate_csv("year,statefip\n2024,6\n2024,0\n")
    assert len(df) == 2
    assert not any("statefip" in warning for warning in warnings)


def test_api_rejects_state_and_statefip(api):
    with pytest.raises(ValueError, match="Row 2: .*both nonzero"):
        api._validate_csv("year,state,statefip\n2024,5,0\n2024,5,6\n")
