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
            with self.assertRaisesRegex(
                ValueError, r"invalid TAXSIM state codes \[0\]"
            ):
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


class MarylandFallbackTests(unittest.TestCase):
    def test_fallback_is_restricted_to_affected_state_and_years(self):
        for state in range(1, 52):
            for year in range(2021, 2027):
                self.assertEqual(
                    refresh.uses_state_fallback(state, year),
                    state in (11, 21) and year in (2024, 2025),
                )

    def test_fallback_rejects_unverified_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "wrong-binary"
            binary.write_text("wrong")
            with patch.dict(os.environ, {"TAXSIM_MD_FALLBACK_BINARY": str(binary)}):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    refresh.maryland_fallback_path()

    def test_fallback_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(refresh.maryland_fallback_path())
