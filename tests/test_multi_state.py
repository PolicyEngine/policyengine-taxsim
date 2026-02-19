"""
Multi-state batch tests to guard against StateGroup enum regressions.

The state_group variable in policyengine-us must correctly map all state
codes to their StateGroup (CONTIGUOUS_US, AK, HI, etc.).  A previous bug
(fixed in policyengine-us 1.449.1) called StateGroup.encode() on raw
state codes like 'AL' and 'KY', which are not valid enum values.  The
error only surfaces in multi-state batches where contiguous and
non-contiguous states are mixed.

These tests ensure the wrapper handles all states—including Kentucky
(which triggers ky_family_size_tax_credit_rate -> state_group) and
non-contiguous states (AK, HI)—without error.
"""

import pytest
import numpy as np
import pandas as pd

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _ky_single_filer():
    """Single Kentucky filer with wage income."""
    return pd.DataFrame(
        [
            {
                "taxsimid": 1,
                "year": 2023,
                "state": 18,  # Kentucky
                "mstat": 1,
                "pwages": 50000,
                "idtl": 2,
            }
        ]
    )


def _ky_family():
    """Married Kentucky family with dependents (exercises family_size_tax_credit)."""
    return pd.DataFrame(
        [
            {
                "taxsimid": 1,
                "year": 2023,
                "state": 18,  # Kentucky
                "mstat": 2,
                "pwages": 60000,
                "swages": 30000,
                "depx": 3,
                "age1": 10,
                "age2": 7,
                "age3": 4,
                "idtl": 2,
            }
        ]
    )


def _multi_state_batch():
    """Records spanning all 51 states — triggers the StateGroup bug if present."""
    records = []
    for i, state in enumerate(range(1, 52)):
        records.append(
            {
                "taxsimid": i + 1,
                "year": 2023,
                "state": state,
                "mstat": 2,
                "pwages": 40000,
                "depx": 2,
                "age1": 8,
                "age2": 5,
                "idtl": 0,
            }
        )
    return pd.DataFrame(records)


def _mixed_contiguous_and_noncontiguous():
    """Mix of contiguous (KY, CA, NY) and non-contiguous (AK, HI) states."""
    return pd.DataFrame(
        [
            {"taxsimid": 1, "year": 2023, "state": 18, "mstat": 1, "pwages": 50000, "idtl": 0},  # KY
            {"taxsimid": 2, "year": 2023, "state": 5, "mstat": 1, "pwages": 50000, "idtl": 0},   # CA
            {"taxsimid": 3, "year": 2023, "state": 33, "mstat": 1, "pwages": 50000, "idtl": 0},  # NY
            {"taxsimid": 4, "year": 2023, "state": 2, "mstat": 1, "pwages": 50000, "idtl": 0},   # AK
            {"taxsimid": 5, "year": 2023, "state": 12, "mstat": 1, "pwages": 50000, "idtl": 0},  # HI
        ]
    )


class TestKentuckySingleState:
    """Kentucky single-state tests (ky_family_size_tax_credit path)."""

    def test_ky_single_filer_completes(self):
        df = _ky_single_filer()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        assert len(result) == 1
        assert result["state"].iloc[0] == 18

    def test_ky_single_filer_has_state_tax(self):
        df = _ky_single_filer()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        # Kentucky has a flat income tax; $50k wages should produce non-zero siitax
        assert result["siitax"].iloc[0] > 0

    def test_ky_family_with_dependents_completes(self):
        df = _ky_family()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        assert len(result) == 1
        assert result["siitax"].iloc[0] > 0


class TestMultiStateBatch:
    """Multi-state batch tests that guard against StateGroup enum errors."""

    def test_all_51_states_complete(self):
        """This is the exact scenario that triggered the StateGroup bug."""
        df = _multi_state_batch()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        assert len(result) == 51

    def test_all_51_states_have_results(self):
        df = _multi_state_batch()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        # Every state should have a fiitax value (even if zero)
        assert not result["fiitax"].isna().any()

    def test_ky_in_multi_state_batch_has_state_tax(self):
        df = _multi_state_batch()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        ky_row = result[result["state"] == 18]
        assert len(ky_row) == 1
        assert ky_row["siitax"].iloc[0] != 0

    def test_mixed_contiguous_and_noncontiguous(self):
        """KY + CA + NY (contiguous) mixed with AK + HI (non-contiguous)."""
        df = _mixed_contiguous_and_noncontiguous()
        runner = PolicyEngineRunner(df, logs=False, disable_salt=True)
        result = runner.run(show_progress=False)
        assert len(result) == 5
        # AK and HI should have no income tax
        assert result[result["state"] == 2]["siitax"].iloc[0] == 0  # AK
        # KY should have income tax
        assert result[result["state"] == 18]["siitax"].iloc[0] > 0  # KY
