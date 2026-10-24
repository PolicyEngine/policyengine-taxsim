"""Record which software produced a run.

``policyengine-taxsim --version`` prints the emulator, PolicyEngine-US and
PolicyEngine-Core versions and the build of the bundled TAXSIM binary.
``--provenance PATH`` writes the same facts to a JSON sidecar, with the
run's options and the SHA-256 of its input and output. PyPI does not keep
every policyengine-us release, so a run's versions have to be recorded when
it runs. Neither option changes the TAXSIM-format output.
"""

import hashlib
import importlib.metadata
import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

PROVENANCE_SCHEMA_VERSION = 1

# NBER's binaries hold their build stamp as a quoted string literal, the
# token they print as the last output header column: "cdate-2025Dec24"
# through build 20260521, "cd2026081819" in later builds.
_EMBEDDED_BUILD = re.compile(rb'"(cdate-[0-9A-Za-z]+|cd\d{10})"')

KEY_PACKAGES = {
    "policyengineTaxsimVersion": "policyengine-taxsim",
    "policyengineUsVersion": "policyengine-us",
    "policyengineCoreVersion": "policyengine-core",
}
KEY_NAMES = set(KEY_PACKAGES.values())


def parse_build_stamp(token):
    """Return the build date in a TAXSIM output header token, or None."""
    if token.startswith("cdate-"):
        return token[len("cdate-") :]
    if re.fullmatch(r"cd\d{10}", token):
        return token
    return None


def read_binary_build(path):
    """Return the build stamp embedded in a TAXSIM binary, without running it.

    This is the value ``TaxsimRunner`` reads from the binary's output header.
    Returns None when the file cannot be read or does not hold exactly one
    distinct stamp.
    """
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    stamps = {
        parse_build_stamp(match.group(1).decode("ascii"))
        for match in _EMBEDDED_BUILD.finditer(data)
    }
    return stamps.pop() if len(stamps) == 1 else None


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name):
    """Installed version of a distribution, or None if it is not installed."""
    if name == "policyengine-taxsim":
        # The running code's own version: an editable install's metadata
        # keeps the version from install time.
        from policyengine_taxsim import __version__

        return __version__
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def taxsim_binary_info(path=None):
    """Describe the TAXSIM binary a run uses: for tax years before 2021 in
    the stdin command and the policyengine subcommand, and for every record
    in the taxsim and compare subcommands."""
    info = dict.fromkeys(
        ["taxsimBinary", "taxsimBinaryPath", "taxsimBinaryBuild", "taxsimBinarySha256"]
    )
    if path is None:
        from policyengine_taxsim.runners.taxsim_runner import (
            default_taxsim_executable,
        )

        try:
            path = default_taxsim_executable()
        except OSError:  # no bundled binary for this operating system
            return info
    path = Path(path)
    info["taxsimBinary"] = path.name
    try:
        sha256 = sha256_file(path)
    except OSError:  # missing or unreadable: reported as not found
        return info
    info["taxsimBinaryPath"] = str(path.resolve())
    info["taxsimBinaryBuild"] = read_binary_build(path)
    info["taxsimBinarySha256"] = sha256
    return info


def collect_versions(taxsim_path=None):
    """Versions ``--version`` prints and every provenance sidecar records."""
    versions = {key: package_version(name) for key, name in KEY_PACKAGES.items()}
    versions.update(taxsim_binary_info(taxsim_path))
    versions["pythonVersion"] = platform.python_version()
    versions["platform"] = platform.platform()
    return versions


def format_version_report(versions):
    """Render ``collect_versions()`` output as ``--version`` prints it."""
    binary = versions["taxsimBinary"]
    if binary is None:
        build = "none bundled for this operating system"
    elif versions["taxsimBinaryPath"] is None:
        build = f"not found or unreadable ({binary})"
    else:
        build = f"{versions['taxsimBinaryBuild'] or 'unknown build'} ({binary})"
    rows = [
        (name, versions[key] or "not installed") for key, name in KEY_PACKAGES.items()
    ]
    rows += [("TAXSIM binary", build), ("Python", versions["pythonVersion"])]
    width = max(len(label) for label, _ in rows) + 1
    return "\n".join(f"{label + ':':<{width}} {value}" for label, value in rows)


def _package_source(dist):
    """Where a distribution came from, for installs not made from an index."""
    try:
        text = dist.read_text("direct_url.json")
        direct_url = json.loads(text) if text else None
    except (OSError, ValueError):
        return None
    if not isinstance(direct_url, dict) or "url" not in direct_url:
        return None
    source = {"url": direct_url["url"]}
    vcs = direct_url.get("vcs_info") or {}
    if vcs.get("commit_id"):
        source["commit"] = vcs["commit_id"]
    if (direct_url.get("dir_info") or {}).get("editable"):
        source["editable"] = True
    return source


def installed_packages():
    """Every installed distribution's version, plus the source of any that
    were installed from a URL, a git commit or a local directory. The key
    packages report the same version as ``collect_versions()``."""
    versions, sources = {}, {}
    # The first distribution found for a name is the one Python imports.
    for dist in importlib.metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:  # unreadable metadata in a broken install
            continue
        if not name or name in versions:
            continue
        canonical = re.sub(r"[-_.]+", "-", name).lower()
        versions[name] = (
            package_version(canonical) if canonical in KEY_NAMES else dist.version
        )
        source = _package_source(dist)
        if source:
            sources[name] = source
    names = sorted(versions, key=str.lower)
    return (
        {name: versions[name] for name in names},
        {name: sources[name] for name in names if name in sources},
    )


def build_provenance(
    command, options, input_info, output_info, engines, taxsim_path=None
):
    """Assemble the sidecar record for one run."""
    packages, sources = installed_packages()
    return {
        "schemaVersion": PROVENANCE_SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": command,
        "options": options,
        **collect_versions(taxsim_path),
        "input": input_info,
        "output": output_info,
        "engines": engines,
        "packageSources": sources,
        "installedPackages": packages,
    }


def is_provenance_record(path):
    """Whether ``path`` is a regular file holding a provenance record, the
    only kind of existing file a new record may replace."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > 10_000_000:
            return False
        with open(path, encoding="utf-8") as stream:
            record = json.load(stream)
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and "schemaVersion" in record


def write_provenance(path, record):
    Path(path).write_text(json.dumps(record, indent=2) + "\n")
