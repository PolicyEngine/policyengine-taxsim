"""Lightweight tests: no PolicyEngine import or simulation on the host."""

import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "refresh_dashboard", Path(__file__).parents[1] / "scripts/refresh_dashboard.py"
)
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class RefreshTests(unittest.TestCase):
    def test_relative_and_net_of_rebates(self):
        ts = {"pwages": 10000, "fiitax": 100, "siitax": -200, "srebate": 200}
        pe = {"fiitax": 199, "siitax": 0, "srebate": 0}
        self.assertEqual(refresh.match_flags(ts, pe), [False, False, True, False, True])
        pe["fiitax"] = 200
        self.assertFalse(refresh.match_flags(ts, pe)[2])

    def test_zero_income_uses_absolute_tolerance(self):
        row = {"fiitax": 0, "siitax": 0, "srebate": 0}
        self.assertEqual(refresh.match_flags(row, row), [True] * 5)
        with self.assertRaises(ValueError):
            refresh.match_flags(row, {**row, "fiitax": "nan"})

    def test_streamed_summary_pairs_and_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            part = base / "part.csv.gz"
            rows = [
                dict(
                    taxsimid=i,
                    source=source,
                    state_code="IL",
                    pwages=10000,
                    fiitax=100,
                    siitax=0,
                    srebate=0,
                )
                for i in (1, 2)
                for source in ("taxsim", "policyengine")
            ]
            with gzip.open(part, "wt", newline="") as stream:
                writer = csv.DictWriter(stream, rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(
                refresh.summarize([part], base / "output", 2021, {}, {"2"}), 2
            )
            summary = json.loads(
                (base / "output/site/2021/summary_2021.json").read_text()
            )
            self.assertEqual(summary["sampleRecords"], 1)
            self.assertEqual(summary["stateMatchPctRelNet"], 100)
            with self.assertRaises(ValueError):
                refresh.summarize([part, part], base / "bad", 2021, {}, {"2"})


class SourceTests(unittest.TestCase):
    def write_source(self, folder, states):
        path = Path(folder) / "source.csv"
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, refresh.INPUT_COLUMNS)
            writer.writeheader()
            for i, state in enumerate(states, 1):
                writer.writerow({"taxsimid": i, "year": 2021, "state": state})
        return path

    def test_checked_in_source_has_every_state(self):
        self.assertEqual(refresh.check_source(refresh.SOURCE), refresh.EXPECTED_RECORDS)

    def test_state_zero_is_rejected(self):
        # TAXSIM reads state 0 as "no state tax"; Alabama was once coded 0.
        with tempfile.TemporaryDirectory() as folder:
            states = [0, *range(2, 52)]
            with self.assertRaisesRegex(ValueError, r"codes: '0' \(taxsimid 1\)$"):
                refresh.check_source(self.write_source(folder, states))

    def test_non_integer_or_blank_state_is_rejected(self):
        # TAXSIM stops at a non-integer code; a blank one would be state 0.
        for bad in ("1.5", "", "nan", "52"):
            with tempfile.TemporaryDirectory() as folder:
                states = [*range(1, 52), bad]
                with self.assertRaisesRegex(ValueError, "taxsimid 52"):
                    refresh.check_source(self.write_source(folder, states))

    def test_missing_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "no households in AL$"):
                refresh.check_source(self.write_source(folder, range(2, 52)))
            path = self.write_source(folder, range(1, 52))
            self.assertEqual(refresh.check_source(path), 51)

    def test_summary_rejects_rows_without_a_state(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            part = base / "part.csv.gz"
            rows = [
                dict(taxsimid=1, source=source, state_code="", fiitax=0, siitax=0)
                for source in ("taxsim", "policyengine")
            ]
            with gzip.open(part, "wt", newline="") as stream:
                writer = csv.DictWriter(stream, rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "no valid state"):
                refresh.summarize([part], base / "output", 2021, {}, set())


class DatasetTests(unittest.TestCase):
    def test_every_dataset_source_is_complete(self):
        for name, spec in refresh.DATASETS.items():
            with self.subTest(dataset=name):
                self.assertEqual(refresh.check_source(spec["source"]), spec["records"])

    def test_populace_metadata_records_the_certified_build(self):
        meta = refresh.dataset_metadata("populace")
        self.assertEqual(meta["buildId"], "populace-us-2024-spm-20260915")
        self.assertEqual(meta["hfRevision"], "populace-us-2024-spm-20260915")
        self.assertEqual(
            meta["h5Sha256"],
            "6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84",
        )
        self.assertEqual(meta["conversionModel"]["policyengine-us"], "2.2.1")
        self.assertEqual(meta["sourceSha256"], refresh.digest(meta_source("populace")))

    def test_stale_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            stale = Path(folder) / "stale.json"
            stale.write_text(json.dumps({"outputSha256": "0" * 64, "records": 1}))
            spec = {**refresh.DATASETS["populace"], "provenance": stale}
            with patch.dict(refresh.DATASETS, {"populace": spec}):
                with self.assertRaisesRegex(ValueError, "does not describe"):
                    refresh.dataset_metadata("populace")

    def test_drilldown_sample_is_deterministic_and_covers_every_state(self):
        source = refresh.DATASETS["populace"]["source"]
        sample = refresh.drilldown_sample(source)
        self.assertEqual(sample, refresh.drilldown_sample(source))
        self.assertTrue(3000 <= len(sample) <= 3000 + 51 * refresh.SAMPLE_STATE_MINIMUM)
        with source.open(newline="") as f:
            states = {
                int(float(row["state"]))
                for row in csv.DictReader(f)
                if str(int(float(row["taxsimid"]))) in sample
            }
        self.assertEqual(states, set(range(1, 52)))

    def test_release_notes_label_rates_and_disclose_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            meta = {
                "dataset": refresh.dataset_metadata("populace"),
                "emulatorCommit": "abc123",
                "policyengineUsVersion": "2.6.17",
                "policyengineCoreVersion": "3.32.6",
                "taxsimBinarySha256": "f" * 64,
                "taxsimtestBuild": "cd2026081819",
                "assumeW2Wages": True,
                "disableSalt": False,
                "generatedAt": "2026-09-24T00:00:00+00:00",
                "limit": 0,
                "records": refresh.DATASETS["populace"]["records"],
            }
            for year, rate in ((2024, 90.0), (2025, 91.5)):
                rates = dict.fromkeys(refresh.RATE_KEYS, rate)
                (Path(folder) / f"provenance_{year}.json").write_text(
                    json.dumps({**meta, "year": year, "rates": rates})
                )
            notes = refresh.release_notes(folder, "https://example.org/run")
            self.assertIn(refresh.COMPARISON_NOTE, notes)
            self.assertIn("populace-us-2024-spm-20260915", notes)
            self.assertIn(
                "6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84",
                notes,
            )
            self.assertIn("| 2025 | 91.5% | 91.5% | 91.5% | 91.5% | 91.5% |", notes)
            self.assertIn("79,729", notes)
            self.assertEqual(
                refresh.release_title(folder),
                "TAXSIM comparison: Populace US 2024, 2026-09-24",
            )
            (Path(folder) / "provenance_2023.json").write_text(
                json.dumps({**meta, "year": 2023, "emulatorCommit": "other"})
            )
            with self.assertRaisesRegex(ValueError, "disagree on emulatorCommit"):
                refresh.release_notes(folder)

    def test_release_notes_reject_smoke_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            smoke = {
                "dataset": refresh.dataset_metadata("populace"),
                "year": 2023,
                "limit": 100,
                "records": 100,
            }
            (Path(folder) / "provenance_2023.json").write_text(json.dumps(smoke))
            with self.assertRaisesRegex(ValueError, "release full runs only"):
                refresh.release_notes(folder)


def meta_source(name):
    return refresh.DATASETS[name]["source"]


class ResourceLimitTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Refresh workers use POSIX process groups")
    def test_memory_limit_terminates_worker_group(self):
        child = Mock(pid=123, returncode=None)
        child.poll.return_value = None
        process = Mock()
        process.memory_info.return_value = SimpleNamespace(rss=6 * 1024**3)
        process.children.return_value = []
        psutil = SimpleNamespace(
            Process=lambda pid: process, NoSuchProcess=ProcessLookupError
        )
        with (
            patch.dict("sys.modules", {"psutil": psutil}),
            patch.object(refresh.subprocess, "Popen", return_value=child),
            patch.object(refresh.os, "killpg") as kill,
        ):
            with self.assertRaisesRegex(RuntimeError, "memory budget"):
                refresh.run_bounded(Path("input.csv"), Path("output.csv.gz"), 5, 4)
            kill.assert_called_once()
            child.wait.assert_called_once()

    def test_missing_drilldown_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            part = base / "part.csv.gz"
            rows = [
                dict(
                    taxsimid=1,
                    source=source,
                    state_code="IL",
                    pwages=10000,
                    fiitax=100,
                    siitax=0,
                    srebate=0,
                )
                for source in ("taxsim", "policyengine")
            ]
            with gzip.open(part, "wt", newline="") as stream:
                writer = csv.DictWriter(stream, rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "sample"):
                refresh.summarize([part], base / "output", 2021, {"limit": 0}, {"2"})
