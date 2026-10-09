"""Lightweight tests: no PolicyEngine import or simulation on the host."""

import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

try:
    from hypothesis import given, strategies as st
except ImportError:  # the refresh environment runs these tests without it
    given = None

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/refresh_dashboard.py"
spec = importlib.util.spec_from_file_location("refresh_dashboard", SCRIPT)
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


# The provenance keys before policyengineTaxsimVersion and taxsimBinaryBuild.
EXISTING_RUN_KEYS = [
    "generatedAt",
    "policyengineUsVersion",
    "policyengineCoreVersion",
    "spmCalculatorVersion",
    "peakWorkerRssMiB",
    "assumeW2Wages",
    "disableSalt",
    "policyengineOutputDetail",
    "taxsimBinarySha256",
]
IDENTITY = {"source": "cps_households.csv", "year": 2023, "limit": 0}
PACKAGE_VERSIONS = {
    "policyengine-us": "2.35.2",
    "policyengine-core": "3.32.29",
    "spm-calculator": "0.4.1",
}


def fake_versions(name):
    return PACKAGE_VERSIONS[name]


class RunMetadataTests(unittest.TestCase):
    def metadata(self, versions):
        with patch.object(refresh.importlib.metadata, "version", fake_versions):
            return refresh.run_metadata(IDENTITY, versions, 812)

    def check(self, versions):
        metadata = self.metadata(versions)
        self.assertEqual(
            sorted(metadata),
            sorted(
                [*IDENTITY, *EXISTING_RUN_KEYS]
                + ["policyengineTaxsimVersion", "taxsimBinaryBuild"]
            ),
        )
        self.assertEqual({k: metadata[k] for k in IDENTITY}, IDENTITY)
        # The keys written before are unchanged.
        self.assertEqual(metadata["policyengineUsVersion"], "2.35.2")
        self.assertEqual(metadata["policyengineCoreVersion"], "3.32.29")
        self.assertEqual(metadata["spmCalculatorVersion"], "0.4.1")
        self.assertEqual(metadata["peakWorkerRssMiB"], 812)
        self.assertEqual(
            [metadata[k] for k in ["assumeW2Wages", "disableSalt"]], [True, False]
        )
        self.assertEqual(metadata["policyengineOutputDetail"], 5)
        self.assertEqual(
            metadata["taxsimBinarySha256"], refresh.digest(refresh.TAXSIM_BINARY)
        )
        # The new keys come from collect_versions().
        self.assertEqual(
            metadata["policyengineTaxsimVersion"],
            versions["policyengineTaxsimVersion"],
        )
        self.assertEqual(metadata["taxsimBinaryBuild"], versions["taxsimBinaryBuild"])

    def test_adds_emulator_version_and_taxsim_build(self):
        self.check(
            {
                "policyengineTaxsimVersion": "3.1.0",
                "taxsimBinaryBuild": "cd2026081819",
                "taxsimBinarySha256": refresh.digest(refresh.TAXSIM_BINARY),
            }
        )

    def test_failed_child_stops_the_refresh(self):
        with tempfile.TemporaryDirectory() as work:
            with patch.object(
                refresh.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, "refresh"),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    refresh.emulator_versions(work)

    def test_unreadable_build_is_null(self):
        metadata = self.metadata(
            {"policyengineTaxsimVersion": "3.1.0", "taxsimBinaryBuild": None}
        )
        self.assertIsNone(metadata["taxsimBinaryBuild"])
        self.assertIsNone(json.loads(json.dumps(metadata))["taxsimBinaryBuild"])

    if given is not None:

        @given(
            version=st.one_of(st.none(), st.text(max_size=20)),
            build=st.one_of(st.none(), st.from_regex(r"cd\d{10}", fullmatch=True)),
        )
        def test_any_versions_leave_existing_keys_unchanged(self, version, build):
            self.check(
                {"policyengineTaxsimVersion": version, "taxsimBinaryBuild": build}
            )


def read_version():
    text = (ROOT / "policyengine_taxsim/__init__.py").read_text()
    return re.search(r'^__version__ = "([^"]+)"', text, re.M).group(1)


def load_provenance_module():
    # Loaded from its file: importing the package would import PolicyEngine.
    spec = importlib.util.spec_from_file_location(
        "provenance_under_test", ROOT / "policyengine_taxsim/core/provenance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(
    importlib.util.find_spec("policyengine_us") is None,
    "needs policyengine-us for the child process",
)
class EmulatorVersionsTests(unittest.TestCase):
    def test_child_reports_checkout_and_linux_binary_without_parent_import(self):
        # A fresh coordinator process, so the import check sees only its own
        # modules.
        program = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("refresh_dashboard", sys.argv[1])
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)
versions = refresh.emulator_versions(sys.argv[2])
loaded = sorted(m for m in sys.modules if m.split(".")[0].startswith("policyengine"))
print(json.dumps({"versions": versions, "loaded": loaded}))
"""
        with tempfile.TemporaryDirectory() as work:
            result = subprocess.run(
                [sys.executable, "-c", program, str(SCRIPT), work],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(os.listdir(work), [])
        report = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(report["loaded"], [])
        versions = report["versions"]
        self.assertEqual(versions["policyengineTaxsimVersion"], read_version())
        self.assertEqual(versions["taxsimBinary"], "taxsimtest-linux.exe")
        self.assertEqual(
            versions["taxsimBinaryBuild"],
            load_provenance_module().read_binary_build(refresh.TAXSIM_BINARY),
        )
        self.assertRegex(versions["taxsimBinaryBuild"], r"^cd\d{10}$")
        # Two implementations of the binary's hash agree.
        self.assertEqual(
            versions["taxsimBinarySha256"], refresh.digest(refresh.TAXSIM_BINARY)
        )
