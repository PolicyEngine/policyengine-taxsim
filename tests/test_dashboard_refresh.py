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

    def test_precomputed_taxsim_takes_the_batch_rows(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "taxsim_2023.csv.gz"
            pd.DataFrame(
                {
                    "taxsimid": [1.0, 2.0, 3.0],
                    "fiitax": [10, 20, 30],
                    "siitax": [1, 2, 3],
                    "srebate": [0, 0, 0],
                }
            ).to_csv(path, index=False, compression="gzip")
            ts = refresh.precomputed_taxsim(path, pd.DataFrame({"taxsimid": [3, 1]}))
            self.assertEqual(sorted(ts.taxsimid), [1.0, 3.0])
            self.assertEqual(
                ts.set_index("taxsimid").fiitax.to_dict(), {1.0: 10, 3.0: 30}
            )
            # A record the outputs do not cover stops the batch.
            with self.assertRaises(ValueError):
                refresh.precomputed_taxsim(path, pd.DataFrame({"taxsimid": [1, 4]}))

    def test_taxsim_outputs_must_match_the_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "taxsim_2023.csv.gz"
            path.write_bytes(gzip.compress(b"taxsimid\n1\n"))
            identity = {
                "source": "cps_households.csv",
                "sourceSha256": "abc",
                "year": 2023,
                "limit": 0,
            }
            provenance = {**identity, "outputSha256": refresh.digest(path)}
            path.with_name("taxsim_2023.json").write_text(json.dumps(provenance))
            self.assertEqual(
                refresh.taxsim_outputs_provenance(path, identity), provenance
            )
            for key, value in (("year", 2024), ("sourceSha256", "x"), ("limit", 100)):
                with self.assertRaises(ValueError):
                    refresh.taxsim_outputs_provenance(path, {**identity, key: value})
            # Outputs changed after their provenance was written.
            path.write_bytes(gzip.compress(b"taxsimid\n2\n"))
            with self.assertRaises(ValueError):
                refresh.taxsim_outputs_provenance(path, identity)

    def test_crash_search_names_each_failing_record(self):
        import pandas as pd

        def fake_taxsim(data):
            if data.taxsimid.isin([3, 7]).any():
                raise RuntimeError("TAXSIM execution failed: SIGFPE")
            return data, "build", Path("taxsim")

        data = pd.DataFrame({"taxsimid": range(1, 9), "state": 14})
        with patch.object(refresh, "taxsim_results", fake_taxsim):
            crashes = refresh.find_taxsim_crashes(data)
        self.assertEqual([row["taxsimid"] for row, _ in crashes], [3, 7])
        self.assertIn("SIGFPE", crashes[0][1])

    def test_a_batch_that_fails_once_is_never_dropped(self):
        import pandas as pd

        calls = []

        def flaky_taxsim(data):
            calls.append(len(data))
            if len(calls) == 1:
                raise RuntimeError("TAXSIM execution failed: SIGFPE")
            return data.assign(fiitax=0, siitax=0, srebate=0), "build", Path(__file__)

        rows = [dict(taxsimid=i, year=2023, state=14) for i in (1, 2)]
        args = SimpleNamespace(year=2023, limit=2, batch_size=5000)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            with (
                patch.object(refresh, "taxsim_results", flaky_taxsim),
                patch.object(refresh, "source_rows", lambda *_: iter(rows)),
            ):
                with self.assertRaises(SystemExit):
                    refresh.write_taxsim_outputs(Path("x"), out, args, {})
            report = json.loads((out / "taxsim_2023_crashes.json").read_text())
            self.assertEqual(report["records"], [])
            self.assertEqual(report["batchesThatFailedOnce"][0]["records"], 2)
            self.assertFalse((out / "taxsim_2023.csv.gz").exists())

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
