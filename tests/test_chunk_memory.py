"""PolicyEngineRunner frees each pass's simulations before it builds the next.

policyengine-core links a simulation, its populations and their holders in
reference cycles: ``Simulation.link_to_entities_instances`` sets each
``population.simulation``, and every ``Holder`` keeps its ``population`` and
``simulation``. Dropping the runner's last reference therefore leaves a
finished simulation, and every array it cached, for Python's cyclic garbage
collector. Two kinds of long-lived policy also kept one alive through
their ``simulation`` attribute: policyengine-us's cached pinned policies (in
2.75.0, New York's child credit in 2018-2024 and from 2028, its EITC in 2021
and Alabama's federal tax deduction in 2021), and, with policyengine-us 1.x,
the shared policy from ``scorp_tax_benefit_system()``. Each pass builds a main
simulation, a marginal-rate branch and, for srebate, a rebate twin, and a
chunk that mixes state-0 and other records runs two passes. Before the
runner freed them between passes and chunks, a pass's simulations stayed
alive while the next pass or chunk built its own, which raised a worker's
peak memory.

These tests turn automatic collection off, so they fail every time the
runner stops freeing simulations, not only when no automatic collection
happens to run in between. After the last chunk the runner only releases its
simulations, since nothing follows, so the tests run one collection before
checking that none outlives the run. In policyengine-us 2.x every simulation that
uses a pinned policy builds its own copy of the whole tax-benefit system
(about 0.6 GB), so the cases each fill one pin, and each test starts and
ends with an empty pinned-policy cache.
"""

import functools
import gc
import weakref
from types import SimpleNamespace

import pandas as pd
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from policyengine_taxsim.runners import PolicyEngineRunner, policyengine_runner

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
        # In policyengine-us 2.75.0, Alabama in 2021 fills the pinned-policy
        # cache with its 2020-IRC federal tax deduction, and New York in 2024
        # with the pre-TCJA child credit. Each entry named a simulation of
        # the pass that filled it, which the next two passes don't replace.
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
    gc.collect()
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
    """For each drawn year, state mix and chunk size: no simulation from an
    earlier pass is alive when a pass starts, none survives a collection after
    the run, rows come back in input order, and the output equals a
    single-chunk run's.

    A New York record in 2024 makes each simulation of its pass build a
    pinned copy of the whole tax-benefit system (about 0.6 GB), so a draw
    with several of them could take this one process past a CI runner's
    memory. ``new-york-pin-2024`` above covers that path."""
    assume(not (year == 2024 and 33 in states))
    records = _records(states, year)

    with monkeypatch.context() as patch:
        output, built, alive_at_pass_start = _run_tracking_liveness(
            patch, records, chunk_size
        )
    assert set(alive_at_pass_start) == {0}
    gc.collect()
    assert all(ref() is None for ref in built)
    assert output["taxsimid"].astype(int).tolist() == list(range(1, len(states) + 1))

    with monkeypatch.context() as patch:
        patch.setattr(PolicyEngineRunner, "CHUNK_SIZE", len(states))
        single_chunk = PolicyEngineRunner(records).run(show_progress=False)
    pd.testing.assert_frame_equal(output, single_chunk)


class _Simulation:
    pass


class _Policy:
    def __init__(self):
        self.simulation = _Simulation()


class _ReadOnlyPolicy:
    """A policy whose ``simulation`` has no setter (AttributeError)."""

    @property
    def simulation(self):
        return "a simulation"


class _WeakSimulationPolicy:
    """A policy that keeps its simulation as a weak reference, so assigning
    ``None`` raises TypeError."""

    def __init__(self, simulation):
        self._simulation = weakref.ref(simulation)

    @property
    def simulation(self):
        return self._simulation()

    @simulation.setter
    def simulation(self, value):
        self._simulation = weakref.ref(value)


def test_release_clears_every_long_lived_policy(monkeypatch):
    """The release clears the shared policy and every cached pinned clone,
    whatever the cache entry's shape, and skips a policy that refuses the
    assignment. Stubs stand in for the policies, so this runs on any
    policyengine-us version, including 2.x, where the shared policy never
    holds a simulation."""
    shared, two_tuple_clone, three_tuple_clone = _Policy(), _Policy(), _Policy()
    read_only = _ReadOnlyPolicy()
    kept_alive = _Simulation()
    weak = _WeakSimulationPolicy(kept_alive)
    cache = {
        # (weak base policy, clone), as in policyengine-us 1.x
        "two": (lambda: None, two_tuple_clone),
        # (weak base policy, weak parameters, clone), as in 2.x
        "three": (lambda: None, lambda: None, three_tuple_clone),
        "read_only": (lambda: None, lambda: None, read_only),
        "weak": (lambda: None, lambda: None, weak),
    }
    monkeypatch.setattr(policyengine_runner, "scorp_tax_benefit_system", lambda: shared)
    monkeypatch.setattr(
        policyengine_runner, "_pinned_tbs", SimpleNamespace(_PINNED_TBS_CACHE=cache)
    )

    policyengine_runner._release_finished_simulations()

    assert shared.simulation is None
    assert two_tuple_clone.simulation is None
    assert three_tuple_clone.simulation is None
    assert read_only.simulation == "a simulation"
    assert weak.simulation is kept_alive


