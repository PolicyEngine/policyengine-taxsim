"""Re-run the fixed 3,000-household dashboard sample in both NIIT modes.

Use hosted runners. Model workers inherit refresh RSS/disk/time limits; only
small summaries and the largest residuals are retained, never new dashboard data.
"""

import argparse
import csv
import gzip
import json
from pathlib import Path
import shutil

from refresh_dashboard import INPUT_COLUMNS, ROOT, match_flags, number, run_bounded


def pairs(path):
    with gzip.open(path, "rt") as stream:
        rows = iter(csv.DictReader(stream))
        return {a["taxsimid"]: (a, next(rows)) for a in rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path("validation"))
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True)
    work = args.output / str(args.year)
    work.mkdir(exist_ok=True)
    source = (
        ROOT / f"dashboard/public/data/{args.year}/comparison_results_{args.year}.csv"
    )
    with source.open() as f:
        inputs = [r for r in csv.DictReader(f) if r["source"] == "taxsim"]
    assert len(inputs) == 3000
    output, metrics = {}, {}
    for mode in ("active", "passive"):
        output[mode] = {}
        peak, seconds = 0, 0
        # A mixed-state sample loads far more state formulas than the
        # state-sorted full refresh. Keep each fresh worker to 500 records.
        for start in range(0, len(inputs), 500):
            input_file = work / "input.csv"
            with input_file.open("w", newline="") as f:
                writer = csv.DictWriter(f, INPUT_COLUMNS)
                writer.writeheader()
                writer.writerows(
                    {k: r.get(k, "") for k in INPUT_COLUMNS}
                    for r in inputs[start : start + 500]
                )
            path = work / f"{mode}-{start}.csv.gz"
            usage = run_bounded(input_file, path, 5, 4, mode)
            batch = pairs(path)
            assert len(batch) == 500
            assert not output[mode].keys() & batch.keys()
            output[mode].update(batch)
            peak = max(peak, usage["peakRssMiB"])
            seconds += usage["seconds"]
            path.unlink()
            print(
                f"{args.year} {mode}: {start + 500}/3000, peak {peak} MiB", flush=True
            )
        usage = {"peakRssMiB": peak, "seconds": round(seconds, 1)}
        assert len(output[mode]) == 3000
        flags = [match_flags(ts, pe) for ts, pe in output[mode].values()]
        metrics[mode] = {
            "federalRelativeMatches": sum(f[2] for f in flags),
            "stateRelativeMatches": sum(f[3] for f in flags),
            "federalAbsoluteMatches": sum(f[0] for f in flags),
            "niitWithinOneDollar": sum(
                abs(number(t["niit"]) - number(p["niit"])) <= 1
                for t, p in output[mode].values()
            ),
            **usage,
        }
    # Keep the small fixed sample for forensic analysis. Full-population
    # output is never downloaded or retained by this validation workflow.
    with gzip.open(args.output / f"details-{args.year}.json.gz", "wt") as stream:
        json.dump(
            [
                {
                    "taxsim": ts,
                    "active": output["active"][key][1],
                    "passive": pe,
                }
                for key, (ts, pe) in output["passive"].items()
            ],
            stream,
        )
    residuals, improved, regressed = [], 0, 0
    violations = []
    match_columns = {"federal_match", "state_match", "overall_match"}
    for key, (ts, passive) in output["passive"].items():
        old_ts, active = output["active"][key]
        # These annotations describe PE/TAXSIM agreement, not TAXSIM output.
        # They must be allowed to change when the PE classification changes.
        comparator_changes = {
            column: [old_ts[column], ts[column]]
            for column in ts
            if column not in match_columns and old_ts[column] != ts[column]
        }
        if comparator_changes:
            violations.append({"taxsimid": key, "comparator": comparator_changes})
        # NIIT classification must preserve income, QBI and payroll tax.
        for column in ("v10", "qbid", "fica"):
            if abs(number(active[column]) - number(passive[column])) > 1:
                violations.append(
                    {
                        "taxsimid": key,
                        "column": column,
                        "active": number(active[column]),
                        "passive": number(passive[column]),
                    }
                )
        before = match_flags(ts, active)[2]
        after = match_flags(ts, passive)[2]
        improved += after and not before
        regressed += before and not after
        residuals.append(
            {
                "taxsimid": key,
                "scorp": number(ts["scorp"]),
                "state": ts["state_code"],
                "federalErrorActive": number(active["fiitax"]) - number(ts["fiitax"]),
                "federalErrorPassive": number(passive["fiitax"]) - number(ts["fiitax"]),
                "niitErrorPassive": number(passive["niit"]) - number(ts["niit"]),
                "qbidError": number(passive["qbid"]) - number(ts["qbid"]),
            }
        )
    report = {
        "year": args.year,
        "sampleHouseholds": 3000,
        "assumeW2Wages": True,
        "metrics": metrics,
        "invarianceViolations": violations,
        "newFederalMatches": improved,
        "lostFederalMatches": regressed,
        "largestResiduals": sorted(
            residuals, key=lambda r: abs(r["federalErrorPassive"]), reverse=True
        )[:15],
    }
    (args.output / f"alignment-{args.year}.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps({k: v for k, v in report.items() if k != "largestResiduals"}),
        flush=True,
    )
    assert not violations, violations[:5]
    assert (
        metrics["passive"]["federalRelativeMatches"]
        > metrics["active"]["federalRelativeMatches"]
    )
    assert (
        metrics["passive"]["niitWithinOneDollar"]
        > metrics["active"]["niitWithinOneDollar"]
    )
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
