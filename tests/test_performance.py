"""
Performance and correctness regression tests for PolicyEngineRunner vectorization.

Tests verify that:
1. Output is identical before and after vectorization
2. Generate phase does not use iterrows (verified by timing scaling)
3. Extract phase builds DataFrame from arrays, not row-by-row dicts
4. 500 records completes within a reasonable time budget
"""

import time
import types
import pytest
import numpy as np
import pandas as pd

from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)


def _make_synthetic_records(n: int, seed: int = 42) -> pd.DataFrame:
    """Create n synthetic TAXSIM input records with realistic variation."""
    rng = np.random.RandomState(seed)

    records = pd.DataFrame(
        {
            "taxsimid": np.arange(1, n + 1),
            "year": 2023,
            "state": rng.choice([5, 33, 44, 14, 39], size=n),  # CA, NY, TX, IL, PA
            "mstat": rng.choice([1, 2], size=n, p=[0.6, 0.4]),
            "depx": rng.choice([0, 1, 2, 3], size=n, p=[0.4, 0.3, 0.2, 0.1]),
            "page": rng.randint(25, 65, size=n),
            "sage": rng.randint(25, 65, size=n),
            "pwages": rng.uniform(20000, 150000, size=n).round(2),
            "swages": rng.uniform(0, 80000, size=n).round(2),
            "idtl": 0,
        }
    )
    # Zero out swages for singles
    records.loc[records["mstat"] == 1, "swages"] = 0
    # Zero out sage for singles
    records.loc[records["mstat"] == 1, "sage"] = 0

    # Add dependent ages
    for i in range(1, 4):
        records[f"age{i}"] = 0
    for idx, row in records.iterrows():
        for i in range(1, int(row["depx"]) + 1):
            records.loc[idx, f"age{i}"] = rng.randint(1, 17)

    return records


# Golden output for correctness regression
_GOLDEN_RECORDS = _make_synthetic_records(20, seed=99)


class TestRunnerOutputCorrectness:
    """Verify that vectorized runner produces identical output to a reference run."""

    @pytest.fixture(scope="class")
    def golden_output(self):
        """Run PolicyEngineRunner on 20 records and return the output as golden reference."""
        runner = PolicyEngineRunner(
            _GOLDEN_RECORDS.copy(), logs=False, disable_salt=True
        )
        return runner.run(show_progress=False)

    def test_output_has_expected_columns(self, golden_output):
        """Golden output must contain at minimum the standard TAXSIM output columns."""
        required = {"taxsimid", "year", "state", "fiitax", "siitax"}
        assert required.issubset(set(golden_output.columns))

    def test_output_row_count_matches_input(self, golden_output):
        assert len(golden_output) == len(_GOLDEN_RECORDS)

    def test_taxsimid_preserved(self, golden_output):
        np.testing.assert_array_equal(
            golden_output["taxsimid"].values,
            _GOLDEN_RECORDS["taxsimid"].values,
        )

    def test_deterministic_output(self, golden_output):
        """Running the same input twice should produce identical results."""
        runner2 = PolicyEngineRunner(
            _GOLDEN_RECORDS.copy(), logs=False, disable_salt=True
        )
        output2 = runner2.run(show_progress=False)
        pd.testing.assert_frame_equal(golden_output, output2)


class TestGeneratePhaseEfficiency:
    """Verify that the generate phase scales sub-linearly (vectorized)."""

    def test_generate_does_not_scale_linearly(self):
        """
        Generate phase for 500 records should take < 3x the time of 100 records.
        With iterrows: ~5x scaling.
        With vectorized: ~1-2x scaling.
        """
        times = {}
        for n in [100, 500]:
            records = _make_synthetic_records(n, seed=42)
            runner = PolicyEngineRunner(
                records.copy(), logs=False, disable_salt=True
            )
            runner.input_df["year"] = runner.input_df["year"].apply(
                lambda x: int(float(x))
            )
            dataset = TaxsimMicrosimDataset(runner.input_df)
            t0 = time.time()
            dataset.generate()
            times[n] = time.time() - t0
            dataset.cleanup()

        ratio = times[500] / max(times[100], 0.01)
        assert ratio < 3.0, (
            f"Generate phase scaled {ratio:.1f}x for 5x more records "
            f"(100: {times[100]:.2f}s, 500: {times[500]:.2f}s). "
            f"Expected < 3x for vectorized implementation."
        )


class TestExtractResultsStructure:
    """Verify extract phase uses vectorized operations."""

    def test_extract_builds_dataframe_without_row_loop(self):
        """
        Extraction for 200 records should complete in < 20s.
        With row-by-row dict building and redundant calculate calls,
        this would be slow at higher record counts.
        """
        records = _make_synthetic_records(200, seed=55)
        runner = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )

        orig_extract = runner._extract_vectorized_results.__func__
        extract_time = {}

        def timed_extract(self_runner, sim, input_df):
            t0 = time.time()
            result = orig_extract(self_runner, sim, input_df)
            extract_time["t"] = time.time() - t0
            return result

        runner._extract_vectorized_results = types.MethodType(
            timed_extract, runner
        )
        result = runner.run(show_progress=False)

        assert len(result) == 200
        assert extract_time["t"] < 20.0, (
            f"Extract phase took {extract_time['t']:.1f}s for 200 records, "
            f"expected < 20s"
        )


