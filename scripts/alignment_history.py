"""Agreement with TAXSIM, release by release.

Each row of dashboard/public/data/alignment_history.json scores one released
policyengine-taxsim / policyengine-us pair against a fixed TAXSIM reference:
the TAXSIM side of the published full-data release the dashboard links to
(FULL_DATA_RELEASE_BASE in dashboard/src/constants/index.js). The households,
tolerances and PolicyEngine options are those of scripts/refresh_dashboard.py,
whose match_flags() decides every match here too. Only the PolicyEngine side
changes between rows, so a change between rows comes from the emulator or the
model, not from TAXSIM.

Subcommands:
  plan       list the pairs to measure, and those PyPI can no longer install
  reference  download the published comparison, verify it, extract TAXSIM's side
  measure    install one pair in an isolated environment and score it
  merge      add rows to the history file and check its invariants

Like the refresh coordinator, this process never imports PolicyEngine. Each
pair runs in its own virtual environment through scripts/alignment_worker.py.
"""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "dashboard/public/data/alignment_history.json"
CONSTANTS = ROOT / "dashboard/src/constants/index.js"
WORKER = Path(__file__).resolve().parent / "alignment_worker.py"
REPO_URL = "https://github.com/PolicyEngine/policyengine-taxsim"
PYPI = "https://pypi.org/pypi/{}/json"
US_CHANGELOG = (
    "https://raw.githubusercontent.com/PolicyEngine/policyengine-us/main/CHANGELOG.md"
)
YEARS = (2021, 2022, 2023, 2024, 2025)
PYTHON = "3.11"
SCHEMA_VERSION = 1
# A pair is installed as PyPI stood just after its later release.
INSTALL_GRACE = timedelta(minutes=1)
# Rows a single workflow run may measure (a GitHub matrix holds 256 jobs).
MAX_PAIRS = 250

_spec = importlib.util.spec_from_file_location(
    "refresh_dashboard", Path(__file__).resolve().parent / "refresh_dashboard.py"
)
refresh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refresh)

STATES = refresh.STATES
# The TAXSIM-side fields match_flags() reads: the gross-income inputs and the
# three tax outputs. Everything else in the published rows is not needed.
GROSS_FIELDS = (
    "pwages",
    "swages",
    "psemp",
    "ssemp",
    "intrec",
    "dividends",
    "otherprop",
    "nonprop",
    "pensions",
    "pui",
    "sui",
    "stcg",
    "ltcg",
    "gssi",
)
OUTPUTS = ("fiitax", "siitax", "srebate")
REFERENCE_FIELDS = ("taxsimid", "state_code", *GROSS_FIELDS, *OUTPUTS)
# Tallies, in the order match_flags() returns its flags, named like the
# summary's rates: unsuffixed is within $15, Rel within 1% of income, RelNet
# within 1% of income with one-time state rebates netted out.
COUNTS = (
    "federalMatches",
    "stateMatches",
    "federalMatchesRel",
    "stateMatchesRel",
    "stateMatchesRelNet",
)
RATES = (
    "federalMatchPct",
    "stateMatchPct",
    "federalMatchPctRel",
    "stateMatchPctRel",
    "stateMatchPctRelNet",
)
ROW_STATUSES = {"measured", "partial", "failed", "install-failed", "not-installable"}
YEAR_STATUSES = {"measured", "failed"}


# ---------------------------------------------------------------- utilities


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text):
    """PyPI writes naive UTC times; changelogs write dates."""
    if len(text) == 10:
        text += "T00:00:00"
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def version_key(text):
    from packaging.version import Version

    return Version(text)


def retry(action, attempts=6):
    """Retry a network action with backoff; GitHub release downloads 5xx at times."""
    for attempt in range(attempts):
        try:
            return action()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(60, 2 ** (attempt + 1)))


def fetch(url):
    def get():
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()

    return retry(get)


def download(url, path):
    """Stream a URL to disk and return its SHA-256."""

    def get():
        h = hashlib.sha256()
        tmp = path.with_suffix(path.suffix + ".part")
        with (
            urllib.request.urlopen(url, timeout=600) as response,
            tmp.open("wb") as out,
        ):
            for block in iter(lambda: response.read(1024 * 1024), b""):
                h.update(block)
                out.write(block)
        tmp.replace(path)
        return h.hexdigest()

    return retry(get)


def write_gzip_csv(path, fields, rows):
    """Write a gzipped CSV whose bytes depend only on its rows.

    gzip.open stamps the file name and time into the header, which would give
    the same data a different SHA-256 on every run.
    """
    import io

    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as packed:
            with io.TextIOWrapper(packed, newline="") as stream:
                writer = csv.DictWriter(stream, fields)
                writer.writeheader()
                writer.writerows(rows)


def run_url():
    if os.environ.get("GITHUB_RUN_ID"):
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        repo = os.environ.get("GITHUB_REPOSITORY", "PolicyEngine/policyengine-taxsim")
        return f"{server}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return None


def reference_tag(constants=CONSTANTS):
    """The full-data release the dashboard links to is the TAXSIM reference."""
    match = re.search(r"releases/download/([^'\"\s/]+)", constants.read_text())
    if not match:
        raise ValueError(f"No FULL_DATA_RELEASE_BASE release in {constants}")
    return match.group(1)


def household_id(row):
    return str(int(float(row["taxsimid"])))


def row_id(taxsim_version, us_version, reference):
    return f"taxsim-{taxsim_version}+us-{us_version}@{reference}"


# ------------------------------------------------------------- aggregation


def empty_tally():
    return {"records": 0, **{name: 0 for name in COUNTS}}


