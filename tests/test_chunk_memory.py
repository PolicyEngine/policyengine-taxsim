"""PolicyEngineRunner frees each pass's simulations before it builds the next.

policyengine-core links a simulation, its populations and their holders in
reference cycles: ``Simulation.link_to_entities_instances`` sets each
``population.simulation``, and every ``Holder`` keeps its ``population`` and
``simulation``. Dropping the runner's last reference therefore leaves a
finished simulation, and every array it cached, alive until Python's cyclic
garbage collector runs. Each pass builds a main simulation, a rebate twin
(for srebate) and a marginal-rate branch, and a chunk that mixes state-0 and
other records runs two passes. Before the runner collected between passes
and chunks, a pass's simulations stayed alive while the next pass or chunk
built its own, so a 15,000-row input (a 10,000-row chunk, then a 5,000-row
one) peaked well above a 10,000-row input.

These tests turn automatic collection off, so they fail every time the
runner stops collecting, not only when no automatic collection happens to
run in between.
"""

import gc
import weakref

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from policyengine_taxsim.runners import PolicyEngineRunner


@pytest.fixture
def automatic_gc_off():
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()


def _records(states):
    n = len(states)
    return pd.DataFrame(
        {
            "taxsimid": range(1, n + 1),
            "year": [2025] * n,
            "state": states,
            "mstat": [1 + (i % 2) for i in range(n)],
            "page": [40] * n,
            "sage": [38 if i % 2 else 0 for i in range(n)],
            "pwages": [30_000 + 20_000 * i for i in range(n)],
            "idtl": [2] * n,
        }
    )


def _run_tracking_liveness(monkeypatch, records, chunk_size):
    """Run the runner and return (output, simulations built, live
    simulations from earlier passes at the start of each pass)."""
    built = []
    alive_at_pass_start = []

    def track(original):
        def tracked(self, *args, **kwargs):
            simulation = original(self, *args, **kwargs)
            built.append(weakref.ref(simulation))
            return simulation

        return tracked

    simulate = PolicyEngineRunner._simulate

    def tracked_simulate(self, *args, **kwargs):
        alive_at_pass_start.append(sum(ref() is not None for ref in built))
        return simulate(self, *args, **kwargs)

    monkeypatch.setattr(PolicyEngineRunner, "CHUNK_SIZE", chunk_size)
    monkeypatch.setattr(
        PolicyEngineRunner,
        "_build_configured_sim",
        track(PolicyEngineRunner._build_configured_sim),
    )
    monkeypatch.setattr(
        PolicyEngineRunner,
        "_wage_perturbation_branch",
        track(PolicyEngineRunner._wage_perturbation_branch),
    )
    monkeypatch.setattr(PolicyEngineRunner, "_simulate", tracked_simulate)
    output = PolicyEngineRunner(records).run(show_progress=False)
    return output, built, alive_at_pass_start


def test_no_simulation_outlives_its_pass(monkeypatch, automatic_gc_off):
    # Chunk 1 mixes a state-0 record with a California one, so it runs two
    # passes; chunk 2 holds one Texas record and runs one.
    records = _records([0, 5, 44])

    output, built, alive_at_pass_start = _run_tracking_liveness(
        monkeypatch, records, chunk_size=2
    )

    assert len(alive_at_pass_start) == 3
    # A main simulation and a marginal-rate branch, at least, in every pass.
    assert len(built) >= 2 * len(alive_at_pass_start)
    assert alive_at_pass_start == [0, 0, 0]
    assert all(ref() is None for ref in built)
    assert output["taxsimid"].astype(int).tolist() == [1, 2, 3]


@settings(
    max_examples=4,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    states=st.lists(st.sampled_from([0, 5, 44]), min_size=2, max_size=4),
    chunk_size=st.integers(min_value=1, max_value=3),
)
def test_chunking_frees_simulations_and_keeps_outputs(
    monkeypatch, automatic_gc_off, states, chunk_size
):
    """For any chunk size and state mix: no simulation from an earlier pass
    is alive when a pass starts or after the run, rows come back in input
    order, and the output equals a single-chunk run's."""
    records = _records(states)

    with monkeypatch.context() as patch:
        output, built, alive_at_pass_start = _run_tracking_liveness(
            patch, records, chunk_size
        )
    assert set(alive_at_pass_start) == {0}
    assert all(ref() is None for ref in built)
    assert output["taxsimid"].astype(int).tolist() == list(range(1, len(states) + 1))

    with monkeypatch.context() as patch:
        patch.setattr(PolicyEngineRunner, "CHUNK_SIZE", len(states))
        single_chunk = PolicyEngineRunner(records).run(show_progress=False)
    pd.testing.assert_frame_equal(output, single_chunk)
