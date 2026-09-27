"""Compare GA/MD reference taxes against the prior complete run on a hosted worker."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def selected(path):
    with path.open() as f:
        return {
            (r["taxsimid"], r["source"]): r
            for r in csv.DictReader(f)
            if r["state_code"] in ("GA", "MD")
        }


def main():
    run = sys.argv[1]
    if not run.isdigit():
        raise ValueError("Expected numeric run ID")
    for year in (2024, 2025):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, source in [("old", "35859275514"), ("new", run)]:
                subprocess.run(
                    [
                        "gh",
                        "run",
                        "download",
                        source,
                        "--repo",
                        "PolicyEngine/policyengine-taxsim",
                        "--name",
                        f"full-data-{year}",
                        "--dir",
                        str(root / name),
                    ],
                    check=True,
                )
            a = selected(root / f"old/comparison_results_{year}.csv")
            b = selected(root / f"new/comparison_results_{year}.csv")
            assert a.keys() == b.keys(), "Fallback population changed"
            errors = []
            for key in a:
                for field in ["fiitax", "siitax", "srebate"]:
                    if abs(float(a[key][field]) - float(b[key][field])) > 0.005:
                        errors.append((key, field, a[key][field], b[key][field]))
            print(
                json.dumps(
                    {
                        "year": year,
                        "householdPairs": len(a) // 2,
                        "changedTaxValues": len(errors),
                        "examples": errors[:10],
                    }
                ),
                flush=True,
            )
            assert not errors, "GA/MD results changed from prior baseline"


if __name__ == "__main__":
    main()
