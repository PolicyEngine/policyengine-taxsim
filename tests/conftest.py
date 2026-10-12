"""Shared pytest configuration for the test suite."""

import pytest

SLOW_SKIP_REASON = "wall-clock benchmark, skipped by default; run with `pytest -m slow`"


def pytest_collection_modifyitems(config, items):
    """
    Skip tests marked ``slow`` unless a ``-m`` expression is given.

    The ``slow`` tests are benchmarks with absolute time limits, which pass or
    fail with the speed of the machine (#1429). They stay out of the default
    run, and so out of CI, and run on request: ``pytest -m slow``. With any
    ``-m`` expression pytest's own selection decides, so
    ``pytest -m "slow or not slow"`` runs everything.
    """
    if config.getoption("markexpr"):
        return
    skip_slow = pytest.mark.skip(reason=SLOW_SKIP_REASON)
    for item in items:
        if item.get_closest_marker("slow"):
            item.add_marker(skip_slow)
