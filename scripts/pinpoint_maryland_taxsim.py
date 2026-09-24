"""Inspect the native Maryland crash without importing the emulator or model."""

import csv
import io
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "maryland-diagnostic"
NEW = ROOT / "resources/taxsimtest/taxsimtest-linux.exe"


def encode(rows):
    s = io.StringIO()
    w = csv.DictWriter(s, rows[0].keys())
    w.writeheader()
    w.writerows(rows)
    return s.getvalue()


def run(rows, binary=NEW):
    p = subprocess.run(
        [str(binary)],
        input=encode(rows),
        text=True,
        capture_output=True,
        timeout=10,
        cwd=OUT,
    )
    return {"returncode": p.returncode, "stderr": p.stderr, "stdout": p.stdout}


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    OUT.mkdir(exist_ok=True)
    evidence = {}
    for year in (2024, 2025):
        with (ROOT / f"tests/fixtures/maryland_taxsim_crash/{year}.csv").open() as f:
            original = list(csv.DictReader(f))
        rows = [dict(r) for r in original]
        assert run(rows)["returncode"] == -8
        cases = {
            "original": rows,
            "reversed": rows[::-1],
            "DE_only": rows[:1],
            "MD_only": rows[1:],
            "MD_twice": [rows[1], rows[1]],
        }
        results = {name: run(value) for name, value in cases.items()}
        results["old_binary"] = run(rows, Path(os.environ["TAXSIM_MD_FALLBACK_BINARY"]))
        # Zero financial inputs cumulatively, retaining only inputs needed for failure.
        preserve = {
            "taxsimid",
            "year",
            "state",
            "mstat",
            "page",
            "sage",
            "depx",
            "idtl",
            "opt1",
            "opt1v",
        }
        for index in range(2):
            for key in rows[index]:
                if key in preserve or key.startswith("age"):
                    continue
                candidate = [dict(r) for r in rows]
                candidate[index][key] = "0"
                if run(candidate)["returncode"] == -8:
                    rows = candidate
        fixture = OUT / f"financial-minimal-{year}.csv"
        fixture.write_text(encode(rows))
        results["financial_minimal"] = rows
        results["preceding_states"] = {}
        for state in range(52):
            candidate = [dict(r) for r in rows]
            candidate[0]["state"] = str(state)
            results["preceding_states"][state] = run(candidate)["returncode"]
        results["single_field_changes"] = {}
        for index in range(2):
            for field, values in [
                ("page", [30, 64, 65, 68]),
                ("sage", [0, 30, 63, 65, 68]),
                ("mstat", [1, 2]),
                ("depx", [0, 1, 2]),
            ]:
                for value in values:
                    candidate = [dict(r) for r in rows]
                    candidate[index][field] = str(value)
                    results["single_field_changes"][f"{index}:{field}={value}"] = run(
                        candidate
                    )["returncode"]
        if shutil.which("gdb"):
            commands = [
                "set pagination off",
                "set print elements 30",
                f"run < {fixture}",
                "bt",
                "x/12i $pc-24",
                "info registers",
                "info locals",
                "info args",
                "p $_siginfo",
                "p subh",
                "p subw",
                "p subt",
                "p subs",
                "set variable subh=subt",
                "set variable subw=subs",
                "continue",
                "bt",
            ]
            cmd = ["gdb", "--batch", "--quiet"]
            for command in commands:
                cmd += ["-ex", command]
            cmd += ["--args", str(NEW)]
            debug = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60, cwd=OUT
            )
            (OUT / f"gdb-{year}.txt").write_text(debug.stdout + "\n" + debug.stderr)
        evidence[year] = results
    (OUT / "pinpoint.json").write_text(json.dumps(evidence, indent=2))
    print(
        "Saved minimized inputs, controlled input variations, and native debugger evidence."
    )


if __name__ == "__main__":
    main()