def score(reference_rows, outputs):
    """Tally agreement for one year.

    reference_rows: dicts with REFERENCE_FIELDS (TAXSIM's side).
    outputs: {taxsimid: {"fiitax", "siitax", "srebate"}} (PolicyEngine's side).
    Every reference household must have exactly one PolicyEngine output.
    """
    overall = empty_tally()
    by_state = {code: empty_tally() for code in STATES}
    seen = set()
    for taxsim in reference_rows:
        key = household_id(taxsim)
        if key in seen:
            raise ValueError(f"Household {key} appears twice in the reference")
        seen.add(key)
        if key not in outputs:
            raise ValueError(f"No PolicyEngine output for household {key}")
        if taxsim["state_code"] not in by_state:
            raise ValueError(f"Household {key} has no valid state code")
        flags = refresh.match_flags(taxsim, outputs[key])
        for tally in (overall, by_state[taxsim["state_code"]]):
            tally["records"] += 1
            for name, flag in zip(COUNTS, flags):
                tally[name] += int(flag)
    extra = set(outputs) - seen
    if extra:
        raise ValueError(f"{len(extra)} PolicyEngine outputs have no reference row")
    return {
        **overall,
        "byState": {
            "households": [by_state[c]["records"] for c in STATES],
            **{name: [by_state[c][name] for c in STATES] for name in COUNTS},
        },
    }


def percentages(year):
    """The five dashboard rates, rounded as refresh_dashboard.summarize does."""
    n = year["records"]
    return [round(100 * year[name] / n, 1) for name in COUNTS]


# --------------------------------------------------------------- reference


def read_pairs(path):
    """Yield (taxsim, policyengine) rows from a published comparison CSV."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        reader = iter(csv.DictReader(stream))
        for taxsim in reader:
            pe = next(reader)
            if (
                taxsim["source"] != "taxsim"
                or pe["source"] != "policyengine"
                or taxsim["taxsimid"] != pe["taxsimid"]
            ):
                raise ValueError(f"Rows are not TAXSIM/PolicyEngine pairs: {path}")
            yield taxsim, pe


def source_rows(source=None):
    with (source or refresh.SOURCE).open(newline="") as stream:
        yield from csv.DictReader(stream)


def summary_check(published, summary):
    """Compare a recomputed year with the dashboard's committed summary."""
    problems = []
    if published["records"] != summary["totalRecords"]:
        problems.append("totalRecords")
    for name, value in zip(RATES, percentages(published)):
        if summary.get(name) != value:
            problems.append(f"{name} {summary.get(name)} != {value}")
    states = {entry["state"]: entry for entry in summary.get("stateBreakdown", [])}
    by_state = published["byState"]
    for i, code in enumerate(STATES):
        entry = states.get(code)
        if entry is None:
            # summarize() lists only states with households.
            if by_state["households"][i]:
                problems.append(f"{code} missing from summary")
            continue
        if (
            entry["households"] != by_state["households"][i]
            or entry["federalMatches"] != by_state["federalMatches"][i]
            or entry["stateMatches"] != by_state["stateMatches"][i]
        ):
            problems.append(f"{code} counts differ")
            continue
        state_rates = [
            round(100 * by_state[name][i] / entry["households"], 1) for name in COUNTS
        ]
        names = [
            "federalPct",
            "statePct",
            "federalPctRel",
            "statePctRel",
            "statePctRelNet",
        ]
        for name, value in zip(names, state_rates):
            if entry.get(name) != value:
                problems.append(f"{code} {name} {entry.get(name)} != {value}")
    return problems


def binary_build(ref, path, sha256):
    """NBER's build stamp in a TAXSIM binary held in git at ref, if it is sha256.

    NBER binaries hold the stamp as a quoted literal ("cd2026090910", or
    "cdate-2025Aug23" in older builds), the token they print last in the
    output header.
    """
    try:
        blob = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if hashlib.sha256(blob).hexdigest() != sha256:
        return None
    match = re.search(rb'"(cd\d{10}|cdate-[0-9A-Za-z]+)"', blob)
    return match.group(1).decode() if match else None


def build_reference(tag, work, years, summaries_dir=None, keep_downloads=False):
    """Extract and verify the TAXSIM reference from a published release."""
    work.mkdir(parents=True, exist_ok=True)
    summaries_dir = summaries_dir or ROOT / "dashboard/public/data"
    base = f"{REPO_URL}/releases/download/{tag}"
    source = {household_id(row): row for row in source_rows()}
    meta = {"release": tag, "url": f"{REPO_URL}/releases/tag/{tag}", "years": {}}
    for year in years:
        provenance = json.loads(fetch(f"{base}/provenance_{year}.json"))
        full = work / f"comparison_results_{year}.csv"
        sha = download(f"{base}/comparison_results_{year}.csv", full)
        if sha != provenance["outputSha256"]:
            raise ValueError(f"{year}: release CSV does not match its provenance")
        if provenance.get("sourceSha256") != refresh.digest(refresh.SOURCE):
            raise ValueError(f"{year}: release was built from a different source")
        compact = work / f"reference_{year}.csv.gz"
        published = {}
        rows = []
        for taxsim, pe in read_pairs(full):
            key = household_id(taxsim)
            raw = source.get(key)
            if raw is None:
                raise ValueError(f"{year}: household {key} is not in the source")
            if taxsim["state_code"] != STATES[int(float(raw["state"])) - 1]:
                raise ValueError(f"{year}: household {key} state differs")
            for name in GROSS_FIELDS:
                if not math.isclose(
                    refresh.number(taxsim.get(name)),
                    refresh.number(raw.get(name)),
                    rel_tol=1e-9,
                    abs_tol=1e-6,
                ):
                    raise ValueError(f"{year}: household {key} {name} differs")
            row = {name: taxsim.get(name, "") for name in REFERENCE_FIELDS}
            row["taxsimid"] = key
            rows.append(row)
            published[key] = {name: pe[name] for name in OUTPUTS}
        write_gzip_csv(compact, REFERENCE_FIELDS, rows)
        if len(rows) != len(source):
            raise ValueError(
                f"{year}: {len(rows)} reference rows, {len(source)} in source"
            )
        recomputed = score(rows, published)
        summary_path = summaries_dir / str(year) / f"summary_{year}.json"
        summary = json.loads(summary_path.read_text())
        problems = summary_check(recomputed, summary)
        if problems:
            raise ValueError(
                f"{year}: the release does not reproduce {summary_path.name}: "
                + "; ".join(problems[:10])
            )
        if not keep_downloads:
            full.unlink()
        fallback = provenance.get("taxsimFallback")
        if fallback:
            fallback = {
                k: fallback[k]
                for k in ("states", "years", "sha256", "reason")
                if k in fallback
            }
            fallback["taxsimBinaryBuild"] = binary_build(
                provenance["taxsimFallback"].get("sourceCommit", ""),
                "resources/taxsimtest/taxsimtest-linux.exe",
                fallback.get("sha256"),
            )
        meta["years"][str(year)] = {
            "records": len(rows),
            "comparisonSha256": sha,
            "referenceSha256": refresh.digest(compact),
            "taxsimBinarySha256": provenance.get("taxsimBinarySha256"),
            "taxsimBinaryBuild": binary_build(
                tag,
                "resources/taxsimtest/taxsimtest-linux.exe",
                provenance.get("taxsimBinarySha256"),
            ),
            "taxsimFallback": fallback,
            "generatedAt": provenance.get("generatedAt"),
            # The PolicyEngine side the dashboard headline shows for this year.
            "publishedPolicyengineUsVersion": provenance.get("policyengineUsVersion"),
            "publishedEmulatorCommit": provenance.get("emulatorCommit"),
            "publishedScorpTreatment": provenance.get("scorpTreatment")
            or summary.get("metadata", {}).get("scorpTreatment"),
            "published": {k: recomputed[k] for k in ("records", *COUNTS)},
        }
        print(f"Reference {year}: {len(rows)} households verified", flush=True)
    meta["source"] = refresh.SOURCE.name
    meta["sourceSha256"] = refresh.digest(refresh.SOURCE)
    refresh.atomic_json(work / "reference.json", meta)
    return meta


