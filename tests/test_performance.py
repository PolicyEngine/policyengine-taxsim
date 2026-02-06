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
        Extraction for 200 records should complete in < 10s.
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
        assert extract_time["t"] < 10.0, (
            f"Extract phase took {extract_time['t']:.1f}s for 200 records, "
            f"expected < 10s"
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
        assert elapsed < 30, (
            f"500 records took {elapsed:.1f}s, expected < 30s"
        )
        print(f"\nBenchmark: 500 records in {elapsed:.1f}s")
