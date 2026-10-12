"""Fail unless every package pinned in a requirements file is installed at that version.

The S-corp end-to-end workflow runs this in its dashboard-pin jobs, after any
test-only installs, to confirm they still run the locked dashboard refresh
environment.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import sys

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version


def pins(requirements_text):
    """Return {name: version} for every pin that applies to this interpreter.

    Reads the format uv pip compile writes: one "name==version" per line,
    optionally with an environment marker, a trailing hash continuation,
    indented "# via" comments and indented "--hash" lines. Any other
    requirement line raises, so no package goes unchecked.
    """
    found = {}
    for number, line in enumerate(requirements_text.splitlines(), 1):
        if not line.strip() or line[0].isspace() or line.startswith(("#", "--")):
            continue
        text = line.split(" #", 1)[0].rstrip().removesuffix("\\").rstrip()
        try:
            requirement = Requirement(text)
        except InvalidRequirement as error:
            raise ValueError(f"Line {number} is not a requirement: {line}") from error
        specifiers = list(requirement.specifier)
        if (
            requirement.url
            or len(specifiers) != 1
            or specifiers[0].operator != "=="
            or "*" in specifiers[0].version
        ):
            raise ValueError(f"Line {number} is not an exact pin: {line}")
        if requirement.marker is None or requirement.marker.evaluate():
            found[requirement.name] = specifiers[0].version
    if "policyengine-us" not in found:
        raise ValueError("The requirements pin no policyengine-us release")
    return found


def same_version(installed, pinned):
    try:
        return Version(installed) == Version(pinned)
    except InvalidVersion:
        return installed == pinned


def mismatches(pinned, installed_version=version):
    """Return {name: (pinned, installed or None)} for every pin not installed."""
    wrong = {}
    for name, expected in pinned.items():
        try:
            actual = installed_version(name)
        except PackageNotFoundError:
            actual = None
        if actual is None or not same_version(actual, expected):
            wrong[name] = (expected, actual)
    return wrong


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements")
    args = parser.parse_args()
    with open(args.requirements) as f:
        pinned = pins(f.read())
    wrong = mismatches(pinned)
    for name, (expected, actual) in sorted(wrong.items()):
        print(f"{name}: pinned {expected}, installed {actual or 'nothing'}")
    if wrong:
        sys.exit(f"{len(wrong)} of {len(pinned)} pinned packages differ")
    print(
        f"All {len(pinned)} pinned packages installed, including"
        f" policyengine-us {pinned['policyengine-us']}"
    )


if __name__ == "__main__":
    main()
