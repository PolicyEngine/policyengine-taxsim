"""Bounded, dependency-free reproducer for the September Linux MD crash."""

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
    fields = [k for k in rows[0] if k != "age11"]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(
        {**{k: (v or "0") for k, v in row.items()}, "year": year} for row in rows
    )
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
        rows = [r for r in csv.DictReader(stream) if int(r["state"]) == 21]
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
        current = run(new, rows, year)
        assert current.returncode == -8 and "mdtax22" in current.stderr, (
            current.returncode,
            current.stderr,
        )
        subset = rows
        while len(subset) > 1:
            midpoint = len(subset) // 2
            subset = (
                subset[:midpoint]
                if run(new, subset[:midpoint], year).returncode == -8
                else subset[midpoint:]
            )
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
