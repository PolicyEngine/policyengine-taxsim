"""Upstream TAXSIM regressions in the bundled build that tests tolerate by name.

Tests that pin the bundled binary's own output list the exact values a known
regression changes. Any other difference still fails; the listed ones xfail
while they last, and the test fails once they are gone so the list is cleaned
up (the same contract as a strict xfail).
"""

import pytest

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
