"""
Performance and correctness regression tests for PolicyEngineRunner vectorization.

Tests verify that:
1. Output is identical before and after vectorization
2. Generate phase does not use iterrows (verified by timing scaling)
3. Extract phase makes the same number of top-level calculate calls however
   many records there are (verified by counting calls, so it does not depend
   on machine speed)
4. Extract phase uses unified state variables, not per-state iteration

The wall-clock benchmarks (TestBenchmark) are marked ``slow``.
tests/conftest.py skips them unless a ``-m`` expression is given;
``pytest -m slow`` runs them.
"""

import time
import types
import pytest
import numpy as np
import pandas as pd

from policyengine_taxsim.runners.policyengine_runner import (
    Microsimulation,
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


def _make_cps_like_records(n: int, seed: int = 123) -> pd.DataFrame:
    """
    Create n CPS-like TAXSIM input records: all 51 states, mixed filing
    statuses, dependents, several income types, full output (idtl=2).
    Mimics BEA distributional accounts use case.
    """
    rng = np.random.RandomState(seed)
    all_states = list(range(1, 52))  # all 51 TAXSIM (SOI) state numbers

    mstat = rng.choice([1, 2], size=n, p=[0.55, 0.45])
    depx = rng.choice([0, 1, 2, 3, 4], size=n, p=[0.35, 0.25, 0.2, 0.15, 0.05])

    records = pd.DataFrame(
        {
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
        }
    )

    # Add dependent ages
    for i in range(1, 5):
        records[f"age{i}"] = 0
    for idx in records.index:
        for i in range(1, int(records.loc[idx, "depx"]) + 1):
            if i <= 4:
                records.loc[idx, f"age{i}"] = rng.randint(1, 18)

    return records


def _tile_records(records: pd.DataFrame, copies: int) -> pd.DataFrame:
    """Repeat the records ``copies`` times, each row with its own taxsimid."""
    tiled = pd.concat([records] * copies, ignore_index=True)
    tiled["taxsimid"] = np.arange(1, len(tiled) + 1)
    return tiled


def _count_extract_calculate_calls(records: pd.DataFrame, monkeypatch) -> int:
    """
    Run PolicyEngineRunner on ``records`` and return how many ``calculate``
    calls ``_extract_vectorized_results`` made on its simulations (the main
    one, the rebate-free twin and the marginal-rate branch).

    Only the runner's own calls count. A PolicyEngine formula reads its
    dependencies through ``calculate`` too; those nested calls depend on the
    households (which formulas apply to anyone), so they are left out.
    """
    state = {"extracting": False, "depth": 0, "calls": 0}
    orig_calculate = Microsimulation.calculate

    def counted_calculate(sim, *args, **kwargs):
        if state["extracting"] and state["depth"] == 0:
            state["calls"] += 1
        state["depth"] += 1
        try:
            return orig_calculate(sim, *args, **kwargs)
        finally:
            state["depth"] -= 1

    runner = PolicyEngineRunner(records.copy(), logs=False, disable_salt=True)
    orig_extract = runner._extract_vectorized_results.__func__

    def tracked_extract(self_runner, *args, **kwargs):
        state["extracting"] = True
        try:
            return orig_extract(self_runner, *args, **kwargs)
        finally:
            state["extracting"] = False

    runner._extract_vectorized_results = types.MethodType(tracked_extract, runner)
    with monkeypatch.context() as patch:
        patch.setattr(Microsimulation, "calculate", counted_calculate)
        result = runner.run(show_progress=False)

    assert len(result) == len(records)
    return state["calls"]


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


class TestFederalOutputAdjustments:
    # 2021 and 2023 are years where taxsimtest cd2026081819 still adds
    # AddMed to fiitax; the emulator excludes it in every year
    # (tests/test_addmed_excluded_from_fiitax.py).
    @pytest.mark.parametrize("year", [2021, 2023, 2024])
    def test_fiitax_uses_income_tax_only_excludes_additional_medicare_tax(self, year):
        """
        fiitax is populated from the income_tax mapping and must NOT be
        further adjusted by additional_medicare_tax in any year. The
        Additional Medicare Tax (Form 8959) is counted in tfica/fica and
        reported in the separate `addmed` column (taxsim #416), so
        `_calc_tax_unit` is never called for `additional_medicare_tax`
        during fiitax assembly.
        """
        records = pd.DataFrame(
            {
                "taxsimid": [1],
                "year": [year],
                "state": [5],  # CA
                "mstat": [1],
                "depx": [0],
                "page": [45],
                "sage": [0],
                "pwages": [300000.0],
                "swages": [0.0],
                "idtl": [0],
            }
        )
        runner = PolicyEngineRunner(records.copy(), logs=False, disable_salt=True)
        runner.mappings = {
            "policyengine_to_taxsim": {
                "fiitax": {
                    "implemented": True,
                    "variable": "income_tax",
                    "idtl": [{"standard_output": 0}, {"full_output": 2}],
                }
            }
        }

        fake_sim = types.SimpleNamespace(
            tax_benefit_system=types.SimpleNamespace(
                variables={
                    "income_tax": object(),
                    "additional_medicare_tax": object(),
                }
            )
        )
        calc_calls = []

        def fake_calc_tu(self_runner, sim, var_name, period):
            calc_calls.append(var_name)
            if var_name == "income_tax":
                return np.array([1000.0])
            if var_name == "additional_medicare_tax":
                # We assert below that this branch is never taken,
                # but return a sentinel so a future regression that
                # re-introduces the call surfaces obviously rather
                # than silently using a zero.
                return np.array([900.0])
            raise AssertionError(f"Unexpected variable: {var_name}")

        runner._calc_tax_unit = types.MethodType(fake_calc_tu, runner)

        result = runner._extract_vectorized_results(fake_sim, runner.input_df)

        assert result["fiitax"].iloc[0] == pytest.approx(1000.0)
        assert "additional_medicare_tax" not in calc_calls, (
            "fiitax must not call additional_medicare_tax: AddMed is "
            "counted in tfica/fica and reported in `addmed`, never in "
            "fiitax (taxsim #416)."
        )


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
            runner = PolicyEngineRunner(records.copy(), logs=False, disable_salt=True)
            runner.input_df["year"] = runner.input_df["year"].apply(
                lambda x: int(float(x))
            )
            dataset = TaxsimMicrosimDataset(runner.input_df)
            t0 = time.time()
            dataset.generate()
            times[n] = time.time() - t0
            dataset.cleanup()

        # Floor the denominator at 100ms: when the 100-record base runs in a
        # few tens of milliseconds, scheduler noise dominates the ratio and
        # the test flakes on CI (observed 5.3x/5.9x on runs where both
        # absolute times were well under a quarter second). A genuinely
        # pathological (e.g. quadratic row-loop) regression still trips the
        # assertion because times[500] grows into whole seconds.
        ratio = times[500] / max(times[100], 0.1)
        assert ratio < 5.0, (
            f"Generate phase scaled {ratio:.1f}x for 5x more records "
            f"(100: {times[100]:.2f}s, 500: {times[500]:.2f}s). "
            f"Expected < 5x for vectorized implementation."
        )


class TestExtractResultsStructure:
    """Verify extract phase uses vectorized operations."""

    @pytest.mark.parametrize(
        "idtl_cycle",
        [(0,), (2, 5)],
        ids=["standard-output", "full-output"],
    )
    def test_extract_builds_dataframe_without_row_loop(self, idtl_cycle, monkeypatch):
        """
        Extraction makes the same number of top-level ``calculate`` calls
        however many records there are. Before it was vectorized (#692) it
        looped over the rows and called ``sim.calculate`` for every output
        variable of every row, which made runtime grow with the record count.

        Both inputs hold the same 51 households, one in each state, so the
        state-specific paths run for every state and only the number of
        records differs. Requiring equal counts catches a loop over only some
        records too, such as one extra call per Delaware record.

        Extraction chooses its outputs from the idtl values in the input, so
        each output mode is checked on its own:

        - standard-output: every record at idtl 0, the default and the
          workload the old timed version of this test ran;
        - full-output: records alternating idtl 2 and 5. idtl 2 alone leaves
          out staxbc and sctc (and with them the Delaware staxbc path), idtl 5
          alone leaves out addmed and v44, and the two together request every
          implemented output.

        Counting calls, instead of timing the phase, gives the same answer on
        any machine: a 60-second limit here failed on slow macOS CI runners
        with no row loop to find (#1429).
        """
        base = _make_cps_like_records(51, seed=55)
        base["state"] = np.arange(1, 52)  # one household in each state
        base["idtl"] = np.resize(idtl_cycle, len(base))
        more = _tile_records(base, 4)

        base_calls = _count_extract_calculate_calls(base, monkeypatch)
        more_calls = _count_extract_calculate_calls(more, monkeypatch)

        assert base_calls > 0, (
            "No calculate call was counted during extraction, so this test "
            "is no longer measuring anything."
        )
        assert more_calls == base_calls, (
            f"Extract phase made {more_calls} calculate calls for "
            f"{len(more)} records but {base_calls} for {len(base)} records "
            f"in the same states. The count must not depend on the number of "
            f"records; a difference points to a per-record loop."
        )


@pytest.mark.slow
class TestBenchmark:
    """
    Wall-clock benchmarks. Run with: pytest -m slow

    Skipped by default (tests/conftest.py): a limit in seconds only means
    something on a machine of known speed. On a shared macOS CI runner
    test_benchmark_cps_like took 266.3s against its 240s limit with no code
    change behind it, and the failed job skipped a release (#1429).
    TestExtractResultsStructure guards the same kind of workload against
    per-record work without a clock.
    """

    def test_benchmark_500_records(self):
        """500 records should complete in under 2 minutes with the
        three-pass --disable-salt code path (two PE Microsim invocations)."""
        records = _make_synthetic_records(500, seed=77)
        runner = PolicyEngineRunner(records, logs=False, disable_salt=True)

        start = time.time()
        result = runner.run(show_progress=False)
        elapsed = time.time() - start

        assert len(result) == 500
        assert elapsed < 120, f"500 records took {elapsed:.1f}s, expected < 120s"
        print(f"\nBenchmark: 500 records in {elapsed:.1f}s")

    def test_benchmark_cps_like(self):
        """
        CPS-like workload: 2000 records across all 51 states, mixed filing
        statuses, dependents, multiple income types, full output (idtl=2).
        Mimics BEA distributional accounts use case.
        """
        n = 2000
        records = _make_cps_like_records(n)

        runner = PolicyEngineRunner(records, logs=False, disable_salt=True)

        start = time.time()
        result = runner.run(show_progress=False)
        elapsed = time.time() - start

        assert len(result) == n
        print(
            f"\nBenchmark (CPS-like): {n} records, {records['state'].nunique()} states, idtl=2"
        )
        print(f"  Total: {elapsed:.1f}s")
        # 2x ceiling accounts for the three-pass --disable-salt code path.
        assert elapsed < 240, f"CPS-like benchmark took {elapsed:.1f}s, expected < 240s"


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
        records = pd.DataFrame(
            {
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
            }
        )

        runner = PolicyEngineRunner(records.copy(), logs=False, disable_salt=True)

        # Count _calc_tax_unit calls
        orig_calc_tu = runner._calc_tax_unit.__func__
        calc_count = {"n": 0}

        def counted_calc_tu(self_runner, sim, var_name, period):
            calc_count["n"] += 1
            return orig_calc_tu(self_runner, sim, var_name, period)

        runner._calc_tax_unit = types.MethodType(counted_calc_tu, runner)
        result = runner.run(show_progress=False)

        unique_states = records["state"].nunique()
        # With unified state vars: ~30-60 _calc_tax_unit calls per PE pass.
        # When `disable_salt=True`, the runner makes two PE passes
        # (state-side + federal-side, see PolicyEngineRunner.run docstring),
        # so the expected ceiling roughly doubles.
        # With per-state iteration: ~10 state vars * 47 states = 470+ calls.
        assert calc_count["n"] < 200, (
            f"_calc_tax_unit() called {calc_count['n']} times for {n} records "
            f"across {unique_states} states. Expected < 200 with unified state "
            f"variables (×2 for the disable_salt three-pass), but got a number "
            f"suggesting per-state iteration."
        )

    def test_state_variable_values_match(self):
        """
        Verify that unified state variable results match expected values.
        state_income_tax (already unified) should match siitax column.
        """
        records = pd.DataFrame(
            {
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
            }
        )
        runner = PolicyEngineRunner(records.copy(), logs=False, disable_salt=True)
        result = runner.run(show_progress=False)

        # siitax should be nonzero for CA and NY
        assert result["siitax"].iloc[0] != 0, "CA state income tax should be nonzero"
        assert result["siitax"].iloc[1] != 0, "NY state income tax should be nonzero"
        # v32 (state_agi) should be nonzero
        if "v32" in result.columns:
            assert result["v32"].iloc[0] != 0, "CA state AGI should be nonzero"
