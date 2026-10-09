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


def test_a_measurement_replaces_an_unavailable_row_but_not_another_measurement(
    tmp_path,
):
    reference = [
        {
            "taxsimid": "1",
            "state_code": "IL",
            "pwages": 1000,
            "fiitax": 0,
            "siitax": 0,
            "srebate": 0,
        }
    ]
    good = measured_row(reference, {"1": {"fiitax": 0, "siitax": 0, "srebate": 0}})
    worse = measured_row(reference, {"1": {"fiitax": 99, "siitax": 0, "srebate": 0}})
    unavailable = {
        k: good[k]
        for k in (
            "id",
            "policyengineTaxsimVersion",
            "policyengineUsVersion",
            "reference",
            "releasedAt",
        )
    }
    unavailable.update(status="install-failed", reason="resolution failed")
    refs = [reference_meta("rel", 1)]
    doc, _ = history.merge(None, [unavailable], refs)
    doc, added = history.merge(doc, [good], refs)
    assert added == [good["id"]] and doc["rows"][0]["status"] == "measured"
    doc2, added = history.merge(doc, [worse], refs)
    assert added == [] and doc2 == doc
    doc3, _ = history.merge(doc, [worse], refs, replace=True)
    assert doc3["rows"][0] == worse


def test_smoke_rows_and_changed_references_are_refused():
    reference = [
        {
            "taxsimid": "1",
            "state_code": "IL",
            "pwages": 1000,
            "fiitax": 0,
            "siitax": 0,
            "srebate": 0,
        }
    ]
    row = measured_row(reference, {"1": {"fiitax": 0, "siitax": 0, "srebate": 0}})
    refs = [reference_meta("rel", 1)]
    with pytest.raises(ValueError, match="smoke"):
        history.merge(None, [{**row, "limit": 100}], refs)
    doc, _ = history.merge(None, [row], refs)
    changed = reference_meta("rel", 1)
    changed["years"]["2023"]["comparisonSha256"] = "other"
    with pytest.raises(ValueError, match="differs"):
        history.merge(doc, [], [changed])


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
    reference = [
        {
            "taxsimid": "1",
            "state_code": "IL",
            "pwages": 1000,
            "fiitax": 0,
            "siitax": 0,
            "srebate": 0,
        }
    ]
    row = measured_row(reference, {"1": {"fiitax": 0, "siitax": 0, "srebate": 0}})
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


def test_committed_history_is_valid():
    if not history.HISTORY.exists():
        pytest.skip("no alignment history committed yet")
    doc = json.loads(history.HISTORY.read_text())
    assert history.validate_history(doc) == []


# -------------------------------------------------------- release timing

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


@st.composite
def release_history(draw):
    """True publish times, increasing with version; some releases later lost."""
    n = draw(st.integers(min_value=1, max_value=30))
    gaps = draw(
        st.lists(st.integers(min_value=1, max_value=60 * 30), min_size=n, max_size=n)
    )
    times, moment = [], T0
    for gap in gaps:
        moment += timedelta(minutes=gap)
        times.append(moment)
    versions = [f"2.{i}.0" for i in range(n)]
    lost = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    exact = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    return versions, times, lost, exact


def build(versions, times, lost, exact):
    available = {
        v: {"uploaded": t, "requiresPython": None}
        for v, t, gone in zip(versions, times, lost)
        if not gone
    }
    dated = {
        v: datetime(t.year, t.month, t.day, tzinfo=timezone.utc)
        for v, t in zip(versions, times)
    }
    precise = {
        v: t for v, t, gone, ex in zip(versions, times, lost, exact) if gone and ex
    }
    return history.timeline(available, dated, precise)


@settings(max_examples=300, deadline=None)
@given(release_history(), st.integers(min_value=-60, max_value=60 * 24 * 40))
def test_publish_windows_hold_the_true_time_and_certain_answers_are_right(data, offset):
    versions, times, lost, exact = data
    releases = build(versions, times, lost, exact)
    truth = dict(zip(versions, times))
    if not all(lost):
        newest_listed = max(
            (v for v, g in zip(versions, lost) if not g), key=history.version_key
        )
    for release in releases:
        assert release["lo"] <= truth[release["version"]] <= release["hi"]
    # Unpublished entries newer than everything on PyPI are left out.
    if not all(lost):
        assert {r["version"] for r in releases} == {
            v
            for v in versions
            if history.version_key(v) <= history.version_key(newest_listed)
        }
    moment = T0 + timedelta(minutes=offset)
    best, certain = history.newest_at(releases, moment)
    candidates = [r["version"] for r in releases if truth[r["version"]] <= moment]
    true_newest = max(candidates, key=history.version_key) if candidates else None
    if certain:
        assert (best or {}).get("version") == true_newest


def test_newest_installed_skips_releases_that_never_published():
    t = T0
    releases = [
        {"version": "2.6.17", "lo": t, "hi": t, "onPypi": True, "commit": None},
        {
            "version": "2.6.20",
            "lo": t + timedelta(hours=1),
            "hi": t + timedelta(hours=1),
            "onPypi": False,
            "commit": "abc",
        },
    ]
    later = t + timedelta(hours=2)
    best, certain = history.newest_installed(
        releases, later, lambda v: True, lambda r: True
    )
    assert (best["version"], certain) == ("2.6.17", True)
    best, _ = history.newest_installed(releases, later, lambda v: True, lambda r: False)
    assert best["version"] == "2.6.20"


def test_pair_reasons_and_install_moment():
    t = T0
    taxsim = {"version": "3.1.1", "lo": t, "hi": t, "onPypi": True}
    us = {
        "version": "2.36.0",
        "lo": t - timedelta(hours=1),
        "hi": t - timedelta(hours=1),
        "onPypi": True,
    }
    entry = history.pair(
        taxsim, us, {"package": "policyengine-taxsim", "version": "3.1.1"}, "rel"
    )
    assert entry["installAsOf"] == history.iso(t + history.INSTALL_GRACE)
    assert "status" not in entry
    gone = history.pair({**taxsim, "onPypi": False}, {**us, "onPypi": False}, {}, "rel")
    assert gone["status"] == "not-installable"
    assert gone["reason"] == (
        "policyengine-taxsim 3.1.1 and policyengine-us 2.36.0 are not on PyPI"
    )


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
