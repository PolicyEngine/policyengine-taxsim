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


def test_pins_read_markers_hashes_and_comments():
    text = (
        "# header\n"
        "--index-url https://pypi.org/simple\n"
        "policyengine-us==2.6.17 \\\n"
        "    --hash=sha256:abc\n"
        "    # via policyengine-taxsim (pyproject.toml)\n"
        "tomli==2.0.1 ; python_version < '3'\n"
        "numpy==2.4.6 ; python_version >= '3'\n"
        "spm-calculator==1.0.0.post1  # inline comment\n"
        "requests[socks]==2.32.5\n"
    )
    assert check.pins(text) == {
        "policyengine-us": "2.6.17",
        "numpy": "2.4.6",
        "spm-calculator": "1.0.0.post1",
        "requests": "2.32.5",
    }


@pytest.mark.parametrize(
    "line",
    [
        "numpy>=2",
        "numpy",
        "numpy == 2.*",
        "numpy @ https://example.com/numpy.whl",
        "-e .",
        "-r other.txt",
        "numpy==",
    ],
)
def test_pins_reject_lines_that_are_not_exact_pins(line):
    with pytest.raises(ValueError):
        check.pins(f"policyengine-us==2.6.17\n{line}\n")


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


def test_mismatches_compare_versions_not_spellings():
    pinned = {"tzdata": "2024.1", "foo": "1.0"}
    installed = {"tzdata": "2024.01", "foo": "1.0.0"}
    assert check.mismatches(pinned, lookup(installed)) == {}


names = st.from_regex(r"[a-z][a-z0-9]{0,4}(-[a-z0-9]{1,4}){0,2}", fullmatch=True)
versions = st.from_regex(r"[0-9]{1,3}(\.[0-9]{1,3}){0,3}", fullmatch=True)
pinsets = st.dictionaries(names, versions, min_size=1).map(
    lambda pinned: {"policyengine-us": "2.6.17", **pinned}
)


@given(pinsets, st.data())
def test_pins_recover_every_pin_however_it_is_written(pinned, data):
    lines = ["# header"]
    for name, value in pinned.items():
        line = f"{name}=={value}"
        if data.draw(st.booleans()):
            line += " ; python_version >= '3'"
        if data.draw(st.booleans()):
            lines += [line + " \\", "    --hash=sha256:0123"]
        else:
            lines.append(line)
        if data.draw(st.booleans()):
            lines.append("    # via something")
        if data.draw(st.booleans()):
            # A pin for another interpreter must not be enforced here.
            lines.append(f"{name}==999 ; python_version < '3'")
    assert check.pins("\n".join(lines) + "\n") == pinned


@given(pinsets, st.data())
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
