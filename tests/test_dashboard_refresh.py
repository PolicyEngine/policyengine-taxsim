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
