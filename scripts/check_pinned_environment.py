"""Fail unless every package pinned in a requirements file is installed at that version.

The S-corp end-to-end workflow runs this in its dashboard-pin jobs, after any
test-only installs, to confirm they still run the locked dashboard refresh
environment.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import re
import sys

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version


# Options allowed on a line of their own: they only choose where pip finds
# packages, not which packages it installs.
SOURCE_OPTIONS = {
    "-i",
    "--index-url",
    "--extra-index-url",
    "--no-index",
    "-f",
    "--find-links",
    "--trusted-host",
    "--pre",
    "--prefer-binary",
    "--only-binary",
    "--no-binary",
    "--use-feature",
}
# The only option allowed after a requirement.
REQUIREMENT_OPTIONS = {"--hash"}
# pip's comment rule: "#" at the start of a line or after whitespace.
COMMENT = re.compile(r"(^|\s)#.*$")


def logical_lines(requirements_text):
    """Yield (first line number, text) with comments removed and "\\" lines joined."""
    pending, start = [], None
    for number, line in enumerate(requirements_text.splitlines(), 1):
        text = COMMENT.sub("", line).strip()
        start = start or number
        if text.endswith("\\"):
            pending.append(text[:-1])
            continue
        yield start, " ".join(pending + [text])
        pending, start = [], None
    if pending:
        yield start, " ".join(pending)


def pins(requirements_text):
    """Return {name: version} for every pin that applies to this interpreter.

    Reads a pip requirements file such as uv pip compile writes. As pip does,
    a line's requirement runs up to its first token that starts with "-", and
    the rest are options. A requirement must be an exact "name==version" pin,
    optionally with an environment marker, and may carry only --hash options.
    A line with no requirement may carry only options that choose a package
    source. Anything else (an included file, constraints, an editable or URL
    requirement, a version range) raises, so no package goes unchecked.
    """
    found = {}
    for number, text in logical_lines(requirements_text):
        tokens = text.split()
        split = next(
            (i for i, token in enumerate(tokens) if token.startswith("-")),
            len(tokens),
        )
        args, options = tokens[:split], tokens[split:]
        allowed = REQUIREMENT_OPTIONS if args else SOURCE_OPTIONS
        for token in options:
            # Tokens that do not start with "-" are values of the option before.
            if token.startswith("-") and token.split("=", 1)[0] not in allowed:
                raise ValueError(f"Line {number} has an unsupported option: {token}")
        if not args:
            continue
        try:
            requirement = Requirement(" ".join(args))
        except InvalidRequirement as error:
            raise ValueError(f"Line {number} is not a requirement: {text}") from error
        specifiers = list(requirement.specifier)
        if (
            requirement.url
            or len(specifiers) != 1
            or specifiers[0].operator != "=="
            or "*" in specifiers[0].version
        ):
            raise ValueError(f"Line {number} is not an exact pin: {text}")
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
