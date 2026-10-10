"""Alignment history: scoring, release timing, the history file's invariants.

No PolicyEngine import or simulation; the worker test uses a stand-in runner.
"""

import copy
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "alignment_history", ROOT / "scripts/alignment_history.py"
)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
refresh = history.refresh
STATES = history.STATES

# ------------------------------------------------------------------ data

amount = st.one_of(
    st.just(0.0),
    st.integers(min_value=-5_000, max_value=400_000).map(float),
    st.floats(min_value=-5_000, max_value=400_000, allow_nan=False, width=32).map(
        lambda x: round(float(x), 2)
    ),
)
# Differences that sit on and around both tolerances ($15 and 1% of income).
nudge = st.sampled_from([0, 0.01, 14.99, 15, 15.01, -15, 100, -2500, 0.5])


@st.composite
def household(draw, taxsimid):
    row = {
        "taxsimid": str(taxsimid),
        "state_code": draw(st.sampled_from(STATES)),
        **{name: draw(amount) for name in history.GROSS_FIELDS},
        "fiitax": draw(amount),
        "siitax": draw(amount),
        "srebate": draw(st.sampled_from([0.0, 0.0, 250.0, 500.0])),
    }
    gross = sum(
        max(refresh.number(row[k]), 0)
        if k in ("stcg", "ltcg")
        else refresh.number(row[k])
        for k in history.GROSS_FIELDS
        if k != "gssi"
    ) + 0.85 * refresh.number(row["gssi"])
    edge = draw(st.sampled_from([0, 0.01 * gross, -0.01 * gross]))
    pe = {
        "fiitax": row["fiitax"] + draw(nudge) + draw(st.sampled_from([0, edge])),
        "siitax": row["siitax"] + draw(nudge),
        "srebate": draw(st.sampled_from([row["srebate"], 0.0])),
    }
    return row, pe


@st.composite
def population(draw, max_size=40):
    n = draw(st.integers(min_value=1, max_value=max_size))
    pairs = [draw(household(i + 1)) for i in range(n)]
    reference = [taxsim for taxsim, _ in pairs]
    outputs = {taxsim["taxsimid"]: pe for taxsim, pe in pairs}
    return reference, outputs


def measured_row(reference, outputs, taxsim="3.1.1", us="2.36.0", ref="rel", year=2023):
    tally = history.score(reference, outputs)
    return {
        "id": history.row_id(taxsim, us, ref),
        "policyengineTaxsimVersion": taxsim,
        "policyengineUsVersion": us,
        "reference": ref,
        "releasedAt": "2026-10-09T12:13:00Z",
        "installAsOf": "2026-10-09T12:14:00Z",
        "triggers": [{"package": "policyengine-taxsim", "version": taxsim}],
        "status": "measured",
        "years": {str(year): {"status": "measured", **tally, "outputSha256": "x"}},
    }


def reference_meta(release, records):
    return {
        "release": release,
        "sourceSha256": "s",
        "years": {
            "2023": {
                "records": records,
                "comparisonSha256": "c",
                "referenceSha256": "r",
            }
        },
    }


# ------------------------------------------------------- scoring invariants


@settings(max_examples=150, deadline=None)
@given(population())
def test_counts_reconcile_and_rates_are_bounded(data):
    reference, outputs = data
    tally = history.score(reference, outputs)
    assert history.validate_year("2023", {"status": "measured", **tally}, "row") == []
    assert tally["records"] == len(reference)
    assert sum(tally["byState"]["households"]) == len(reference)
    for name in history.COUNTS:
        assert 0 <= tally[name] <= tally["records"]
        assert sum(tally["byState"][name]) == tally[name]
        for count, n in zip(tally["byState"][name], tally["byState"]["households"]):
            assert 0 <= count <= n
    for rate in history.percentages(tally):
        assert 0 <= rate <= 100


@settings(max_examples=100, deadline=None)
@given(population(), st.randoms(use_true_random=False))
def test_score_ignores_household_order(data, rng):
    reference, outputs = data
    shuffled = reference[:]
    rng.shuffle(shuffled)
    assert history.score(shuffled, outputs) == history.score(reference, outputs)


