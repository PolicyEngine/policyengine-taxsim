"""FIPS normalization runs before either tax calculation backend."""

import pandas as pd
import pytest

from policyengine_taxsim.runners.base_runner import BaseTaxRunner


class InputRunner(BaseTaxRunner):
    def run(self, show_progress=True):
        return self.input_df


@pytest.mark.parametrize(
    "fips,soi", [(48, 44), (12, 10), (6, 5), (1, 1), (11, 9), (56, 51)]
)
def test_fips_without_state(fips, soi):
    result = InputRunner(pd.DataFrame({"year": [2025], "statefip": [fips]}))
    assert result.input_df.state.tolist() == [soi]


def test_mixed_rows_missing_values_and_explicit_state():
    data = pd.DataFrame(
        {
            "year": [2025] * 5,
            "state": [0, None, 5, 0, None],
            "statefip": [48, 12, 48, None, 0],
        }
    )
    original = data.copy()
    result = InputRunner(data)
    assert result.input_df.state.tolist() == [44, 10, 5, 0, 0]
    pd.testing.assert_frame_equal(data, original)


@pytest.mark.parametrize("fips", [6.5, -1, 99, float("inf")])
def test_invalid_fips_rejected(fips):
    with pytest.raises(ValueError, match="valid US state FIPS"):
        InputRunner(pd.DataFrame({"year": [2025], "statefip": [fips]}))


def test_numeric_strings():
    result = InputRunner(
        pd.DataFrame({"year": [2025], "state": ["0"], "statefip": ["06"]})
    )
    assert result.input_df.state.tolist() == [5]
