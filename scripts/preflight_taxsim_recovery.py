"""Validate every TAXSIM batch before expensive PolicyEngine work; retain GA evidence."""

import csv
import json
import os
from pathlib import Path
import resource
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from policyengine_taxsim.runners import TaxsimRunner
from refresh_dashboard import SOURCE, uses_state_fallback, maryland_fallback_path

OUT = Path("taxsim-preflight")


def run(data, binary=None):
    return TaxsimRunner(data, taxsim_path=binary).run(show_progress=False)


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    OUT.mkdir(exist_ok=True)
    old = maryland_fallback_path()
    data = pd.read_csv(SOURCE)
    # Recreate the 100-household, state-stratified smoke input.
    buckets = [g.head(2) for _, g in data.groupby("state", sort=False)]
    smoke = (
        pd.concat([g.iloc[[i]] for i in range(2) for g in buckets if len(g) > i])
        .head(100)
        .copy()
    )
    smoke["year"] = 2024
    suspect = smoke[smoke.state != 21].copy()
    try:
        run(suspect)
    except Exception as error:
        (OUT / "georgia-original-error.txt").write_text(str(error))
        # Remove records while retaining the same Georgia crash.
        size = 2
        while len(suspect) > 1:
            width = max(1, (len(suspect) + size - 1) // size)
            reduced = False
            for start in range(0, len(suspect), width):
                candidate = pd.concat(
                    [suspect.iloc[:start], suspect.iloc[start + width :]]
                )
                if candidate.empty:
                    continue
                try:
                    run(candidate)
                except Exception as e:
                    if "gatax24" in str(e):
                        suspect = candidate
                        size = max(2, size - 1)
                        reduced = True
                        break
            if not reduced:
                if size >= len(suspect):
                    break
                size = min(len(suspect), size * 2)
        runner = TaxsimRunner(suspect)
        path = Path(runner._create_taxsim_input_file(suspect))
        (OUT / "georgia-reproducer.csv").write_bytes(path.read_bytes())
        path.unlink()
        suspect.to_csv(OUT / "georgia-source-rows.csv", index=False)
        run(suspect, old).to_csv(OUT / "georgia-previous-output.csv", index=False)
        print(
            f"Georgia reproducer: {len(suspect)} records; previous binary succeeds",
            flush=True,
        )
    counts = {}
    for year in (2024, 2025):
        n = 0
        for start in range(0, len(data), 5000):
            batch = data.iloc[start : start + 5000].copy()
            batch["year"] = year
            mask = batch.state.isin([11, 21])
            for subset, binary in ((batch[~mask], None), (batch[mask], old)):
                if subset.empty:
                    continue
                result = run(subset, binary)
                assert not result.taxsimid.duplicated().any()
                assert set(result.taxsimid) == set(subset.taxsimid)
                for col in ["fiitax", "siitax", "srebate"]:
                    assert (
                        result[col]
                        .map(lambda x: pd.notna(x) and abs(x) != float("inf"))
                        .all()
                    )
                n += len(result)
            print(f"Preflight {year}: {n} households validated", flush=True)
        assert n == len(data) == 111347
        counts[year] = n
    (OUT / "validated.json").write_text(json.dumps(counts))


if __name__ == "__main__":
    main()