def test_release_without_a_pinned_policy_cache(monkeypatch):
    shared = _Policy()
    monkeypatch.setattr(policyengine_runner, "scorp_tax_benefit_system", lambda: shared)
    monkeypatch.setattr(policyengine_runner, "_pinned_tbs", None)

    policyengine_runner._release_finished_simulations()

    assert shared.simulation is None


def test_release_leaves_an_unbuilt_shared_policy_unbuilt(monkeypatch):
    """The release builds no shared policy just to clear it, and clears one
    that a simulation has built."""
    builds = []

    @functools.lru_cache(maxsize=1)
    def shared_policy():
        builds.append(1)
        return _Policy()

    monkeypatch.setattr(policyengine_runner, "scorp_tax_benefit_system", shared_policy)
    monkeypatch.setattr(policyengine_runner, "_pinned_tbs", None)

    policyengine_runner._release_finished_simulations()
    assert builds == []

    shared = shared_policy()
    policyengine_runner._release_finished_simulations()
    assert builds == [1]
    assert shared.simulation is None


def test_failed_chunk_still_releases(monkeypatch):
    """A chunk that raises still runs the release, so a long-lived process
    (the local or Modal API) can collect the failed pass's simulations once
    it drops the error, instead of keeping them into its next run."""
    releases = []

    def fail(self, chunk_df):
        raise RuntimeError("chunk failed")

    monkeypatch.setattr(PolicyEngineRunner, "_run_chunk", fail)
    monkeypatch.setattr(
        policyengine_runner,
        "_release_finished_simulations",
        lambda: releases.append(1),
    )

    with pytest.raises(RuntimeError, match="chunk failed"):
        PolicyEngineRunner(_records([5])).run(show_progress=False)
    assert releases == [1]


def test_release_cannot_replace_a_chunk_error(monkeypatch):
    """If the release itself fails after a chunk raises, the caller still
    gets the chunk's error (the API maps a ValueError to a 400)."""

    def fail(self, chunk_df):
        raise ValueError("bad input")

    def broken_release():
        raise MemoryError

    monkeypatch.setattr(PolicyEngineRunner, "_run_chunk", fail)
    monkeypatch.setattr(
        policyengine_runner, "_release_finished_simulations", broken_release
    )

    with pytest.raises(ValueError, match="bad input"):
        PolicyEngineRunner(_records([5])).run(show_progress=False)


@pytest.mark.parametrize(
    "years, chunk_size, expected",
    [
        # Chunks hold one year each: 2024's record, then 2025's two.
        ([2025, 2025, 2024], 1, ["collect", "collect", "release"]),
        ([2025, 2025, 2024], 10_000, ["collect", "release"]),
        ([2025, 2025, 2025], 10_000, ["release"]),
    ],
    ids=["three-chunks", "two-years", "one-chunk"],
)
def test_collects_only_before_more_simulations(
    monkeypatch, years, chunk_size, expected
):
    """The runner collects after every chunk but the last and only releases
    after the last. A full collection walks the roughly 3 million objects of
    a loaded policyengine-us, which took about 0.55 s on an Apple M5 Max,
    against about 0.64 s for a whole one-record run, and nothing gets built
    after the last chunk."""
    calls = []
    records = _records([5, 5, 5])
    records["year"] = years

    monkeypatch.setattr(PolicyEngineRunner, "CHUNK_SIZE", chunk_size)
    monkeypatch.setattr(
        PolicyEngineRunner,
        "_run_chunk",
        lambda self, chunk_df: chunk_df[["taxsimid"]].reset_index(drop=True),
    )
    monkeypatch.setattr(
        policyengine_runner,
        "_free_finished_simulations",
        lambda: calls.append("collect"),
    )
    monkeypatch.setattr(
        policyengine_runner,
        "_release_finished_simulations",
        lambda: calls.append("release"),
    )

    output = PolicyEngineRunner(records).run(show_progress=False)

    assert calls == expected
    assert output["taxsimid"].tolist() == [1, 2, 3]
