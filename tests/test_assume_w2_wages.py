"""
Tests for the --assume-w2-wages flag.

This flag sets w2_wages_from_qualified_business to a large value so that
the W-2 wage cap in the QBID calculation never binds, aligning PE's
Section 199A implementation with TAXSIM's simplified approach for S-Corp income.
"""

import importlib
from io import StringIO
from unittest.mock import patch

import pytest
import numpy as np
import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_taxsim.cli import cli


def _make_scorp_records():
    """
    Create test records with S-Corp income above the QBID phase-out threshold.

    Above $170,050 (single, 2023) / $340,100 (MFJ, 2023), the W-2 wage cap
    applies to QBID. Without W-2 wages, QBID should be zero. With
    --assume-w2-wages, the cap is bypassed and QBID = 20% of QBI.
    """
    return pd.DataFrame(
        {
            "taxsimid": [1, 2],
            "year": 2023,
            "state": [5, 33],  # CA, NY
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": [50000.0, 50000.0],
            "swages": 0.0,
            "scorp": [200000.0, 200000.0],  # S-Corp income pushes above threshold
            "idtl": 2,  # full output to get QBID in v28
        }
    )


def _make_low_income_scorp_records():
    """
    Create records with S-Corp income below the QBID phase-out threshold.

    Below the threshold, the W-2 wage cap does NOT apply, so the flag
    should have no effect on QBID.
    """
    return pd.DataFrame(
        {
            "taxsimid": [10, 11],
            "year": 2023,
            "state": [5, 33],
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": [30000.0, 30000.0],
            "swages": 0.0,
            "scorp": [50000.0, 50000.0],  # Below threshold
            "idtl": 2,
        }
    )


def _make_no_scorp_records():
    """Records with no S-Corp income — flag should have no effect."""
    return pd.DataFrame(
        {
            "taxsimid": [20, 21],
            "year": 2023,
            "state": [5, 33],
            "mstat": 1,
            "depx": 0,
            "page": 45,
            "sage": 0,
            "pwages": [100000.0, 100000.0],
            "swages": 0.0,
            "idtl": 0,
        }
    )


class TestAssumeW2WagesRunner:
    """Test the assume_w2_wages parameter on PolicyEngineRunner directly."""

    def test_flag_stored_on_runner(self):
        """Runner stores the assume_w2_wages flag."""
        records = _make_no_scorp_records()
        runner = PolicyEngineRunner(records.copy(), assume_w2_wages=True)
        assert runner.assume_w2_wages is True

    def test_flag_defaults_to_false(self):
        """Runner defaults assume_w2_wages to False."""
        records = _make_no_scorp_records()
        runner = PolicyEngineRunner(records.copy())
        assert runner.assume_w2_wages is False

    def test_scorp_above_threshold_qbid_changes(self):
        """
        For high-income S-Corp filers, --assume-w2-wages should increase QBID
        (and thus reduce federal income tax) compared to default.
        """
        records = _make_scorp_records()

        # Without flag
        runner_default = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )
        result_default = runner_default.run(show_progress=False)

        # With flag
        runner_w2 = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True, assume_w2_wages=True
        )
        result_w2 = runner_w2.run(show_progress=False)

        # With assumed W-2 wages, QBID should be higher (or equal), which means
        # federal income tax should be lower (or equal)
        for i in range(len(records)):
            assert result_w2["fiitax"].iloc[i] <= result_default["fiitax"].iloc[i], (
                f"Record {i}: fiitax with --assume-w2-wages ({result_w2['fiitax'].iloc[i]}) "
                f"should be <= without ({result_default['fiitax'].iloc[i]})"
            )

        # At least one record should show a meaningful difference
        fiitax_diff = result_default["fiitax"].values - result_w2["fiitax"].values
        assert fiitax_diff.max() > 100, (
            f"Expected meaningful QBID difference for high-income S-Corp filers, "
            f"but max fiitax reduction was only ${fiitax_diff.max():.2f}"
        )

    def test_no_scorp_flag_has_no_effect(self):
        """For records without S-Corp income, the flag should not change results."""
        records = _make_no_scorp_records()

        runner_default = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )
        result_default = runner_default.run(show_progress=False)

        runner_w2 = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True, assume_w2_wages=True
        )
        result_w2 = runner_w2.run(show_progress=False)

        np.testing.assert_array_almost_equal(
            result_default["fiitax"].values,
            result_w2["fiitax"].values,
            decimal=0,
            err_msg="Flag should not affect records without S-Corp/QBI income",
        )

    def test_low_income_scorp_flag_has_minimal_effect(self):
        """
        For S-Corp filers below the threshold, QBID = 20% of QBI regardless
        of W-2 wages, so the flag should have little to no effect.
        """
        records = _make_low_income_scorp_records()

        runner_default = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )
        result_default = runner_default.run(show_progress=False)

        runner_w2 = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True, assume_w2_wages=True
        )
        result_w2 = runner_w2.run(show_progress=False)

        # Below threshold, results should be identical or very close
        np.testing.assert_array_almost_equal(
            result_default["fiitax"].values,
            result_w2["fiitax"].values,
            decimal=0,
            err_msg="Below-threshold S-Corp filers should see no QBID change",
        )

    def test_output_shape_unchanged(self):
        """Flag should not change the number of rows or columns in output."""
        records = _make_scorp_records()

        runner_default = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )
        result_default = runner_default.run(show_progress=False)

        runner_w2 = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True, assume_w2_wages=True
        )
        result_w2 = runner_w2.run(show_progress=False)

        assert result_default.shape == result_w2.shape
        assert list(result_default.columns) == list(result_w2.columns)


