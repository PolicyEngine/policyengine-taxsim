"""Fail unless every package pinned in a requirements file is installed at that version.

The S-corp end-to-end workflow runs this in its dashboard-pin jobs, after any
test-only installs, to confirm they still run the locked dashboard refresh
environment.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import re
import sys

# "name==version", optionally followed by an environment marker or a hash
# continuation, as written by uv pip compile.
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", re.MULTILINE)


def pins(requirements_text):
    found = dict(PIN.findall(requirements_text))
    if "policyengine-us" not in found:
        raise ValueError("The requirements pin no policyengine-us release")
    return found


def mismatches(pinned, installed_version=version):
    """Return {name: (pinned, installed or None)} for every pin not installed."""
    wrong = {}
    for name, expected in pinned.items():
        try:
            actual = installed_version(name)
        except PackageNotFoundError:
            actual = None
        if actual != expected:
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