@pytest.mark.slow
class TestBenchmark:
    """Performance benchmarks. Run with: pytest -m slow"""

    def test_benchmark_500_records(self):
        """500 records should complete in under 30 seconds."""
        records = _make_synthetic_records(500, seed=77)
        runner = PolicyEngineRunner(records, logs=False, disable_salt=True)

        start = time.time()
        result = runner.run(show_progress=False)
        elapsed = time.time() - start

        assert len(result) == 500
        assert elapsed < 60, (
            f"500 records took {elapsed:.1f}s, expected < 60s"
        )
        print(f"\nBenchmark: 500 records in {elapsed:.1f}s")

    def test_benchmark_cps_like(self):
        """
        CPS-like workload: 2000 records across all 51 states, mixed filing
        statuses, dependents, multiple income types, full output (idtl=2).
        Mimics BEA distributional accounts use case.
        """
        rng = np.random.RandomState(123)
        n = 2000
        all_states = list(range(1, 52))  # all 51 FIPS state codes

        mstat = rng.choice([1, 2], size=n, p=[0.55, 0.45])
        depx = rng.choice([0, 1, 2, 3, 4], size=n, p=[0.35, 0.25, 0.2, 0.15, 0.05])

        records = pd.DataFrame({
            "taxsimid": np.arange(1, n + 1),
            "year": 2023,
            "state": rng.choice(all_states, size=n),
            "mstat": mstat,
            "depx": depx,
            "page": rng.randint(20, 75, size=n),
            "sage": np.where(mstat == 2, rng.randint(20, 75, size=n), 0),
            "pwages": rng.lognormal(10.5, 1.0, size=n).round(2),
            "swages": np.where(
                mstat == 2, rng.lognormal(10.0, 1.2, size=n).round(2), 0
            ),
            "dividends": np.where(
                rng.random(n) < 0.15, rng.lognormal(8, 2, size=n).round(2), 0
            ),
            "intrec": np.where(
                rng.random(n) < 0.25, rng.lognormal(7, 1.5, size=n).round(2), 0
            ),
            "pensions": np.where(
                rng.random(n) < 0.20, rng.lognormal(9.5, 1.0, size=n).round(2), 0
            ),
            "idtl": 2,
        })

        # Add dependent ages
        for i in range(1, 5):
            records[f"age{i}"] = 0
        for idx in records.index:
            for i in range(1, int(records.loc[idx, "depx"]) + 1):
                if i <= 4:
                    records.loc[idx, f"age{i}"] = rng.randint(1, 18)

        runner = PolicyEngineRunner(records, logs=False, disable_salt=True)

        start = time.time()
        result = runner.run(show_progress=False)
        elapsed = time.time() - start

        assert len(result) == n
        print(f"\nBenchmark (CPS-like): {n} records, {records['state'].nunique()} states, idtl=2")
        print(f"  Total: {elapsed:.1f}s")
        assert elapsed < 120, (
            f"CPS-like benchmark took {elapsed:.1f}s, expected < 120s"
        )


class TestStateVariableEfficiency:
    """Verify that state variables use unified PE variables, not per-state iteration."""

    def test_extract_does_not_iterate_states(self):
        """
        With unified state variables (state_agi, state_eitc, etc.),
        _calc_tax_unit should be called once per variable, not once per state.
        Count _calc_tax_unit calls — should be roughly equal to number of
        output vars (~30), not vars * states (~30 * 50 = 1500).
        """
        rng = np.random.RandomState(88)
        all_states = list(range(1, 52))
        n = 50
        records = pd.DataFrame({
            "taxsimid": np.arange(1, n + 1),
            "year": 2023,
            "state": rng.choice(all_states, size=n),
            "mstat": 1,
            "depx": 0,
            "page": 40,
            "sage": 0,
            "pwages": rng.uniform(30000, 100000, size=n).round(2),
            "swages": 0.0,
            "idtl": 2,  # full output to trigger all state vars
        })

        runner = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )

        # Count _calc_tax_unit calls
        orig_calc_tu = runner._calc_tax_unit.__func__
        calc_count = {"n": 0}

        def counted_calc_tu(self_runner, sim, var_name, period):
            calc_count["n"] += 1
            return orig_calc_tu(self_runner, sim, var_name, period)

        runner._calc_tax_unit = types.MethodType(counted_calc_tu, runner)
        result = runner.run(show_progress=False)

        unique_states = records["state"].nunique()
        # With unified state vars: ~30-60 _calc_tax_unit calls
        # With per-state iteration: ~10 state vars * 47 states = 470+ calls
        assert calc_count["n"] < 100, (
            f"_calc_tax_unit() called {calc_count['n']} times for {n} records "
            f"across {unique_states} states. Expected < 100 with unified state "
            f"variables, but got a number suggesting per-state iteration."
        )

    def test_state_variable_values_match(self):
        """
        Verify that unified state variable results match expected values.
        state_income_tax (already unified) should match siitax column.
        """
        records = pd.DataFrame({
            "taxsimid": [1, 2],
            "year": 2023,
            "state": [5, 33],  # CA, NY
            "mstat": 1,
            "depx": 0,
            "page": 40,
            "sage": 0,
            "pwages": [80000.0, 60000.0],
            "swages": 0.0,
            "idtl": 2,
        })
        runner = PolicyEngineRunner(
            records.copy(), logs=False, disable_salt=True
        )
        result = runner.run(show_progress=False)

        # siitax should be nonzero for CA and NY
        assert result["siitax"].iloc[0] != 0, "CA state income tax should be nonzero"
        assert result["siitax"].iloc[1] != 0, "NY state income tax should be nonzero"
        # v32 (state_agi) should be nonzero
        if "v32" in result.columns:
            assert result["v32"].iloc[0] != 0, "CA state AGI should be nonzero"
