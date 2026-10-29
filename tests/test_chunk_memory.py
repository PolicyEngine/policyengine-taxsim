"""PolicyEngineRunner frees each pass's simulations before it builds the next.

policyengine-core links a simulation, its populations and their holders in
reference cycles: ``Simulation.link_to_entities_instances`` sets each
``population.simulation``, and every ``Holder`` keeps its ``population`` and
``simulation``. Dropping the runner's last reference therefore leaves a
finished simulation, and every array it cached, for Python's cyclic garbage
collector. Two long-lived policies also kept one alive through their
``simulation`` attribute: policyengine-us's cached pinned policies (New
York's child credit in 2018-2024 and from 2028, its EITC in 2021, Alabama's
federal tax deduction in 2021), and, with policyengine-us 1.x, the shared
policy from ``scorp_tax_benefit_system()``. Each pass builds a main
simulation, a marginal-rate branch and, for srebate, a rebate twin, and a
chunk that mixes state-0 and other records runs two passes. Before the
runner freed them between passes and chunks, a pass's simulations stayed
alive while the next pass or chunk built its own, which raised a worker's
peak memory.

These tests turn automatic collection off, so they fail every time the
runner stops freeing simulations, not only when no automatic collection
happens to run in between. In policyengine-us 2.x every simulation that
uses a pinned policy builds its own copy of the whole tax-benefit system
(about 0.6 GB), so the cases each fill one pin, and each test starts and
ends with an empty pinned-policy cache.
"""

import gc
import weakref

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from policyengine_taxsim.runners import PolicyEngineRunner

try:
    from policyengine_us.tools import pinned_tbs
except ImportError:
    pinned_tbs = None


def _empty_pinned_policy_cache():
    getattr(pinned_tbs, "_PINNED_TBS_CACHE", {}).clear()
    gc.collect()


@pytest.fixture
def automatic_gc_off():
    _empty_pinned_policy_cache()
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()
        _empty_pinned_policy_cache()


def _records(states, year=2025):
    n = len(states)
    return pd.DataFrame(
        {
            "taxsimid": range(1, n + 1),
            "year": [year] * n,
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


@pytest.mark.parametrize(
    "year, states, chunk_size",
    [
        # Chunk 1 mixes a state-0 record with a California one, so it runs
        # two passes; chunk 2 holds one Texas record and runs one.
        (2025, [0, 5, 44], 2),
        # Alabama in 2021 fills policyengine-us's pinned-policy cache with
        # its 2020-IRC federal tax deduction, and New York in 2024 with the
        # pre-TCJA child credit. Each entry named a simulation of the pass
        # that filled it, which the next two passes don't replace.
        (2021, [1, 5, 5], 1),
        (2024, [33, 5, 5], 1),
    ],
    ids=["mixed-chunk-2025", "alabama-pin-2021", "new-york-pin-2024"],
)
def test_no_simulation_outlives_its_pass(
    monkeypatch, automatic_gc_off, year, states, chunk_size
):
    records = _records(states, year)

    output, built, alive_at_pass_start = _run_tracking_liveness(
        monkeypatch, records, chunk_size=chunk_size
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
    year=st.sampled_from([2024, 2025]),
    states=st.lists(st.sampled_from([0, 5, 33, 44]), min_size=2, max_size=4),
    chunk_size=st.integers(min_value=1, max_value=3),
)
def test_chunking_frees_simulations_and_keeps_outputs(
    monkeypatch, automatic_gc_off, year, states, chunk_size
):
    """For any year, state mix and chunk size: no simulation from an earlier
    pass is alive when a pass starts or after the run, rows come back in
    input order, and the output equals a single-chunk run's."""
    records = _records(states, year)

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