@settings(max_examples=100, deadline=None)
@given(population(max_size=25))
def test_score_agrees_with_dashboard_summarize(tmp_path_factory, data):
    """Differential: the history and the dashboard refresh tally identically."""
    reference, outputs = data
    folder = tmp_path_factory.mktemp("summarize")
    part = folder / "part.csv.gz"
    fields = [*history.REFERENCE_FIELDS, "source"]
    with gzip.open(part, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for taxsim in reference:
            writer.writerow({**taxsim, "source": "taxsim"})
            writer.writerow(
                {**taxsim, **outputs[taxsim["taxsimid"]], "source": "policyengine"}
            )
    refresh.summarize([part], folder / "out", 2023, {}, set())
    summary = json.loads((folder / "out/site/2023/summary_2023.json").read_text())
    tally = history.score(reference, outputs)
    problems = history.summary_check(tally, summary)
    assert problems == []


def test_score_rejects_missing_extra_or_repeated_households():
    row = {
        "taxsimid": "1",
        "state_code": "IL",
        "pwages": 1000,
        "fiitax": 0,
        "siitax": 0,
        "srebate": 0,
    }
    pe = {"fiitax": 0, "siitax": 0, "srebate": 0}
    assert history.score([row], {"1": pe})["records"] == 1
    with pytest.raises(ValueError, match="No PolicyEngine output"):
        history.score([row], {})
    with pytest.raises(ValueError, match="no reference row"):
        history.score([row], {"1": pe, "2": pe})
    with pytest.raises(ValueError, match="twice"):
        history.score([row, row], {"1": pe})
    with pytest.raises(ValueError, match="valid state"):
        history.score([{**row, "state_code": "XX"}], {"1": pe})


def test_percentages_round_like_the_dashboard():
    tally = {
        "records": 111347,
        **dict(zip(history.COUNTS, [90304, 93310, 99990, 105667, 106776])),
    }
    assert history.percentages(tally) == [
        round(100 * n / 111347, 1) for n in tally.values() if n != 111347
    ]


# ----------------------------------------------------------- the history


@settings(max_examples=60, deadline=None)
@given(
    population(max_size=15), population(max_size=15), st.randoms(use_true_random=False)
)
def test_merge_is_idempotent_and_order_free(a, b, rng):
    n = len(a[0])
    rows = [
        measured_row(*a, taxsim="3.1.0", us="2.34.1"),
        measured_row(a[0], a[1], taxsim="3.1.1", us="2.36.0"),
        {
            "id": history.row_id("2.10.0", "1.587.1", "rel"),
            "policyengineTaxsimVersion": "2.10.0",
            "policyengineUsVersion": "1.587.1",
            "reference": "rel",
            "releasedAt": "2026-02-26T02:16:00Z",
            "triggers": [{"package": "policyengine-taxsim", "version": "2.10.0"}],
            "status": "not-installable",
            "reason": "policyengine-us 1.587.1 is not on PyPI",
        },
    ]
    rows[1]["releasedAt"] = "2026-10-09T12:14:00Z"
    refs = [reference_meta("rel", n)]
    once, added = history.merge(None, rows, refs)
    assert len(added) == 3
    assert history.validate_history(once) == []
    twice, again = history.merge(once, rows, refs)
    assert twice == once and again == []
    shuffled = rows[:]
    rng.shuffle(shuffled)
    assert history.merge(None, shuffled, refs)[0] == once
    # A different population for the same reference is refused.
    if len(b[0]) != n:
        with pytest.raises(ValueError, match="reference population"):
            history.merge(once, [measured_row(*b, taxsim="3.2.0", us="2.40.0")], refs)


ONE = [
    {"taxsimid": "1", "state_code": "IL", "pwages": 1000, "fiitax": 0, "siitax": 0,
     "srebate": 0}
]  # fmt: skip
AGREE = {"1": {"fiitax": 0, "siitax": 0, "srebate": 0}}
DIFFER = {"1": {"fiitax": 99, "siitax": 0, "srebate": 0}}


def with_years(row, **statuses):
    """The row with one year per keyword: y2023="measured" or "failed"."""
    measured = row["years"]["2023"]
    years = {
        name[1:]: measured
        if status == "measured"
        else {"status": "failed", "reason": "x"}
        for name, status in statuses.items()
    }
    found = set(statuses.values())
    status = (
        "measured"
        if found == {"measured"}
        else "partial"
        if "measured" in found
        else "failed"
    )
    return {**row, "years": years, "status": status}


def references_for(*years):
    meta = reference_meta("rel", 1)
    meta["years"] = {str(y): dict(meta["years"]["2023"]) for y in years}
    return [meta]


def test_a_row_is_replaced_only_by_one_that_measured_more_years():
    refs = references_for(2023, 2024)
    good = measured_row(ONE, AGREE)
    worse = measured_row(ONE, DIFFER)
    failed_install = {k: v for k, v in good.items() if k not in ("years", "status")} | {
        "status": "install-failed",
        "reason": "resolution failed",
    }
    doc, _ = history.merge(None, [failed_install], refs)
    # A retry that measures one year of two replaces the failed attempt...
    partial = with_years(good, y2023="measured", y2024="failed")
    doc, changed = history.merge(doc, [partial], refs)
    assert changed == [good["id"]] and doc["rows"][0]["status"] == "partial"
    # ...a failed retry does not replace the partial row...
    doc2, changed = history.merge(
        doc, [with_years(good, y2023="failed", y2024="failed")], refs
    )
    assert changed == [] and doc2 == doc
    # ...a full measurement does...
    full = with_years(good, y2023="measured", y2024="measured")
    doc, changed = history.merge(doc, [full], refs)
    assert changed == [good["id"]] and doc["rows"][0]["status"] == "measured"
    # ...and a later, different measurement of the same pair does not.
    doc3, changed = history.merge(
        doc, [with_years(worse, y2023="measured", y2024="measured")], refs
    )
    assert changed == [] and doc3 == doc
    doc4, _ = history.merge(doc, [worse], refs, replace=True)
    assert doc4["rows"][0]["years"]["2023"]["federalMatchesRel"] == 0


def test_a_recorded_pair_gains_the_triggers_of_a_later_plan():
    refs = [reference_meta("rel", 1)]
    row = measured_row(ONE, AGREE)
    doc, _ = history.merge(None, [row], refs)
    again = {**row, "triggers": [{"package": "policyengine-us", "version": "2.36.0"}]}
    doc, changed = history.merge(doc, [again], refs)
    assert changed == [row["id"]]
    assert [t["package"] for t in doc["rows"][0]["triggers"]] == [
        "policyengine-taxsim",
        "policyengine-us",
    ]


def test_better_evidence_re_pairs_a_release_recorded_as_not_installable():
    refs = [reference_meta("rel", 1)]
    trigger = [{"package": "policyengine-taxsim", "version": "3.1.1"}]
    gone = {
        "id": history.row_id("3.1.1", "2.36.1", "rel"),
        "policyengineTaxsimVersion": "3.1.1",
        "policyengineUsVersion": "2.36.1",
        "reference": "rel",
        "releasedAt": "2026-10-09T12:13:00Z",
        "triggers": trigger,
        "status": "not-installable",
        "reason": "policyengine-us 2.36.1 is not on PyPI",
    }
    doc, _ = history.merge(None, [gone], refs)
    measured = measured_row(ONE, AGREE)  # taxsim 3.1.1 with policyengine-us 2.36.0
    doc, changed = history.merge(doc, [measured], refs)
    assert [r["id"] for r in doc["rows"]] == [measured["id"]]
    assert set(changed) == {measured["id"], gone["id"]}
    # A not-installable row whose release nothing else claims stays.
    other = {
        **gone,
        "triggers": [{"package": "policyengine-taxsim", "version": "2.10.0"}],
    }
    doc, _ = history.merge(None, [other], refs)
    doc, _ = history.merge(doc, [measured], refs)
    assert len(doc["rows"]) == 2


def test_only_planned_full_population_rows_for_known_years_are_recorded():
    refs = [reference_meta("rel", 1)]
    row = measured_row(ONE, AGREE)
    with pytest.raises(ValueError, match="smoke"):
        history.merge(None, [{**row, "limit": 100}], refs)
    with pytest.raises(ValueError, match="smoke"):
        history.merge(None, [{**row, "taxsimSpec": "."}], refs)
    with pytest.raises(ValueError, match="installAsOf"):
        history.merge(
            None, [{k: v for k, v in row.items() if k != "installAsOf"}], refs
        )
    with pytest.raises(ValueError, match="needs the release"):
        history.merge(None, [{**row, "triggers": []}], refs)
    with pytest.raises(ValueError, match="the reference has no 2024"):
        history.merge(None, [with_years(row, y2024="measured")], refs)
    # The committed file is held to the same rules as an incoming row.
    doc, _ = history.merge(None, [row], refs)
    doc["rows"][0]["limit"] = 1
    assert any("smoke" in p for p in history.validate_history(doc))
    changed = reference_meta("rel", 1)
    changed["years"]["2023"]["comparisonSha256"] = "other"
    with pytest.raises(ValueError, match="differs"):
        history.merge(history.merge(None, [row], refs)[0], [], [changed])


SOURCE_ROW = {name: "0" for name in refresh.INPUT_COLUMNS} | {
    "taxsimid": "7", "year": "2021", "state": "14", "mstat": "1", "depx": "0",
    "pwages": "41904.76190476191", "age1": "", "age2": "",
}  # fmt: skip


def test_the_reference_must_be_the_source_household_in_the_requested_year():
    published = {**SOURCE_ROW, "year": "2023", "state_code": "IL", "taxsimid": "7.0",
                 "pwages": "41904.7619047619", "age1": "nan"}  # fmt: skip
    history.check_published_household(published, SOURCE_ROW, 2023)
    for change, message in [
        ({"year": "2022"}, "was run for 2022"),
        ({"mstat": "2"}, "mstat"),
        ({"depx": "10"}, "depx"),
        ({"pwages": "41905.76"}, "pwages"),
        ({"age1": "12"}, "age1"),
        ({"state_code": "TX"}, "state differs"),
    ]:
        with pytest.raises(ValueError, match=message):
            history.check_published_household({**published, **change}, SOURCE_ROW, 2023)


def test_measure_refuses_a_reference_that_was_not_the_one_verified(tmp_path):
    rows = [{name: "0" for name in history.REFERENCE_FIELDS}]
    history.write_gzip_csv(
        tmp_path / "reference_2023.csv.gz", history.REFERENCE_FIELDS, rows
    )
    meta = {
        "sourceSha256": refresh.digest(refresh.SOURCE),
        "years": {
            "2023": {
                "referenceSha256": refresh.digest(tmp_path / "reference_2023.csv.gz")
            }
        },
    }
    history.check_reference(meta, tmp_path)
    with pytest.raises(ValueError, match="not the source"):
        history.check_reference({**meta, "sourceSha256": "other"}, tmp_path)
    history.write_gzip_csv(
        tmp_path / "reference_2023.csv.gz", history.REFERENCE_FIELDS, rows * 2
    )
    with pytest.raises(ValueError, match="not the verified 2023 reference"):
        history.check_reference(meta, tmp_path)


CORRUPTIONS = [
    lambda y: y.__setitem__("federalMatchesRel", y["records"] + 1),
    lambda y: y.__setitem__("stateMatches", -1),
    lambda y: y["byState"]["households"].__setitem__(
        0, y["byState"]["households"][0] + 1
    ),
    lambda y: y["byState"]["stateMatchesRel"].append(0),
    lambda y: y["byState"]["federalMatches"].__setitem__(
        0, y["byState"]["households"][0] + 1
    ),
    lambda y: y.__setitem__("records", 0),
    lambda y: y.__setitem__("status", "maybe"),
]


@settings(max_examples=80, deadline=None)
@given(population(max_size=20), st.sampled_from(range(len(CORRUPTIONS))))
def test_validation_catches_counts_that_do_not_reconcile(data, which):
    row = measured_row(*data)
    assert history.validate_row(row) == []
    broken = copy.deepcopy(row)
    CORRUPTIONS[which](broken["years"]["2023"])
    assert history.validate_row(broken) != []


def test_validation_checks_ids_statuses_and_order():
    row = measured_row(ONE, AGREE)
    assert history.validate_row(row) == []
    assert any("id should be" in p for p in history.validate_row({**row, "id": "x"}))
    assert history.validate_row({**row, "status": "partial"}) != []
    doc = history.skeleton()
    doc["references"]["rel"] = reference_meta("rel", 1)
    late = {
        **row,
        "releasedAt": "2026-10-10T00:00:00Z",
        "id": history.row_id("3.2", "2.4", "rel"),
        "policyengineTaxsimVersion": "3.2",
        "policyengineUsVersion": "2.4",
    }
    doc["rows"] = [late, row]
    assert "rows must be sorted by releasedAt" in history.validate_history(doc)
    doc["rows"] = [row, late]
    assert history.validate_history(doc) == []


def test_committed_history_is_valid():
    if not history.HISTORY.exists():
        pytest.skip("no alignment history committed yet")
    doc = json.loads(history.HISTORY.read_text())
    assert history.validate_history(doc) == []


# -------------------------------------------------------- release timing

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


@st.composite
def release_history(draw):
    """A true release history, and what can be observed of it afterwards.

    Versions are bumped in order. Each bump either publishes some minutes
    later (uploads keep version order) or never publishes. Published releases
    may since have been deleted from PyPI. For a release PyPI lacks, the
    publish job is on record (and tells the truth) or it is not.
    """
    n = draw(st.integers(min_value=1, max_value=25))
    moment, last_upload, releases = T0, T0, []
    for i in range(n):
        # Bumps come in version order; a bump may precede the previous upload.
        moment += timedelta(minutes=draw(st.integers(min_value=1, max_value=60 * 30)))
        bumped = moment
        published = draw(st.booleans()) or i == 0
        upload = job = None
        if published:
            start = bumped + timedelta(minutes=draw(st.integers(0, 20)))
            # Uploads keep version order: the one assumption the windows rest on.
            upload = max(
                start + timedelta(minutes=draw(st.integers(0, 90))),
                last_upload + timedelta(minutes=1),
            )
            job = (start, upload + timedelta(minutes=draw(st.integers(0, 10))))
            last_upload = upload
        releases.append(
            dict(
                version=f"2.{i}.0",
                bumped=bumped,
                upload=upload,
                job=job,
                deleted=published and draw(st.booleans()),
                on_record=draw(st.booleans()),
                has_commit=draw(st.booleans()),
            )
        )
    return releases


def observe(truth):
    available = {
        r["version"]: {
            "available": r["upload"],
            "complete": r["upload"],
            "requiresPython": None,
        }
        for r in truth
        if r["upload"] and not r["deleted"]
    }
    dated = {
        r["version"]: datetime(
            r["bumped"].year, r["bumped"].month, r["bumped"].day, tzinfo=timezone.utc
        )
        for r in truth
    }
    bumps = {
        r["version"]: (r["bumped"], r["version"]) for r in truth if r["has_commit"]
    }
    by_version = {r["version"]: r for r in truth}

    def evidence(release):
        r = by_version[release["version"]]
        if not release["commit"] or not r["on_record"]:
            return ("unknown", None, None)
        return ("published", *r["job"]) if r["upload"] else ("never", None, None)

    end = max(r["upload"] or r["bumped"] for r in truth) + timedelta(days=2)
    return history.timeline(available, dated, bumps, end), evidence


@settings(max_examples=400, deadline=None)
@given(release_history(), st.integers(min_value=0, max_value=60 * 24 * 40))
def test_publish_windows_hold_the_true_time_and_certain_answers_are_right(
    truth, offset
):
    releases, evidence = observe(truth)
    uploads = {r["version"]: r["upload"] for r in truth if r["upload"]}
    for release in releases:
        if release["version"] in uploads:
            assert release["lo"] <= uploads[release["version"]] <= release["hi"]
    moment = T0 + timedelta(minutes=offset)
    best, certain = history.newest_installed(releases, moment, evidence=evidence)
    # Evidence only ever narrows a window around the truth.
    for release in releases:
        if release["version"] in uploads and release.get("state") != "never":
            assert release["lo"] <= uploads[release["version"]] <= release["hi"]
        assert not (release.get("state") == "never" and release["version"] in uploads)
    out = [v for v, t in uploads.items() if t <= moment]
    true_newest = max(out, key=history.version_key) if out else None
    if certain:
        assert (best or {}).get("version") == true_newest
    # With no evidence at all, a certain answer is still never wrong.
    plain, _ = observe(truth)
    best, certain = history.newest_at(plain, moment)
    if certain:
        assert (best or {}).get("version") == true_newest


def test_a_release_that_never_published_is_not_what_a_user_got():
    t = T0
    releases = [
        {"version": "2.6.17", "lo": t, "hi": t, "onPypi": True, "commit": None},
        {"version": "2.6.20", "lo": t + timedelta(hours=1), "hi": t + timedelta(days=1),
         "onPypi": False, "commit": "abc"},
    ]  # fmt: skip
    later = t + timedelta(hours=2)
    never = lambda r: ("never", None, None)  # noqa: E731
    best, certain = history.newest_installed(
        [dict(r) for r in releases], later, evidence=never
    )
    assert (best["version"], certain) == ("2.6.17", True)
    # No evidence: it may or may not have been out, so the answer is open.
    best, certain = history.newest_installed([dict(r) for r in releases], later)
    assert (best["version"], certain) == ("2.6.17", False)
    # Published 01:20-01:30, then deleted: it is what a user got, for certain.
    job = (t + timedelta(minutes=80), t + timedelta(minutes=90))
    best, certain = history.newest_installed(
        [dict(r) for r in releases], later, evidence=lambda r: ("published", *job)
    )
    assert (best["version"], certain) == ("2.6.20", True)


def test_a_bump_commit_is_not_the_moment_of_publication():
    """Bumped 00:10, uploaded 00:20: at 00:15 the older release was newest."""
    t = T0
    available = {
        "2.0.0": {"available": t, "complete": t, "requiresPython": None},
        "2.0.2": {"available": t + timedelta(hours=5), "complete": t, "requiresPython": None},
    }  # fmt: skip
    dated = {"2.0.0": T0, "2.0.1": T0, "2.0.2": T0}
    bumps = {"2.0.1": (t + timedelta(minutes=10), "sha")}
    releases = history.timeline(available, dated, bumps)
    best, certain = history.newest_at(releases, t + timedelta(minutes=15))
    assert (best["version"], certain) == ("2.0.0", False)
    job = (t + timedelta(minutes=12), t + timedelta(minutes=21))
    best, certain = history.newest_installed(
        history.timeline(available, dated, bumps),
        t + timedelta(minutes=30),
        evidence=lambda r: ("published", *job),
    )
    assert (best["version"], certain) == ("2.0.1", True)


def test_a_release_is_available_from_its_first_file(monkeypatch):
    listing = {
        "releases": {
            "2.0.1": [
                {"upload_time": "2026-09-01T01:00:00", "requires_python": ">=3.11"},
                {"upload_time": "2026-09-01T03:00:00", "requires_python": ">=3.11"},
            ],
            "2.0.2": [{"upload_time": "2026-09-02T00:00:00", "yanked": True}],
        }
    }
    monkeypatch.setattr(history, "fetch", lambda url: json.dumps(listing).encode())
    releases = history.pypi_releases("policyengine-us")
    assert list(releases) == ["2.0.1"]
    assert releases["2.0.1"]["available"].hour == 1
    assert releases["2.0.1"]["complete"].hour == 3


def test_pair_reasons_and_install_moment():
    t = T0
    taxsim = {"version": "3.1.1", "lo": t, "hi": t, "onPypi": True,
              "complete": t + timedelta(minutes=3)}  # fmt: skip
    earlier = t - timedelta(hours=1)
    us = {"version": "2.36.0", "lo": earlier, "hi": earlier, "onPypi": True,
          "complete": earlier}  # fmt: skip
    trigger = {"package": "policyengine-taxsim", "version": "3.1.1"}
    entry = history.pair(taxsim, us, trigger, "rel")
    assert entry["releasedAt"] == history.iso(t)
    assert entry["installAsOf"] == history.iso(
        t + timedelta(minutes=3) + history.INSTALL_GRACE
    )
    assert "status" not in entry
    gone = history.pair(taxsim, {**us, "onPypi": False}, trigger, "rel")
    assert gone["status"] == "not-installable" and "installAsOf" not in gone
    assert gone["reason"] == "policyengine-us 2.36.0 is not on PyPI"


def test_changelog_dates_and_reference_tag():
    text = "## [3.1.1] - 2026-10-09\n\n## [0.2.0] - 2025-07-29 14:27:02\n"
    dates = history.changelog_dates(text)
    assert dates["0.2.0"].date().isoformat() == "2025-07-29"
    assert history.reference_tag().startswith("full-ecps-comparison")


# ----------------------------------------------------------- files, worker


def test_gzip_csv_bytes_depend_only_on_rows(tmp_path):
    rows = [{"a": 1, "b": 2.5}, {"a": 3, "b": -1}]
    shas = []
    for name in ("one.csv.gz", "two.csv.gz"):
        history.write_gzip_csv(tmp_path / name, ["a", "b"], rows)
        shas.append(hashlib.sha256((tmp_path / name).read_bytes()).hexdigest())
    assert shas[0] == shas[1]
    with gzip.open(tmp_path / "one.csv.gz", "rt") as stream:
        assert stream.read().splitlines() == ["a,b", "1,2.5", "3,-1"]


def test_smoke_selection_covers_every_state():
    rows = history.select_households(102)
    assert len(rows) == 102
    assert {int(r["state"]) for r in rows} == set(range(1, 52))


FAKE_RUNNER = textwrap.dedent(
    """
    import pandas as pd

    class PolicyEngineRunner:
        def __init__(self, input_df, logs=False, disable_salt=False):
            self.df = input_df

        def run(self, show_progress=True):
            if int(self.df.year.iloc[0]) == 2022:
                raise RuntimeError("no 2022 rules")
            return pd.DataFrame(
                {"taxsimid": self.df.taxsimid, "fiitax": self.df.pwages * 0.1,
                 "siitax": 0.0, "srebate": 0.0}
            )
    """
)


def test_worker_passes_only_supported_options_and_records_failed_years(tmp_path):
    pytest.importorskip("pandas")
    package = tmp_path / "fake" / "policyengine_taxsim" / "runners"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("")
    (package / "__init__.py").write_text(FAKE_RUNNER)
    batch = tmp_path / "in.csv"
    batch.write_text("taxsimid,year,state,pwages\n1,2021,14,1000\n2,2021,14,2000\n")
    out, settings_path = tmp_path / "out.csv.gz", tmp_path / "settings.json"
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "fake")}
    script = ROOT / "scripts/alignment_worker.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            str(batch),
            str(out),
            str(settings_path),
            "2021",
            "2022",
        ],
        check=True,
        env=env,
        cwd=tmp_path,
    )
    result = json.loads(settings_path.read_text())
    assert result["applied"] == {"logs": False, "disable_salt": False}
    assert result["unsupported"] == ["assume_w2_wages"]
    assert result["scorpTreatment"] is None
    assert (
        list(result["errors"]) == ["2022"]
        and "no 2022 rules" in result["errors"]["2022"]
    )
    with gzip.open(out, "rt", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [(r["taxsimid"], r["year"], float(r["fiitax"])) for r in rows] == [
        ("1", "2021", 100.0),
        ("2", "2021", 200.0),
    ]


# ------------------------------------------------------- worker scheduling

# Stands in for alignment_worker.py: fails 2022 the way a release without
# 2022 rules would, crashes on household 13 unless it is alone in its batch
# or the batch is small, and always crashes on household 99.
STUB_WORKER = textwrap.dedent(
    """
    import csv, gzip, json, sys
    input_path, output_path, settings_path, year = sys.argv[-4:]
    rows = list(csv.DictReader(open(input_path)))
    ids = [r["taxsimid"] for r in rows]
    if "99" in ids or ("13" in ids and len(ids) > 2):
        sys.exit(3)
    errors = {year: "RuntimeError: no 2022 rules"} if year == "2022" else {}
    with gzip.open(output_path, "wt", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["taxsimid", "year", "fiitax", "siitax", "srebate"])
        if not errors:
            writer.writerows([i, year, 1, 2, 0] for i in ids)
    json.dump(
        {"versions": {"policyengine-taxsim": "9.9.9"}, "applied": {}, "unsupported": [],
         "scorpTreatment": None, "errors": errors},
        open(settings_path, "w"),
    )
    """
)


@pytest.fixture
def stub_worker(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("workers use POSIX process groups")
    pytest.importorskip("psutil")
    script = tmp_path / "stub_worker.py"
    script.write_text(STUB_WORKER)
    monkeypatch.setattr(history, "WORKER", script)
    monkeypatch.setattr(history, "POLL_SECONDS", 0.05)
    work = tmp_path / "work"
    work.mkdir()

    def run(ids, years, batch_size=4, workers=3):
        households = [{"taxsimid": str(i), "state": 14} for i in ids]
        batches = [
            households[i : i + batch_size]
            for i in range(0, len(households), batch_size)
        ]
        return history.run_workers(
            sys.executable, batches, years, work, workers, 6, 60, log=lambda *_: None
        )

    return run


def scored_ids(paths):
    ids = []
    for path in paths:
        with gzip.open(path, "rt", newline="") as stream:
            ids += [row["taxsimid"] for row in csv.DictReader(stream)]
    return ids


def test_every_batch_and_year_runs_once(stub_worker):
    done, errors, settings, _ = stub_worker(range(1, 11), [2021, 2023])
    assert errors == {}
    assert settings["versions"] == {"policyengine-taxsim": "9.9.9"}
    for year in (2021, 2023):
        assert sorted(scored_ids(done[year]), key=int) == [str(i) for i in range(1, 11)]


def test_a_year_the_release_cannot_compute_is_reported_and_skipped(stub_worker):
    done, errors, _, _ = stub_worker(range(1, 11), [2021, 2022], workers=1)
    assert list(errors) == [2022] and "no 2022 rules" in errors[2022]
    assert done[2022] == []
    assert sorted(scored_ids(done[2021]), key=int) == [str(i) for i in range(1, 11)]


def test_a_stopped_batch_is_retried_in_halves_without_losing_households(stub_worker):
    # Household 13 crashes a batch of four; each half of two then succeeds.
    done, errors, _, _ = stub_worker(range(10, 18), [2021])
    assert errors == {}
    assert sorted(scored_ids(done[2021]), key=int) == [str(i) for i in range(10, 18)]


def test_a_worker_that_keeps_crashing_fails_the_measurement(stub_worker):
    with pytest.raises(history.WorkerFailure, match="worker exited 3"):
        stub_worker(range(96, 104), [2021])


def test_a_crashed_worker_leaves_no_child_process_behind(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("workers use POSIX process groups")
    psutil = pytest.importorskip("psutil")
    script = tmp_path / "leaky_worker.py"
    script.write_text(
        textwrap.dedent(
            """
            import subprocess, sys
            child = subprocess.Popen(["sleep", "60"])
            open(sys.argv[-2] + ".child", "w").write(str(child.pid))
            sys.exit(3)
            """
        )
    )
    monkeypatch.setattr(history, "WORKER", script)
    monkeypatch.setattr(history, "POLL_SECONDS", 0.05)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(history.WorkerFailure):
        history.run_workers(
            sys.executable,
            [[{"taxsimid": "1", "state": 14}]],
            [2021],
            work,
            1,
            6,
            60,
            log=lambda *_: None,
        )
    (pid_file,) = work.glob("*.child")
    pid = int(pid_file.read_text())
    gone = not psutil.pid_exists(pid) or psutil.Process(pid).status() == "zombie"
    assert gone, "the crashed worker's child is still running"


def test_workers_over_the_total_memory_budget_are_requeued_not_failed(
    stub_worker, monkeypatch
):
    # Every worker reports 2 GiB; with a 3 GiB total budget only one can run.
    messages = []
    monkeypatch.setattr(history, "rss", lambda process, psutil: 2 * 1024**3)
    households = [{"taxsimid": str(i), "state": 14} for i in range(1, 13)]
    batches = [households[i : i + 2] for i in range(0, 12, 2)]
    work = next(iter(history.WORKER.parent.glob("work")))
    done, errors, _, peak = history.run_workers(
        sys.executable, batches, [2021], work, 3, 6, 60, 3, log=messages.append
    )
    assert errors == {} and peak == 2 * 1024**3
    assert sorted(scored_ids(done[2021]), key=int) == [str(i) for i in range(1, 13)]
    assert any("continuing with 1 at a time" in m for m in messages)
