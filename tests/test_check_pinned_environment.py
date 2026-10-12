"""Tests for the pinned-environment check used by the S-corp end-to-end workflow."""

import importlib.util
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from hypothesis import given, strategies as st
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "check_pinned_environment", ROOT / "scripts/check_pinned_environment.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def lookup(installed):
    def installed_version(name):
        if name not in installed:
            raise PackageNotFoundError(name)
        return installed[name]

    return installed_version


def test_dashboard_requirements_match_their_source_pin():
    compiled = check.pins(
        (ROOT / "scripts/dashboard-refresh-requirements.txt").read_text()
    )
    source = check.pins((ROOT / "scripts/dashboard-refresh.in").read_text())
    assert source.items() <= compiled.items()
    assert len(compiled) > len(source)


def test_pins_skip_comments_and_keep_markers_and_hashes():
    text = (
        "# header\n"
        "policyengine-us==2.6.17 \\\n"
        "    --hash=sha256:abc\n"
        "tomli==2.0.1 ; python_version < '3.11'\n"
        "    # via policyengine-core\n"
        "spm-calculator==1.0.0.post1\n"
    )
    assert check.pins(text) == {
        "policyengine-us": "2.6.17",
        "tomli": "2.0.1",
        "spm-calculator": "1.0.0.post1",
    }


def test_requirements_without_policyengine_us_are_rejected():
    with pytest.raises(ValueError):
        check.pins("numpy==2.4.6\n")


def test_mismatches_report_wrong_and_missing_packages():
    pinned = {"policyengine-us": "2.6.17", "numpy": "2.4.6", "pandas": "3.0.6"}
    installed = {"policyengine-us": "2.38.19", "numpy": "2.4.6"}
    assert check.mismatches(pinned, lookup(installed)) == {
        "policyengine-us": ("2.6.17", "2.38.19"),
        "pandas": ("3.0.6", None),
    }


names = st.from_regex(r"[a-z][a-z0-9-]{0,10}", fullmatch=True)
versions = st.from_regex(r"[0-9]{1,3}(\.[0-9]{1,3}){0,3}", fullmatch=True)


@given(st.dictionaries(names, versions, min_size=1), st.data())
def test_mismatches_flag_exactly_the_changed_pins(pinned, data):
    # An exact install passes; changing or removing some packages flags exactly those.
    assert check.mismatches(pinned, lookup(pinned)) == {}
    changed = data.draw(st.sets(st.sampled_from(sorted(pinned))))
    removed = data.draw(st.sets(st.sampled_from(sorted(pinned))))
    installed = {
        name: value + ".1" if name in changed else value
        for name, value in pinned.items()
        if name not in removed
    }
    assert set(check.mismatches(pinned, lookup(installed))) == changed | removed
