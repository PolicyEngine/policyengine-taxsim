"""Tests for Stata (.dta) file format support."""

import pandas as pd
import pytest
from pathlib import Path

from policyengine_taxsim.core.io import read_input, write_output


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "taxsimid": [1, 2],
            "year": [2024, 2024],
            "state": [5, 6],
            "mstat": [1, 2],
            "pwages": [50000.0, 80000.0],
        }
    )


class TestReadInput:
    def test_read_csv(self, tmp_path, sample_df):
        csv_path = tmp_path / "input.csv"
        sample_df.to_csv(csv_path, index=False)

        result = read_input(csv_path)
        assert len(result) == 2
        assert list(result.columns) == list(sample_df.columns)

    def test_read_stata(self, tmp_path, sample_df):
        dta_path = tmp_path / "input.dta"
        sample_df.to_stata(dta_path, write_index=False)

        result = read_input(dta_path)
        assert len(result) == 2
        assert "taxsimid" in result.columns
        assert "pwages" in result.columns

    def test_read_unknown_extension_defaults_to_csv(self, tmp_path, sample_df):
        txt_path = tmp_path / "input.txt"
        sample_df.to_csv(txt_path, index=False)

        result = read_input(txt_path)
        assert len(result) == 2


class TestWriteOutput:
    def test_write_csv(self, tmp_path, sample_df):
        csv_path = tmp_path / "output.csv"
        write_output(sample_df, csv_path)

        result = pd.read_csv(csv_path)
        assert len(result) == 2
        assert list(result.columns) == list(sample_df.columns)

    def test_write_stata(self, tmp_path, sample_df):
        dta_path = tmp_path / "output.dta"
        write_output(sample_df, dta_path)

        result = pd.read_stata(dta_path)
        assert len(result) == 2
        assert "taxsimid" in result.columns

    def test_roundtrip_stata(self, tmp_path, sample_df):
        """Write then read a .dta file and verify data is preserved."""
        dta_path = tmp_path / "roundtrip.dta"
        write_output(sample_df, dta_path)
        result = read_input(dta_path)

        pd.testing.assert_frame_equal(
            result[sample_df.columns].reset_index(drop=True),
            sample_df.reset_index(drop=True),
            check_dtype=False,
        )
