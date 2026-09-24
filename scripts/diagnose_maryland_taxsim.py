"""Bounded, dependency-free reproducer for the September Linux MD crash."""

import ast
import csv
import io
import json
import math
import os
from pathlib import Path
import resource
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "maryland-diagnostic"


def encode(rows, year):
    # Mirror the runner's emitted columns/defaults without importing PE/pandas.
    tree = ast.parse(
        (ROOT / "policyengine_taxsim/runners/taxsim_runner.py").read_text()
    )
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TaxsimRunner"
    )
    columns = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in cls.body
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.List)
    }
    formatted = []
    fields = []
    for raw in rows:
        names = (
            columns["REQUIRED_COLUMNS"]
            + [f"age{i}" for i in range(1, min(int(float(raw["depx"])), 10) + 1)]
            + columns["INCOME_COLUMNS"]
            + columns["OPTION_COLUMNS"]
        )
        row = {}
        for key in names:
            value = float(raw.get(key) or 0)
            if key.startswith("age") and key[3:].isdigit() and value <= 0:
                value = 10
            row[key] = value
            if key not in fields:
                fields.append(key)
        row["year"] = year
        formatted.append(row)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fields, restval="0")
    writer.writeheader()
    writer.writerows(formatted)
    return stream.getvalue()


def run(binary, rows, year):
    return subprocess.run(
        [str(binary)],
        input=encode(rows, year),
        text=True,
        capture_output=True,
        timeout=30,
        cwd=OUT,
    )


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    OUT.mkdir(exist_ok=True)
    with (ROOT / "cps_households.csv").open() as stream:
        all_rows = list(csv.DictReader(stream))
        rows = [r for r in all_rows if int(r["state"]) == 21]
    old = Path(os.environ["TAXSIM_MD_FALLBACK_BINARY"])
    new = ROOT / "resources/taxsimtest/taxsimtest-linux.exe"
    evidence = []
    for year in (2024, 2025):
        previous = run(old, rows, year)
        assert previous.returncode == 0, previous.stderr
        lines = previous.stdout.splitlines()
        header = next(line for line in lines if line.startswith("taxsimid,"))
        lines = [
            line
            for line in lines
            if line.split(",")[0].strip().rstrip(".").isdigit()
            and len(line.split(",")) == len(header.split(","))
        ]
        result = list(csv.DictReader([header, *lines]))
        assert len(result) == len(rows)
        assert {int(float(r["taxsimid"])) for r in result} == {
            int(r["taxsimid"]) for r in rows
        }
        assert all(
            math.isfinite(float(r[k]))
            for r in result
            for k in ("fiitax", "siitax", "srebate")
        )
        subset = all_rows[75000:80000]
        current = run(new, subset, year)
        assert current.returncode == -8 and "mdtax22" in current.stderr, (
            current.returncode,
            current.stderr,
        )
        while len(subset) > 1:
            midpoint = len(subset) // 2
            if run(new, subset[:midpoint], year).returncode == -8:
                subset = subset[:midpoint]
            elif run(new, subset[midpoint:], year).returncode == -8:
                subset = subset[midpoint:]
            else:
                # Preserve a multi-record trigger rather than claiming a false single-record case.
                (OUT / f"multi-record-{year}.csv").write_text(encode(subset, year))
                (OUT / f"new-{year}.stderr").write_text(current.stderr)
                evidence.append(
                    {
                        "year": year,
                        "previousBinaryValidatedRows": len(result),
                        "triggerRows": len(subset),
                        "newReturnCode": -8,
                    }
                )
                break
        if len(subset) > 1:
            continue
        row = dict(subset[0])
        assert run(new, [row], year).returncode == -8
        (OUT / f"original-{year}.csv").write_text(encode([row], year))
        # Remove income/deduction fields that are not needed for the crash.
        for field in row:
            if field in {
                "taxsimid",
                "year",
                "state",
                "mstat",
                "page",
                "sage",
                "depx",
                "idtl",
            } or field.startswith("age"):
                continue
            candidate = {**row, field: "0"}
            if run(new, [candidate], year).returncode == -8:
                row = candidate
        new_result = run(new, [row], year)
        old_result = run(old, [row], year)
        assert old_result.returncode == 0
        (OUT / f"minimal-{year}.csv").write_text(encode([row], year))
        (OUT / f"new-{year}.stderr").write_text(new_result.stderr)
        (OUT / f"old-{year}.stdout").write_text(old_result.stdout)
        evidence.append(
            {
                "year": year,
                "previousBinaryValidatedRows": len(result),
                "newReturnCode": new_result.returncode,
                "minimalInput": row,
                "oldReturnCode": old_result.returncode,
            }
        )
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
