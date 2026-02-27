"""Tests for StitchedRunner that routes rows to PE or TAXSIM by year."""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from policyengine_taxsim.runners.stitched_runner import StitchedRunner


def _make_input(ids_and_years):
    """Helper: build minimal input DataFrame from (taxsimid, year) pairs."""
    rows = [
        {"taxsimid": tid, "year": yr, "state": 6, "mstat": 1, "pwages": 50000}
        for tid, yr in ids_and_years
    ]
    return pd.DataFrame(rows)


def _make_result(ids_and_years, prefix=""):
    """Helper: build a fake result DataFrame mirroring runner output."""
    rows = [
        {"taxsimid": tid, "year": yr, "fiitax": tid * 100.0, "siitax": 0.0}
        for tid, yr in ids_and_years
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


class TestRouting:
    """Rows are sent to the correct engine based on year."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_all_pe_years(self, MockPE, MockTaxsim):
        """All rows >= 2021 go only to PolicyEngineRunner."""
        df = _make_input([(1, 2021), (2, 2024), (3, 2025)])
        MockPE.return_value.run.return_value = _make_result(
            [(1, 2021), (2, 2024), (3, 2025)]
        )

        runner = StitchedRunner(df)
        runner.run(show_progress=False)

        MockPE.assert_called_once()
        MockTaxsim.assert_not_called()

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_all_taxsim_years(self, MockPE, MockTaxsim):
        """All rows < 2021 go only to TaxsimRunner."""
        df = _make_input([(1, 1970), (2, 2000), (3, 2020)])
        MockTaxsim.return_value.run.return_value = _make_result(
            [(1, 1970), (2, 2000), (3, 2020)]
        )

        runner = StitchedRunner(df)
        runner.run(show_progress=False)

        MockTaxsim.assert_called_once()
        MockPE.assert_not_called()

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_mixed_years(self, MockPE, MockTaxsim):
        """Mixed years split correctly between engines."""
        df = _make_input([(1, 2019), (2, 2022), (3, 1990), (4, 2025)])
        MockPE.return_value.run.return_value = _make_result(
            [(2, 2022), (4, 2025)]
        )
        MockTaxsim.return_value.run.return_value = _make_result(
            [(1, 2019), (3, 1990)]
        )

        runner = StitchedRunner(df)
        runner.run(show_progress=False)

        MockPE.assert_called_once()
        MockTaxsim.assert_called_once()

        # Check PE got the right rows
        pe_input = MockPE.call_args[0][0]
        assert sorted(pe_input["taxsimid"].tolist()) == [2, 4]

        # Check TAXSIM got the right rows
        taxsim_input = MockTaxsim.call_args[0][0]
        assert sorted(taxsim_input["taxsimid"].tolist()) == [1, 3]


# ---------------------------------------------------------------------------
# Boundary years
# ---------------------------------------------------------------------------


class TestBoundaryYears:
    """Year 2021 goes to PE, year 2020 goes to TAXSIM."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_year_2021_goes_to_pe(self, MockPE, MockTaxsim):
        df = _make_input([(1, 2021)])
        MockPE.return_value.run.return_value = _make_result([(1, 2021)])

        runner = StitchedRunner(df)
        runner.run(show_progress=False)

        MockPE.assert_called_once()
        MockTaxsim.assert_not_called()

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_year_2020_goes_to_taxsim(self, MockPE, MockTaxsim):
        df = _make_input([(1, 2020)])
        MockTaxsim.return_value.run.return_value = _make_result([(1, 2020)])

        runner = StitchedRunner(df)
        runner.run(show_progress=False)

        MockTaxsim.assert_called_once()
        MockPE.assert_not_called()


# ---------------------------------------------------------------------------
# Output ordering
# ---------------------------------------------------------------------------


class TestOutputOrdering:
    """Result rows are returned in the original taxsimid order."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_order_preserved(self, MockPE, MockTaxsim):
        df = _make_input([(3, 2019), (1, 2023), (4, 1990), (2, 2025)])
        MockPE.return_value.run.return_value = _make_result(
            [(1, 2023), (2, 2025)]
        )
        MockTaxsim.return_value.run.return_value = _make_result(
            [(3, 2019), (4, 1990)]
        )

        runner = StitchedRunner(df)
        result = runner.run(show_progress=False)

        assert result["taxsimid"].tolist() == [3, 1, 4, 2]


# ---------------------------------------------------------------------------
# Configurable cutoff
# ---------------------------------------------------------------------------


class TestConfigurableCutoff:
    """pe_min_year parameter shifts the routing boundary."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_custom_cutoff(self, MockPE, MockTaxsim):
        df = _make_input([(1, 2022), (2, 2023)])
        # With cutoff at 2023, only year 2023 goes to PE
        MockPE.return_value.run.return_value = _make_result([(2, 2023)])
        MockTaxsim.return_value.run.return_value = _make_result([(1, 2022)])

        runner = StitchedRunner(df, pe_min_year=2023)
        runner.run(show_progress=False)

        pe_input = MockPE.call_args[0][0]
        assert pe_input["taxsimid"].tolist() == [2]

        taxsim_input = MockTaxsim.call_args[0][0]
        assert taxsim_input["taxsimid"].tolist() == [1]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Single-row inputs and empty DataFrame."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_single_pe_row(self, MockPE, MockTaxsim):
        df = _make_input([(1, 2024)])
        MockPE.return_value.run.return_value = _make_result([(1, 2024)])

        runner = StitchedRunner(df)
        result = runner.run(show_progress=False)

        assert len(result) == 1
        MockPE.assert_called_once()
        MockTaxsim.assert_not_called()

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_single_taxsim_row(self, MockPE, MockTaxsim):
        df = _make_input([(1, 1980)])
        MockTaxsim.return_value.run.return_value = _make_result([(1, 1980)])

        runner = StitchedRunner(df)
        result = runner.run(show_progress=False)

        assert len(result) == 1
        MockTaxsim.assert_called_once()
        MockPE.assert_not_called()

    def test_empty_dataframe_raises(self):
        """Empty DataFrame raises ValueError (from BaseTaxRunner)."""
        with pytest.raises(ValueError, match="cannot be empty"):
            StitchedRunner(pd.DataFrame())


# ---------------------------------------------------------------------------
# Kwargs forwarding
# ---------------------------------------------------------------------------


class TestKwargsForwarding:
    """PE-specific kwargs (logs, disable_salt) are forwarded."""

    @patch("policyengine_taxsim.runners.stitched_runner.TaxsimRunner")
    @patch("policyengine_taxsim.runners.stitched_runner.PolicyEngineRunner")
    def test_pe_kwargs_forwarded(self, MockPE, MockTaxsim):
        df = _make_input([(1, 2024)])
        MockPE.return_value.run.return_value = _make_result([(1, 2024)])

        runner = StitchedRunner(df, logs=True, disable_salt=True)
        runner.run(show_progress=False)

        _, kwargs = MockPE.call_args
        assert kwargs["logs"] is True
        assert kwargs["disable_salt"] is True


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    """The CLI stdin/stdout mode uses StitchedRunner."""

    def test_cli_imports_stitched_runner(self):
        """StitchedRunner is importable from the runners package."""
        from policyengine_taxsim.runners import StitchedRunner as SR

        assert SR is StitchedRunner

    @patch("policyengine_taxsim.cli.StitchedRunner")
    def test_cli_uses_stitched_runner(self, MockStitched):
        """The CLI default mode instantiates StitchedRunner."""
        from click.testing import CliRunner
        from policyengine_taxsim.cli import cli

        MockStitched.return_value.run.return_value = _make_result(
            [(1, 2024)]
        )
        # Mock input_df attribute for YAML generation check
        MockStitched.return_value.input_df = _make_input([(1, 2024)])

        cli_runner = CliRunner()
        result = cli_runner.invoke(
            cli, input="taxsimid,year,state,mstat,pwages\n1,2024,6,1,50000\n"
        )

        assert result.exit_code == 0
        MockStitched.assert_called_once()
