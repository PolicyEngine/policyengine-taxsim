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
# (resources/taxsimtest/README.md), which has none of the regressions below.
CURRENT_BUILD = "cd2026102718"

# The first build with the correction reported on taxsim #1225: AddMed is
# out of fiitax in 2013-2023 too.
ADDMED_CORRECTION_BUILD = "cd2026100817"


def _bundled_build():
    """The build stamp of this platform's bundled taxsimtest, read from the file."""
    path = TaxsimRunner._detect_taxsim_executable(None)
    match = re.search(rb"cd20\d{8}", path.read_bytes()) if path.exists() else None
    return match.group().decode() if match else "unknown"


BUNDLED_BUILD = _bundled_build()


def bundled_build_is_at_least(build):
    """Whether the bundled build is `build` or a later one. Stamps are
    cdYYYYMMDDHH, so they sort by date."""
    return BUNDLED_BUILD.startswith("cd") and BUNDLED_BUILD >= build


def on_current_build(values):
    """`values` where this platform bundles CURRENT_BUILD, else nothing."""
    return set(values) if BUNDLED_BUILD == CURRENT_BUILD else set()


TAXSIM_1461 = (
    "taxsim #1461: bundled build cd2026102718 multiplies New York's 2024 "
    "Empire State child credit by 33% a second time below the income limit "
    "(sctc 108.90 = 0.33 x 330 for one child aged 13-16), so siitax is higher "
    "than by Form IT-213."
)

TAXSIM_1482 = (
    "taxsim #1482: bundled build cd2026102718 counts nonprop twice in federal "
    "AGI (v10) in every year before 2024, and in the state AGI that starts "
    "from it, so v10, fiitax and the taxes built on them differ from earlier "
    "builds."
)


def check_known_mismatches(mismatches, known, reason):
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
