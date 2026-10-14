"""Upstream TAXSIM regressions in the bundled build that tests tolerate by name.

Tests that pin the bundled binary's own output list the exact values a known
regression changes. Any other difference still fails; the listed ones xfail
while they last, and the test fails once they are gone so the list is cleaned
up (the same contract as a strict xfail).
"""

import re

import pytest

from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

# macOS and Linux bundle this build; Windows keeps cd2026081318
# (resources/taxsimtest/README.md), which has neither regression.
OCTOBER_BUILD = "cd2026100817"


def _bundled_build():
    """The build stamp of this platform's bundled taxsimtest, read from the file."""
    path = TaxsimRunner._detect_taxsim_executable(None)
    match = re.search(rb"cd20\d{8}", path.read_bytes()) if path.exists() else None
    return match.group().decode() if match else "unknown"


BUNDLED_BUILD = _bundled_build()


def on_october_build(values):
    """`values` where this platform bundles the October build, else nothing."""
    return set(values) if BUNDLED_BUILD == OCTOBER_BUILD else set()


TAXSIM_1416 = (
    "taxsim #1416: bundled build cd2026100817 starts the EITC phase-out at $0 "
    "for some filers (EITC = maximum credit - phase-out rate x income, when "
    "that is below the phase-in amount), so v25, fiitax and state credits "
    "built on the federal EITC differ from earlier builds."
)


def check_known_mismatches(mismatches, known, reason=TAXSIM_1416):
    """Fail on a mismatch outside `known`; xfail while `known` ones remain."""
    unexpected = sorted(set(mismatches) - set(known))
    assert not unexpected, f"Differences from the pinned values: {unexpected}"
    fixed = sorted(set(known) - set(mismatches))
    assert not fixed, (
        f"{fixed} match the pinned values again; remove them from the known "
        f"list ({reason})"
    )
    if known:
        pytest.xfail(reason)