class TestAssumeW2WagesCLI:
    """Test the --assume-w2-wages CLI flag on policyengine and compare commands."""

    @pytest.fixture
    def input_csv(self, tmp_path):
        """Write a small CSV with S-Corp income for CLI tests."""
        records = _make_scorp_records()
        csv_path = tmp_path / "input.csv"
        records.to_csv(csv_path, index=False)
        return str(csv_path)

    def test_policyengine_command_accepts_flag(self, input_csv, tmp_path):
        """The policyengine command should accept --assume-w2-wages without error."""
        output_path = str(tmp_path / "output.csv")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["policyengine", input_csv, "-o", output_path, "--assume-w2-wages"],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
        output_df = pd.read_csv(output_path)
        assert len(output_df) == 2

    def test_policyengine_command_without_flag(self, input_csv, tmp_path):
        """The policyengine command should work without --assume-w2-wages."""
        output_path = str(tmp_path / "output.csv")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["policyengine", input_csv, "-o", output_path],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"

    def test_policyengine_flag_changes_output(self, input_csv, tmp_path):
        """Running with vs. without the flag should produce different federal tax."""
        out_default = str(tmp_path / "out_default.csv")
        out_w2 = str(tmp_path / "out_w2.csv")
        runner = CliRunner()

        runner.invoke(cli, ["policyengine", input_csv, "-o", out_default])
        runner.invoke(
            cli,
            ["policyengine", input_csv, "-o", out_w2, "--assume-w2-wages"],
        )

        df_default = pd.read_csv(out_default)
        df_w2 = pd.read_csv(out_w2)

        # With S-Corp above threshold, the flag should change fiitax
        assert not np.allclose(
            df_default["fiitax"].values, df_w2["fiitax"].values, atol=1.0
        ), "Expected different fiitax with --assume-w2-wages for high-income S-Corp"


@pytest.mark.parametrize(
    "args, target, expected",
    [
        ([], "StitchedRunner", False),
        (["--assume-w2-wages"], "StitchedRunner", True),
        (["policyengine", "{path}", "--assume-w2-wages"], "StitchedRunner", True),
        (["--assume-w2-wages", "policyengine", "{path}"], "StitchedRunner", True),
        (["compare", "{path}", "--assume-w2-wages"], "PolicyEngineRunner", True),
        (["--assume-w2-wages", "compare", "{path}"], "PolicyEngineRunner", True),
    ],
)
def test_cli_forwards_flag(args, target, expected, tmp_path):
    """Every PolicyEngine entry point, including the stdin drop-in command,
    passes the flag to the runner; the default stays off."""
    path = tmp_path / "input.csv"
    csv = _make_scorp_records().to_csv(index=False)
    path.write_text(csv)
    module = importlib.import_module("policyengine_taxsim.cli")
    args = [str(path) if a == "{path}" else a for a in args]
    # Stop before model work; verify the flag reaches the actual runner.
    with patch.object(module, target, side_effect=RuntimeError("stop")) as runner:
        CliRunner().invoke(cli, args, input=csv)
    assert runner.call_args.kwargs["assume_w2_wages"] is expected


def test_stdin_command_flag_gives_full_qbid_for_pbusinc():
    """
    Single filer, 2024, $400,000 of pbusinc. TAXSIM documents pbusinc as QBI
    "assuming sufficient wages paid or capital to be eligible for the full
    deduction".

    Hand computation:
    - SECA base 400,000 x 0.9235 = 369,400; SECA = 168,600 x 12.4%
      + 369,400 x 2.9% = 31,619.00; deductible half 15,809.50.
    - AGI 384,190.50; less the 14,600 standard deduction = 369,590.50.
    - QBI 400,000 - 15,809.50 = 384,190.50.
    - QBID = min(20% x 384,190.50, 20% x 369,590.50) = 73,918.10.
    Taxable income is above the 2024 phase-in range ($241,950), so with no
    W-2 wages the section 199A(b)(2)(B) limit is zero and QBID is zero.
    """
    csv = "taxsimid,year,state,mstat,page,depx,pbusinc,idtl\n1,2024,0,1,40,0,400000,2\n"

    def run(args):
        result = CliRunner().invoke(cli, args, input=csv)
        assert result.exit_code == 0, f"CLI failed: {result.exception}"
        return pd.read_csv(StringIO(result.stdout)).iloc[0]

    default = run([])
    assumed = run(["--assume-w2-wages"])

    assert default["qbid"] == pytest.approx(0, abs=1)
    assert assumed["qbid"] == pytest.approx(73_918.10, abs=1)
    assert assumed["fiitax"] < default["fiitax"]