def read_reference(work, year):
    with gzip.open(work / f"reference_{year}.csv.gz", "rt", newline="") as stream:
        return list(csv.DictReader(stream))


# ------------------------------------------------------------------- plan


def pypi_releases(name):
    """{version: {"uploaded": datetime, "requiresPython": str|None}} from PyPI."""
    data = json.loads(fetch(PYPI.format(name)))
    releases = {}
    for version, files in data["releases"].items():
        files = [f for f in files if not f.get("yanked")]
        if files:
            releases[version] = {
                "uploaded": max(parse_time(f["upload_time"]) for f in files),
                "requiresPython": next(
                    (
                        f.get("requires_python")
                        for f in files
                        if f.get("requires_python")
                    ),
                    None,
                ),
            }
    return releases


def changelog_dates(text):
    """{version: date} for every release a towncrier/changelog file lists."""
    dates = {}
    for match in re.finditer(r"^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})", text, re.M):
        dates.setdefault(match.group(1), parse_time(match.group(2)))
    return dates


def us_release_times(repo, ref="HEAD"):
    """{version: (commit time, commit)} of policyengine-us version bumps in a clone.

    The commit that first sets a version is its bump; PyPI's upload follows it.
    """
    log = subprocess.run(
        [
            "git",
            "log",
            ref,
            "--format=C %H %cI",
            "-p",
            "-G^version = ",
            "--",
            "pyproject.toml",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    found, current = {}, None
    for line in log.splitlines():
        if line.startswith("C "):
            _, sha, moment = line.split()
            current = (parse_time(moment), sha)
        elif match := re.match(r'^\+version = "([^"]+)"', line):
            # The log runs newest first, so the last assignment is the oldest.
            found[match.group(1)] = current
    return found


def publish_conclusion(sha, repo="PolicyEngine/policyengine-us"):
    """The conclusion of the Publish job for a version-bump commit, if any."""
    runs = json.loads(
        subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/runs?head_sha={sha}&per_page=50"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )["workflow_runs"]
    for run in runs:
        if run["event"] != "push":
            continue
        jobs = json.loads(
            subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )["jobs"]
        for job in jobs:
            if job["name"] == "Publish":
                return job["conclusion"]
    return None


def timeline(available, dated, precise=None):
    """Every known release, oldest first, with the window it was published in.

    available: PyPI releases (exact upload times). dated: changelog dates for
    every release, including those PyPI has deleted. precise: optional exact
    times for deleted releases. Returns dicts with version, lo, hi (the earliest
    and latest moment the release can have been published) and onPypi.

    Releases are numbered in time order, so a deleted release known only by
    its date was published that day, after the nearest earlier release with a
    known time and before the nearest later one. A changelog entry newer than
    everything on PyPI is not published yet and is left out.
    """
    precise = {
        v: t if isinstance(t, tuple) else (t, None) for v, t in (precise or {}).items()
    }
    versions = sorted(set(available) | set(dated), key=version_key)
    if available:
        newest = max(available, key=version_key)
        versions = [v for v in versions if version_key(v) <= version_key(newest)]
    known = {}
    for version in versions:
        if version in available:
            known[version] = available[version]["uploaded"]
        elif version in precise:
            known[version] = precise[version][0]
    out = []
    for i, version in enumerate(versions):
        if version in known:
            lo = hi = known[version]
        else:
            day = dated[version]
            lo, hi = day, day + timedelta(days=1) - timedelta(seconds=1)
            earlier = [known[v] for v in versions[:i] if v in known]
            later = [known[v] for v in versions[i + 1 :] if v in known]
            if earlier:
                lo = max(lo, max(earlier))
            if later:
                hi = min(hi, min(later))
        out.append(
            {
                "version": version,
                "lo": lo,
                "hi": hi,
                "onPypi": version in available,
                "commit": precise.get(version, (None, None))[1],
            }
        )
    return out


def newest_at(releases, moment, allowed=lambda version: True):
    """The newest allowed release published by a moment, and whether that is certain.

    It is uncertain when a newer allowed release may or may not have been
    published by then (its window straddles the moment).
    """
    best, straddling = _newest(releases, moment, allowed)
    return best, not straddling


def _newest(releases, moment, allowed):
    candidates = [r for r in releases if allowed(r["version"])]
    before = [r for r in candidates if r["hi"] <= moment]
    best = max(before, key=lambda r: version_key(r["version"])) if before else None
    floor = version_key(best["version"]) if best else None
    straddling = [
        r
        for r in candidates
        if r["lo"] <= moment < r["hi"]
        and (floor is None or version_key(r["version"]) > floor)
    ]
    return best, straddling


def newest_installed(releases, moment, allowed, never_published):
    """newest_at, skipping releases that never reached PyPI.

    never_published(release) is True only for a release whose publish job did
    not succeed; nobody could install it, so it can't be what a user got.
    Releases PyPI deleted after publishing stay in.
    """
    dropped = set()
    while True:
        best, straddling = _newest(
            releases, moment, lambda v: allowed(v) and v not in dropped
        )
        unpublished = [
            r
            for r in ([best] if best else []) + straddling
            if not r["onPypi"] and never_published(r)
        ]
        if not unpublished:
            return best, not straddling
        dropped.update(r["version"] for r in unpublished)


def us_allowed(spec, us_available):
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version

    specifier = SpecifierSet(spec or "")

    def allowed(version):
        if Version(version) not in specifier:
            return False
        info = us_available.get(version)
        requires = info and info["requiresPython"]
        return not requires or Version(PYTHON + ".0") in SpecifierSet(requires)

    return allowed


def taxsim_requirement(version):
    """policyengine-taxsim's policyengine-us requirement for a PyPI release."""
    data = json.loads(
        fetch(f"https://pypi.org/pypi/policyengine-taxsim/{version}/json")
    )
    for requirement in data["info"].get("requires_dist") or []:
        name = re.match(r"[A-Za-z0-9_.-]+", requirement).group(0).lower()
        if name.replace("_", "-") == "policyengine-us":
            spec = requirement[len(name) :].split(";")[0]
            return spec.strip().strip("()").strip()
    return ""


def pair(taxsim, us, trigger, reference):
    """A pair to measure, or a not-installable row explaining why it can't be."""
    released = max(taxsim["hi"], us["hi"])
    entry = {
        "id": row_id(taxsim["version"], us["version"], reference),
        "policyengineTaxsimVersion": taxsim["version"],
        "policyengineUsVersion": us["version"],
        "policyengineTaxsimReleasedAt": iso(taxsim["hi"]),
        "policyengineUsReleasedAt": iso(us["hi"]),
        "releasedAt": iso(released),
        "triggers": [trigger],
        "reference": reference,
    }
    missing = [
        f"{name} {release['version']}"
        for name, release in (("policyengine-taxsim", taxsim), ("policyengine-us", us))
        if not release["onPypi"]
    ]
    if missing:
        return {
            **entry,
            "status": "not-installable",
            "reason": " and ".join(missing)
            + (" are" if len(missing) > 1 else " is")
            + " not on PyPI",
        }
    entry["installAsOf"] = iso(released + INSTALL_GRACE)
    return entry


def plan(
    mode,
    reference,
    history=None,
    taxsim_version=None,
    us_repo=None,
    retry_failed=False,
    us_ref="HEAD",
    since_days=7,
    max_pairs=MAX_PAIRS,
    log=print,
):
    """Pairs to measure and rows that cannot be measured, minus those recorded.

    recent: backfill, limited to releases from the last since_days days and to
      what PyPI serves (a changelog entry PyPI lacks never published).
    backfill: every policyengine-taxsim release with the policyengine-us release
      that was newest when it came out (what installing it that day gave), plus,
      for each day, the last policyengine-us release PyPI still serves with the
      policyengine-taxsim release that was newest then.
    release: one policyengine-taxsim release, with the newest policyengine-us.
    latest: the newest release of each.
    """
    taxsim_available = pypi_releases("policyengine-taxsim")
    us_available = pypi_releases("policyengine-us")
    taxsim_all = timeline(
        taxsim_available, changelog_dates((ROOT / "CHANGELOG.md").read_text())
    )
    us_all = timeline(
        us_available,
        changelog_dates(fetch(US_CHANGELOG).decode()),
        us_release_times(us_repo, us_ref) if us_repo else None,
    )
    if mode != "backfill":
        # Going forward PyPI is the record: a changelog entry PyPI lacks is
        # still being published, or its publish failed.
        us_all = [r for r in us_all if r["onPypi"]]
    since = now() - timedelta(days=since_days) if mode == "recent" else None
    conclusions = {}

    def never_published(release):
        """True when the release's publish job did not succeed (needs us_repo)."""
        if not release.get("commit"):
            return False
        if release["version"] not in conclusions:
            conclusions[release["version"]] = publish_conclusion(release["commit"])
            log(
                f"policyengine-us {release['version']}: publish job "
                f"{conclusions[release['version']]}"
            )
        return conclusions[release["version"]] in ("failure", "cancelled", "skipped")

    requirements = {}

    def requirement(version):
        if version not in requirements:
            requirements[version] = (
                taxsim_requirement(version) if version in taxsim_available else ""
            )
        return requirements[version]

    entries = []
    skipped = 0
    if mode in ("backfill", "recent", "release"):
        for release in taxsim_all:
            if mode == "release" and release["version"] != taxsim_version:
                continue
            if since and release["hi"] < since:
                continue
            allowed = us_allowed(requirement(release["version"]), us_available)
            us, certain = newest_installed(
                us_all, release["hi"], allowed, never_published
            )
            if us is None:
                skipped += 1
                continue
            trigger = {"package": "policyengine-taxsim", "version": release["version"]}
            entry = pair(release, us, trigger, reference)
            if not certain:
                entry.pop("installAsOf", None)
                entry.update(
                    status="not-installable",
                    reason=(
                        "a policyengine-us release PyPI doesn't serve may have "
                        f"come out after {us['version']} and before this release; "
                        "which one a user got is unknown"
                    ),
                )
            entries.append(entry)
        if mode == "release" and not entries:
            raise ValueError(f"policyengine-taxsim {taxsim_version} is not on PyPI")
    if mode in ("backfill", "recent"):
        last = {}
        for release in us_all:
            if release["onPypi"] and not (since and release["hi"] < since):
                day = release["hi"].date()
                if day not in last or version_key(release["version"]) > version_key(
                    last[day]["version"]
                ):
                    last[day] = release
        for day, us in sorted(last.items()):
            taxsim, certain = newest_at(taxsim_all, us["hi"])
            if taxsim is None or not certain:
                skipped += 1
                continue
            if not us_allowed(requirement(taxsim["version"]), us_available)(
                us["version"]
            ):
                skipped += 1
                continue
            trigger = {"package": "policyengine-us", "version": us["version"]}
            entries.append(pair(taxsim, us, trigger, reference))
    if mode == "latest":
        taxsim = max(
            (r for r in taxsim_all if r["onPypi"]),
            key=lambda r: version_key(r["version"]),
        )
        allowed = us_allowed(requirement(taxsim["version"]), us_available)
        us = max(
            (r for r in us_all if allowed(r["version"])),
            key=lambda r: version_key(r["version"]),
        )
        newer = taxsim if taxsim["hi"] > us["hi"] else us
        package = "policyengine-taxsim" if newer is taxsim else "policyengine-us"
        entries.append(
            pair(
                taxsim, us, {"package": package, "version": newer["version"]}, reference
            )
        )
    if skipped:
        log(f"{skipped} releases had no installable counterpart and were skipped")
    merged = {}
    for entry in entries:
        if entry["id"] in merged:
            known = merged[entry["id"]]
            known["triggers"] += [
                t for t in entry["triggers"] if t not in known["triggers"]
            ]
        else:
            merged[entry["id"]] = entry
    recorded = {
        row["id"]
        for row in (history or {}).get("rows", [])
        if not retry_failed or row.get("status") in ("measured", "not-installable")
    }
    todo = [e for e in merged.values() if e["id"] not in recorded]
    measure = [e for e in todo if e.get("status") != "not-installable"]
    unavailable = [e for e in todo if e.get("status") == "not-installable"]
    measure.sort(key=lambda e: e["releasedAt"], reverse=True)
    if len(measure) > max_pairs:
        log(
            f"{len(measure) - max_pairs} older pairs left for a later run "
            f"(this run measures at most {max_pairs})"
        )
        measure = measure[:max_pairs]
    log(
        f"{len(merged)} pairs; {len(merged) - len(todo)} already recorded; "
        f"{len(measure)} to measure; {len(unavailable)} not installable"
    )
    return {"measure": measure, "unavailable": unavailable}


# ---------------------------------------------------------------- measure


def install(env, pairs_spec, as_of, log_path):
    """Create the pair's virtual environment; return (ok, log tail)."""
    commands = [
        ["uv", "venv", "--quiet", "--python", PYTHON, str(env)],
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(env / "bin" / "python"),
            *(["--exclude-newer", as_of] if as_of else []),
            *pairs_spec,
        ],
    ]
    with log_path.open("w") as log:
        for command in commands:
            log.write("$ " + " ".join(command) + "\n")
            log.flush()
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                break
    tail = log_path.read_text()[-3000:]
    return result.returncode == 0, tail


def select_households(limit):
    """All source households, or a smoke-test subset covering every state."""
    rows = list(source_rows())
    if not limit:
        return rows
    per_state = {}
    quota = math.ceil(limit / len(STATES))
    for row in rows:
        bucket = per_state.setdefault(row["state"], [])
        if len(bucket) < quota:
            bucket.append(row)
    picked = [
        bucket[i]
        for i in range(quota)
        for bucket in per_state.values()
        if i < len(bucket)
    ][:limit]
    order = {row["taxsimid"]: i for i, row in enumerate(rows)}
    return sorted(picked, key=lambda row: order[row["taxsimid"]])


def rss(process, psutil):
    if process is None:
        return 0
    try:
        return process.memory_info().rss + sum(
            child.memory_info().rss
            for child in process.children(recursive=True)
            if child.is_running()
        )
    except psutil.NoSuchProcess:
        return 0


def run_workers(
    python,
    batches,
    years,
    work,
    workers,
    max_memory_gb,
    timeout,
    total_memory_gb=None,
    log=print,
):
    """Run batches through the worker, at most `workers` at once.

    Each worker is stopped above max_memory_gb of RSS (with its children) or
    after `timeout` seconds; a stopped batch is retried once, split in two.
    If the workers together pass total_memory_gb, the newest is stopped and its
    batch requeued (not a failure), and one fewer worker runs from then on.
    Returns [(output, settings)] per completed batch, failures, and peak RSS.
    """
    import psutil
    import signal

    queue = [(i, batch, True) for i, batch in enumerate(batches)]
    running, done, failures, peak = [], [], [], 0
    counter = len(batches)
    while queue or running:
        while queue and len(running) < workers:
            index, batch, retry = queue.pop(0)
            stem = work / f"part-{index:05}"
            input_path = stem.with_suffix(".input.csv")
            with input_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, refresh.INPUT_COLUMNS)
                writer.writeheader()
                writer.writerows(batch)
            output = stem.with_suffix(".csv.gz")
            settings = stem.with_suffix(".json")
            child = subprocess.Popen(
                [
                    str(python),
                    "-I",
                    str(WORKER),
                    str(input_path),
                    str(output),
                    str(settings),
                    *map(str, years),
                ],
                cwd=work,
                start_new_session=True,
            )
            try:
                process = psutil.Process(child.pid)
            except psutil.NoSuchProcess:
                process = None
            running.append(
                dict(
                    child=child,
                    process=process,
                    started=time.monotonic(),
                    index=index,
                    batch=batch,
                    retry=retry,
                    input=input_path,
                    output=output,
                    settings=settings,
                )
            )
        time.sleep(2)
        total = sum(rss(job["process"], psutil) for job in running)
        if total_memory_gb and total > total_memory_gb * 1024**3 and len(running) > 1:
            job = max(running, key=lambda j: j["started"])
            os.killpg(job["child"].pid, signal.SIGKILL)
            job["child"].wait()
            running.remove(job)
            job["input"].unlink(missing_ok=True)
            queue.insert(0, (job["index"], job["batch"], job["retry"]))
            workers = max(1, len(running))
            log(
                f"Workers together passed {total_memory_gb} GiB; requeued batch "
                f"{job['index']} and continuing with {workers} at a time"
            )
        for job in list(running):
            child = job["child"]
            reason = None
            if child.poll() is None:
                used = rss(job["process"], psutil)
                peak = max(peak, used)
                if used > max_memory_gb * 1024**3:
                    reason = f"exceeded {max_memory_gb} GiB"
                elif time.monotonic() - job["started"] > timeout:
                    reason = f"exceeded {timeout} s"
                if reason is None:
                    continue
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            elif child.returncode != 0 or not job["settings"].exists():
                reason = f"exited {child.returncode}"
            running.remove(job)
            job["input"].unlink(missing_ok=True)
            if reason is None:
                done.append((job["index"], job["output"], job["settings"]))
                log(
                    f"Batch {job['index']}: {len(job['batch'])} households "
                    f"in {time.monotonic() - job['started']:.0f} s",
                )
            elif job["retry"] and len(job["batch"]) > 1:
                half = len(job["batch"]) // 2
                log(f"Batch {job['index']} {reason}; retrying in two halves")
                for part in (job["batch"][:half], job["batch"][half:]):
                    queue.insert(0, (counter, part, False))
                    counter += 1
            else:
                failures.append(
                    f"{len(job['batch'])} households (batch {job['index']}) {reason}"
                )
                log(f"Batch {job['index']} {reason}; giving up")
    done.sort()
    return [(output, settings) for _, output, settings in done], failures, peak


def measure(args):
    # Workers run inside the work directory, so every path must be absolute.
    work = args.work_dir.resolve()
    args.reference_dir = args.reference_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    reference_meta = json.loads((args.reference_dir / "reference.json").read_text())
    entry = json.loads(args.pair) if args.pair else {}
    taxsim_version = args.taxsim_version or entry["policyengineTaxsimVersion"]
    us_version = args.us_version or entry["policyengineUsVersion"]
    as_of = args.as_of if args.as_of is not None else entry.get("installAsOf")
    years = [int(y) for y in (args.years or reference_meta["years"])]
    row = {
        "id": row_id(taxsim_version, us_version, reference_meta["release"]),
        "policyengineTaxsimVersion": taxsim_version,
        "policyengineUsVersion": us_version,
        **{
            k: entry[k]
            for k in (
                "policyengineTaxsimReleasedAt",
                "policyengineUsReleasedAt",
                "releasedAt",
                "triggers",
            )
            if k in entry
        },
        "reference": reference_meta["release"],
        "installAsOf": as_of,
        "generatedAt": iso(now()),
        "run": run_url(),
    }
    if args.limit:
        row["limit"] = args.limit
    if args.taxsim_spec:
        row["taxsimSpec"] = args.taxsim_spec
    env = work / "env"
    if env.exists():
        shutil.rmtree(env)
    ok, tail = install(
        env,
        [
            args.taxsim_spec or f"policyengine-taxsim=={taxsim_version}",
            f"policyengine-us=={us_version}",
        ],
        as_of,
        work / "install.log",
    )
    if not ok:
        row.update(status="install-failed", reason=tail.strip().splitlines()[-1][:500])
        write_row(work, row)
        return row
    python = env / "bin" / "python"
    installed = json.loads(
        subprocess.run(
            [str(python), "-I", str(WORKER), "--versions"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    if not args.taxsim_spec and installed["policyengine-taxsim"] != taxsim_version:
        raise RuntimeError(f"Installed {installed}, expected taxsim {taxsim_version}")
    if installed["policyengine-us"] != us_version:
        raise RuntimeError(
            f"Installed {installed}, expected policyengine-us {us_version}"
        )
    households = select_households(args.limit)
    batches = [
        households[i : i + args.batch_size]
        for i in range(0, len(households), args.batch_size)
    ]
    started = time.monotonic()
    parts, failures, peak = run_workers(
        python,
        batches,
        years,
        work,
        args.workers,
        args.max_memory_gb,
        args.timeout,
        args.total_memory_gb,
    )
    settings = [json.loads(path.read_text()) for _, path in parts]
    first = settings[0] if settings else {}
    for other in settings[1:]:
        for key in ("versions", "applied", "unsupported", "scorpTreatment"):
            if other.get(key) != first.get(key):
                raise RuntimeError(f"Workers disagree on {key}")
    errors = {}
    for item in settings:
        for year, message in item.get("errors", {}).items():
            errors.setdefault(year, message)
    row.update(
        policyengineTaxsimVersion=first.get("versions", installed)[
            "policyengine-taxsim"
        ],
        policyengineCoreVersion=first.get("versions", installed).get(
            "policyengine-core"
        ),
        pythonVersion=first.get("pythonVersion"),
        settings={
            "assumeW2Wages": first.get("applied", {}).get("assume_w2_wages"),
            "disableSalt": first.get("applied", {}).get("disable_salt"),
            "scorpTreatment": first.get("scorpTreatment"),
            "policyengineOutputDetail": first.get("policyengineOutputDetail"),
            "unsupportedOptions": first.get("unsupported", []),
        },
        workerSeconds=round(time.monotonic() - started),
        peakWorkerRssMiB=round(peak / 1024**2),
    )
    if args.taxsim_spec:
        row["id"] = row_id(
            row["policyengineTaxsimVersion"] + "+local", us_version, row["reference"]
        )
    keep = {household_id(h) for h in households}
    row["years"] = {}
    for year in years:
        if failures:
            row["years"][str(year)] = {"status": "failed", "reason": failures[0]}
            continue
        if str(year) in errors:
            row["years"][str(year)] = {"status": "failed", "reason": errors[str(year)]}
            continue
        outputs = {}
        for output, _ in parts:
            with gzip.open(output, "rt", newline="") as stream:
                for record in csv.DictReader(stream):
                    if int(record["year"]) == year:
                        key = household_id(record)
                        if key in outputs:
                            raise ValueError(f"{year}: household {key} scored twice")
                        outputs[key] = {k: record[k] for k in OUTPUTS}
        reference = [
            r for r in read_reference(args.reference_dir, year) if r["taxsimid"] in keep
        ]
        tally = score(reference, outputs)
        out_path = work / f"policyengine_{year}.csv.gz"
        write_gzip_csv(
            out_path,
            ["taxsimid", *OUTPUTS],
            ({"taxsimid": key, **outputs[key]} for key in sorted(outputs, key=int)),
        )
        row["years"][str(year)] = {
            "status": "measured",
            **tally,
            "outputSha256": refresh.digest(out_path),
        }
    statuses = {y["status"] for y in row["years"].values()}
    row["status"] = (
        "measured"
        if statuses == {"measured"}
        else "failed"
        if "measured" not in statuses
        else "partial"
    )
    write_row(work, row)
    return row


def write_row(work, row):
    refresh.atomic_json(work / "row.json", row)
    printable = {k: v for k, v in row.items() if k != "years"}
    print(json.dumps(printable), flush=True)
    for year, entry in (row.get("years") or {}).items():
        if entry["status"] == "measured":
            fed, state = percentages(entry)[2:4]
            print(f"{year}: federal {fed}%, state {state}% within 1% of income")
        else:
            print(f"{year}: {entry['status']}: {entry['reason'][:300]}")


# ------------------------------------------------------------------ merge


def skeleton():
    return {
        "schemaVersion": SCHEMA_VERSION,
        "description": (
            "Agreement with TAXSIM by release. Each row scores one "
            "policyengine-taxsim / policyengine-us pair, installed as PyPI stood "
            "at its release, against the TAXSIM side of the published full-data "
            "release named by `reference`, on the same households and tolerances "
            "as the dashboard. Counts only; a rate is a count over `records`. "
            "Written by scripts/alignment_history.py."
        ),
        "states": list(STATES),
        "references": {},
        "rows": [],
    }


def validate_year(year, entry, where):
    problems = []
    status = entry.get("status")
    if status not in YEAR_STATUSES:
        return [f"{where} {year}: unknown status {status!r}"]
    if status == "failed":
        if not entry.get("reason"):
            problems.append(f"{where} {year}: failed without a reason")
        return problems
    n = entry.get("records")
    if not isinstance(n, int) or n <= 0:
        return [f"{where} {year}: records must be a positive integer"]
    by_state = entry.get("byState", {})
    households = by_state.get("households")
    if not isinstance(households, list) or len(households) != len(STATES):
        return [f"{where} {year}: byState.households must list {len(STATES)} states"]
    if any(not isinstance(h, int) or h < 0 for h in households):
        problems.append(f"{where} {year}: state household counts must be >= 0")
    if sum(households) != n:
        problems.append(
            f"{where} {year}: state households sum to {sum(households)}, not {n}"
        )
    for name in COUNTS:
        value = entry.get(name)
        if not isinstance(value, int) or not 0 <= value <= n:
            problems.append(f"{where} {year}: {name} must be an integer in [0, {n}]")
            continue
        column = by_state.get(name)
        if not isinstance(column, list) or len(column) != len(STATES):
            problems.append(f"{where} {year}: byState.{name} must list every state")
            continue
        if sum(column) != value:
            problems.append(
                f"{where} {year}: byState.{name} sums to {sum(column)}, not {value}"
            )
        if any(
            not isinstance(c, int) or not 0 <= c <= h
            for c, h in zip(column, households)
        ):
            problems.append(
                f"{where} {year}: byState.{name} exceeds a state's households"
            )
    return problems


def validate_row(row, references=None):
    where = row.get("id", "<row without id>")
    problems = []
    for key in (
        "id",
        "policyengineTaxsimVersion",
        "policyengineUsVersion",
        "reference",
    ):
        if not isinstance(row.get(key), str) or not row[key]:
            problems.append(f"{where}: missing {key}")
    if problems:
        return problems
    expected_id = row_id(
        row["policyengineTaxsimVersion"], row["policyengineUsVersion"], row["reference"]
    )
    if row["id"] != expected_id and not row.get("taxsimSpec"):
        problems.append(f"{where}: id should be {expected_id}")
    if references is not None and row["reference"] not in references:
        problems.append(f"{where}: unknown reference {row['reference']}")
    status = row.get("status")
    if status not in ROW_STATUSES:
        return problems + [f"{where}: unknown status {status!r}"]
    years = row.get("years") or {}
    if status in ("not-installable", "install-failed"):
        if years:
            problems.append(f"{where}: {status} rows have no years")
        if not row.get("reason"):
            problems.append(f"{where}: {status} without a reason")
        return problems
    if not years:
        return problems + [f"{where}: {status} rows need years"]
    statuses = set()
    for year, entry in years.items():
        if not re.fullmatch(r"\d{4}", year):
            problems.append(f"{where}: bad year {year!r}")
        problems += validate_year(year, entry, where)
        statuses.add(entry.get("status"))
    expected = (
        "measured"
        if statuses == {"measured"}
        else "failed"
        if "measured" not in statuses
        else "partial"
    )
    if status != expected:
        problems.append(f"{where}: status {status} but years say {expected}")
    if status != "failed":
        records = {e["records"] for e in years.values() if e["status"] == "measured"}
        if len(records) != 1:
            problems.append(f"{where}: measured years cover different households")
    return problems


def validate_history(doc):
    problems = []
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        problems.append("schemaVersion")
    if doc.get("states") != list(STATES):
        problems.append("states must list the TAXSIM state order")
    references = doc.get("references", {})
    ids = set()
    for row in doc.get("rows", []):
        problems += validate_row(row, references)
        if row.get("id") in ids:
            problems.append(f"{row.get('id')}: duplicate row")
        ids.add(row.get("id"))
        reference = references.get(row.get("reference"), {})
        for year, entry in (row.get("years") or {}).items():
            ref_year = reference.get("years", {}).get(year)
            if entry.get("status") != "measured" or ref_year is None:
                continue
            if not row.get("limit") and entry["records"] != ref_year["records"]:
                problems.append(f"{row['id']} {year}: not the reference population")
    order = [
        r.get("releasedAt") or r.get("generatedAt") or "" for r in doc.get("rows", [])
    ]
    if order != sorted(order):
        problems.append("rows must be sorted by releasedAt")
    return problems


def sort_key(row):
    return (
        row.get("releasedAt") or row.get("generatedAt") or "",
        version_key(row["policyengineTaxsimVersion"].split("+")[0]),
        version_key(row["policyengineUsVersion"]),
    )


def merge(doc, rows, references=(), replace=False):
    """Add rows (and their references) to a history; return (doc, added ids)."""
    doc = json.loads(json.dumps(doc)) if doc else skeleton()
    for meta in references:
        known = doc["references"].get(meta["release"])
        if known is None:
            doc["references"][meta["release"]] = meta
        elif reference_identity(known) != reference_identity(meta):
            raise ValueError(
                f"Reference {meta['release']} differs from the recorded one"
            )
    existing = {row["id"]: i for i, row in enumerate(doc["rows"])}
    added = []
    for row in rows:
        problems = validate_row(row, doc["references"])
        if problems:
            raise ValueError("; ".join(problems))
        if row.get("limit") or row.get("taxsimSpec"):
            raise ValueError(f"{row['id']}: smoke-test rows are not recorded")
        if row["id"] in existing:
            old = doc["rows"][existing[row["id"]]]
            # A measurement replaces an earlier "not installable" or failed
            # attempt; otherwise the first measurement stands.
            if replace or (old["status"] != "measured" and row["status"] == "measured"):
                doc["rows"][existing[row["id"]]] = row
                added.append(row["id"])
            continue
        existing[row["id"]] = len(doc["rows"])
        doc["rows"].append(row)
        added.append(row["id"])
    doc["rows"].sort(key=sort_key)
    problems = validate_history(doc)
    if problems:
        raise ValueError("; ".join(problems[:20]))
    return doc, added


def reference_identity(meta):
    """What makes two extractions of a release the same reference."""
    return (
        meta["release"],
        meta.get("sourceSha256"),
        {
            year: (
                entry["records"],
                entry["comparisonSha256"],
                entry["referenceSha256"],
            )
            for year, entry in meta["years"].items()
        },
    )


def load_history(path=HISTORY):
    return json.loads(path.read_text()) if path.exists() else skeleton()


def write_history(doc, path=HISTORY):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
    tmp.replace(path)


# -------------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="list pairs to measure")
    p.add_argument(
        "--mode", choices=["recent", "backfill", "latest", "release"], required=True
    )
    p.add_argument("--since-days", type=int, default=7, help="mode recent")
    p.add_argument("--max-pairs", type=int, default=MAX_PAIRS, help="newest first")
    p.add_argument("--taxsim-version", help="the release to measure (mode release)")
    p.add_argument("--us-repo", type=Path, help="policyengine-us clone for exact times")
    p.add_argument("--us-ref", default="HEAD", help="its branch holding every release")
    p.add_argument("--reference", help="release tag (default: the dashboard's)")
    p.add_argument("--history", type=Path, default=HISTORY)
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--output", type=Path, required=True)

    r = sub.add_parser("reference", help="extract the TAXSIM reference")
    r.add_argument("--reference", help="release tag (default: the dashboard's)")
    r.add_argument("--work-dir", type=Path, required=True)
    r.add_argument("--years", type=int, nargs="*", default=list(YEARS))

    m = sub.add_parser("measure", help="score one pair")
    m.add_argument("--pair", help="one entry of a plan's `measure` list, as JSON")
    m.add_argument("--taxsim-version")
    m.add_argument("--us-version")
    m.add_argument("--taxsim-spec", help="install this instead (smoke tests only)")
    m.add_argument("--as-of", help="resolve other packages as PyPI stood then")
    m.add_argument("--reference-dir", type=Path, required=True)
    m.add_argument("--work-dir", type=Path, required=True)
    m.add_argument("--years", type=int, nargs="*")
    # Defaults fit a GitHub-hosted runner (4 CPUs, 16 GB): importing
    # policyengine-us costs ~3 GB per worker, so batches are large.
    m.add_argument("--batch-size", type=int, default=5000)
    m.add_argument("--workers", type=int, default=3)
    m.add_argument("--max-memory-gb", type=float, default=6)
    m.add_argument("--total-memory-gb", type=float, default=13)
    m.add_argument("--timeout", type=int, default=3600, help="seconds per batch")
    m.add_argument("--limit", type=int, default=0, help="smoke test: households")

    g = sub.add_parser("merge", help="add rows to the history")
    g.add_argument("rows", type=Path, nargs="*", help="row.json files or folders")
    g.add_argument("--plan", type=Path, help="record a plan's not-installable rows")
    g.add_argument("--reference-meta", type=Path, action="append", default=[])
    g.add_argument("--history", type=Path, default=HISTORY)
    g.add_argument("--replace", action="store_true")
    g.add_argument("--check", action="store_true", help="only validate the history")

    args = parser.parse_args(argv)
    if args.command == "plan":
        result = plan(
            args.mode,
            args.reference or reference_tag(),
            load_history(args.history),
            args.taxsim_version,
            args.us_repo,
            args.retry_failed,
            args.us_ref,
            args.since_days,
            min(args.max_pairs, MAX_PAIRS),
        )
        args.output.write_text(json.dumps(result, indent=1) + "\n")
        matrix = [
            {"id": e["id"], "pair": json.dumps(e, separators=(",", ":"))}
            for e in result["measure"]
        ]
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as out:
                out.write(f"matrix={json.dumps({'include': matrix})}\n")
                out.write(f"count={len(matrix)}\n")
                out.write(f"unavailable={len(result['unavailable'])}\n")
    elif args.command == "reference":
        build_reference(args.reference or reference_tag(), args.work_dir, args.years)
    elif args.command == "measure":
        if not (args.pair or (args.taxsim_version and args.us_version)):
            parser.error("give --pair, or --taxsim-version and --us-version")
        measure(args)
    elif args.command == "merge":
        doc = load_history(args.history)
        if args.check:
            problems = validate_history(doc)
            if problems:
                sys.exit("\n".join(problems))
            print(f"{args.history.name}: {len(doc['rows'])} rows valid")
            return
        rows = []
        for path in args.rows:
            files = sorted(path.rglob("row.json")) if path.is_dir() else [path]
            rows += [json.loads(f.read_text()) for f in files]
        if args.plan:
            rows += json.loads(args.plan.read_text())["unavailable"]
        references = [json.loads(p.read_text()) for p in args.reference_meta]
        doc, added = merge(doc, rows, references, args.replace)
        write_history(doc, args.history)
        print(f"{len(added)} rows added; {len(doc['rows'])} in {args.history.name}")


if __name__ == "__main__":
    main()
