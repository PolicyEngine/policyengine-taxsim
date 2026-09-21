"""Reproducible dashboard refresh with streaming I/O and isolated model workers.

The coordinator never imports PolicyEngine. Each worker handles one batch and
exits after atomically saving its result, releasing all model caches to the OS.
"""

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TAG = "full-ecps-comparison-2026.07.07"
EXPECTED_RECORDS = 111347
STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
INPUT_COLUMNS = (
    "taxsimid year state mstat page sage depx pwages psemp swages ssemp dividends intrec stcg ltcg otherprop nonprop pensions gssi pui sui transfers rentpaid proptax otheritem childcare mortgage scorp idtl "
    + " ".join(f"age{i}" for i in range(1, 12))
).split()


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def number(value):
    value = float(value or 0)
    if not math.isfinite(value):
        raise ValueError("Non-finite comparison value")
    return value


def match_flags(taxsim, pe):
    # Same gross-income proxy and strict relative threshold as dataLoader.js.
    gross = sum(
        number(taxsim.get(k))
        for k in (
            "pwages",
            "swages",
            "psemp",
            "ssemp",
            "intrec",
            "dividends",
            "otherprop",
            "nonprop",
            "pensions",
            "pui",
            "sui",
        )
    )
    gross += (
        max(number(taxsim.get("stcg")), 0)
        + max(number(taxsim.get("ltcg")), 0)
        + 0.85 * number(taxsim.get("gssi"))
    )
    fed = abs(number(pe["fiitax"]) - number(taxsim["fiitax"]))
    state = abs(number(pe["siitax"]) - number(taxsim["siitax"]))
    net = abs(
        number(pe["siitax"])
        + number(pe["srebate"])
        - number(taxsim["siitax"])
        - number(taxsim["srebate"])
    )
    return [
        fed <= 15,
        state <= 15,
        fed < 0.01 * gross if gross > 0 else fed <= 15,
        state < 0.01 * gross if gross > 0 else state <= 15,
        net < 0.01 * gross if gross > 0 else net <= 15,
    ]


def worker(input_path, output_path):
    sys.path.insert(0, str(ROOT))
    import pandas as pd
    from policyengine_taxsim.runners import PolicyEngineRunner, TaxsimRunner

    data = pd.read_csv(input_path)
    pe_input = data.copy()
    # Request detailed PE output (including staxbc), without changing tax inputs.
    pe_input["idtl"] = 5
    pe = PolicyEngineRunner(
        pe_input, logs=False, assume_w2_wages=True, disable_salt=False
    ).run(show_progress=False)
    ts = TaxsimRunner(data).run(show_progress=False)
    expected_ids = set(data.taxsimid)
    for name, result in [("PolicyEngine", pe), ("TAXSIM", ts)]:
        if result.taxsimid.duplicated().any() or set(result.taxsimid) != expected_ids:
            raise ValueError(f"{name} lost or duplicated household IDs")
        if result[["fiitax", "siitax", "srebate"]].isna().any().any():
            raise ValueError(f"{name} missing required outputs")
    ts = ts.set_index("taxsimid").to_dict("index")
    pe = pe.set_index("taxsimid").to_dict("index")
    records = []
    for raw in data.to_dict("records"):
        key = raw["taxsimid"]
        rows = []
        for source, results in [("taxsim", ts), ("policyengine", pe)]:
            row = {
                **results[key],
                **raw,
                "source": source,
                "state_code": STATES[int(raw["state"]) - 1],
            }
            rows.append(row)
        flags = match_flags(*rows)
        for row in rows:
            row.update(
                federal_match=flags[0],
                state_match=flags[1],
                overall_match=flags[0] and flags[1],
            )
            records.append(row)
    pd.DataFrame(records).to_csv(output_path, index=False, compression="gzip")
    # Data and file handles are closed. Avoid expensive cyclic-GC teardown of
    # the model graph; process exit releases the entire worker address space.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def run_bounded(input_path, output_path, max_memory_gb, min_disk_gb):
    import psutil

    started = time.monotonic()
    peak = 0
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        str(input_path),
        str(output_path),
    ]
    child = subprocess.Popen(cmd, start_new_session=True)
    try:
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                rss = process.memory_info().rss + sum(
                    p.memory_info().rss
                    for p in process.children(recursive=True)
                    if p.is_running()
                )
            except psutil.NoSuchProcess:
                rss = 0
            peak = max(peak, rss)
            if rss > max_memory_gb * 1024**3:
                raise RuntimeError(
                    "Worker exceeded memory budget; reduce --batch-size and retry"
                )
            if shutil.disk_usage(input_path.parent).free < min_disk_gb * 1024**3:
                raise RuntimeError("Disk reserve reached; refusing to continue")
            if time.monotonic() - started > 900:
                raise RuntimeError("Worker exceeded 15-minute timeout")
            time.sleep(2)
        if child.returncode != 0:
            raise RuntimeError(f"Worker failed with exit {child.returncode}")
    finally:
        if child.poll() is None:
            import signal

            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    return {
        "peakRssMiB": round(peak / 1024**2),
        "seconds": round(time.monotonic() - started, 1),
    }


def summarize(parts, output_dir, year, metadata, sample_ids):
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = [0] * 6
    by_state = {}
    fields = []
    for path in parts:
        with gzip.open(path, "rt", newline="") as stream:
            for field in csv.DictReader(stream).fieldnames:
                if field not in fields:
                    fields.append(field)
    full = output_dir / f"comparison_results_{year}.csv"
    site = output_dir / "site" / str(year)
    site.mkdir(parents=True, exist_ok=True)
    sampled_ids = set()
    seen = set()
    with full.open("w", newline="") as f, (site / full.name).open("w", newline="") as s:
        writers = [csv.DictWriter(stream, fields) for stream in (f, s)]
        for writer in writers:
            writer.writeheader()
        for part in parts:
            with gzip.open(part, "rt", newline="") as stream:
                reader = iter(csv.DictReader(stream))
                for taxsim in reader:
                    pe = next(reader)
                    key = str(int(float(taxsim["taxsimid"])))
                    if (
                        taxsim["source"] != "taxsim"
                        or pe["source"] != "policyengine"
                        or taxsim["taxsimid"] != pe["taxsimid"]
                        or key in seen
                    ):
                        raise ValueError("Invalid or duplicate household pair")
                    seen.add(key)
                    flags = match_flags(taxsim, pe)
                    state_counts = by_state.setdefault(taxsim["state_code"], [0] * 6)
                    for tally in (counts, state_counts):
                        tally[0] += 1
                        for i, flag in enumerate(flags, 1):
                            tally[i] += int(flag)
                    for row in (taxsim, pe):
                        writers[0].writerow(row)
                        if key in sample_ids:
                            writers[1].writerow(row)
                            sampled_ids.add(key)
    if len(sampled_ids) != len(sample_ids & seen):
        raise ValueError("Incomplete drill-down sample")

    def percentages(tally):
        return [round(100 * n / tally[0], 1) for n in tally[1:]]

    summary = dict(
        zip(
            [
                "federalMatchPct",
                "stateMatchPct",
                "federalMatchPctRel",
                "stateMatchPctRel",
                "stateMatchPctRelNet",
            ],
            percentages(counts),
        )
    )
    summary.update(
        totalRecords=counts[0], metadata=metadata, sampleRecords=len(sampled_ids)
    )
    summary["stateBreakdown"] = []
    for state, tally in sorted(by_state.items(), key=lambda item: -item[1][0]):
        entry = dict(
            zip(
                [
                    "federalPct",
                    "statePct",
                    "federalPctRel",
                    "statePctRel",
                    "statePctRelNet",
                ],
                percentages(tally),
            )
        )
        entry.update(
            state=state,
            households=tally[0],
            federalMatches=tally[1],
            stateMatches=tally[2],
        )
        summary["stateBreakdown"].append(entry)
    atomic_json(site / f"summary_{year}.json", summary)
    atomic_json(
        output_dir / f"provenance_{year}.json",
        {**metadata, "records": counts[0], "outputSha256": digest(full)},
    )
    print(
        json.dumps({k: v for k, v in summary.items() if k != "stateBreakdown"}),
        flush=True,
    )
    return counts[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2)
    parser.add_argument("--year", type=int, choices=range(2021, 2026))
    parser.add_argument("--work-dir", type=Path, default=Path("refresh-work"))
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Smoke test only; 0 processes the complete population",
    )
    parser.add_argument("--max-memory-gb", type=float, default=5)
    parser.add_argument("--min-disk-gb", type=float, default=4)
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
        return
    if args.year is None or not 1 <= args.batch_size <= 10000 or args.limit < 0:
        parser.error("A year, batch size 1–10000, and nonnegative limit are required")
    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work).free < args.min_disk_gb * 1024**3:
        raise RuntimeError("Insufficient free disk space")
    source = work / "source.csv"
    if not source.exists():
        url = f"https://github.com/PolicyEngine/policyengine-taxsim/releases/download/{SOURCE_TAG}/comparison_results_{args.year}.csv"
        with (
            urllib.request.urlopen(url, timeout=120) as response,
            source.with_suffix(".tmp").open("wb") as target,
        ):
            shutil.copyfileobj(response, target, length=1024 * 1024)
        source.with_suffix(".tmp").replace(source)
    identity = {
        "sourceTag": SOURCE_TAG,
        "sourceSha256": digest(source),
        "year": args.year,
        "emulatorCommit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "requirementsSha256": digest(
            ROOT / "scripts/dashboard-refresh-requirements.txt"
        ),
        "scriptSha256": digest(__file__),
        "batchSize": args.batch_size,
        "limit": args.limit,
    }
    manifest = work / "checkpoint.json"
    if manifest.exists() and json.loads(manifest.read_text()) != identity:
        raise RuntimeError(
            "Checkpoint configuration differs; use a fresh work directory"
        )
    atomic_json(manifest, identity)
    with (
        ROOT / f"dashboard/public/data/{args.year}/comparison_results_{args.year}.csv"
    ).open() as f:
        sample_ids = {str(int(float(row["taxsimid"]))) for row in csv.DictReader(f)}
    parts = []
    processed = 0
    peak = 0
    with source.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = (row for row in reader if row["source"] == "taxsim")
        if args.limit:
            # Cover every state in the smoke test; the source is state-sorted.
            per_state = {}
            quota = math.ceil(args.limit / len(STATES))
            for row in rows:
                bucket = per_state.setdefault(row["state"], [])
                if len(bucket) < quota:
                    bucket.append(row)
            rows = iter(
                [
                    bucket[i]
                    for i in range(quota)
                    for bucket in per_state.values()
                    if i < len(bucket)
                ][: args.limit]
            )
        while batch := list(itertools.islice(rows, args.batch_size)):
            part = work / f"part-{len(parts):04}.csv.gz"
            check = part.with_suffix(".json")
            if (
                not part.exists()
                or not check.exists()
                or digest(part) != json.loads(check.read_text())["sha256"]
            ):
                input_path = work / "batch-input.csv"
                with input_path.open("w", newline="") as f:
                    writer = csv.DictWriter(f, INPUT_COLUMNS)
                    writer.writeheader()
                    for row in batch:
                        if int(float(row["year"])) != args.year:
                            raise ValueError("Source year mismatch")
                        writer.writerow({k: row.get(k, "") for k in INPUT_COLUMNS})
                temp = part.with_suffix(".tmp.gz")
                usage = run_bounded(
                    input_path, temp, args.max_memory_gb, args.min_disk_gb
                )
                temp.replace(part)
                atomic_json(
                    check, {"sha256": digest(part), "records": len(batch), **usage}
                )
                input_path.unlink()
            usage = json.loads(check.read_text())
            peak = max(peak, usage["peakRssMiB"])
            processed += len(batch)
            parts.append(part)
            print(
                f"Checkpoint: {args.year} {processed} households, peak worker {peak} MiB",
                flush=True,
            )
    expected = min(args.limit, EXPECTED_RECORDS) if args.limit else EXPECTED_RECORDS
    if processed != expected:
        raise ValueError(f"Expected {expected} source households, got {processed}")
    metadata = {
        **identity,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "policyengineUsVersion": importlib.metadata.version("policyengine-us"),
        "policyengineCoreVersion": importlib.metadata.version("policyengine-core"),
        "spmCalculatorVersion": importlib.metadata.version("spm-calculator"),
        "peakWorkerRssMiB": peak,
        "assumeW2Wages": True,
        "disableSalt": False,
        "policyengineOutputDetail": 5,
        "taxsimBinarySha256": digest(ROOT / "resources/taxsimtest/taxsimtest-linux.exe")
        if (ROOT / "resources/taxsimtest/taxsimtest-linux.exe").exists()
        else None,
    }
    actual = summarize(parts, work / "output", args.year, metadata, sample_ids)
    if actual != expected:
        raise ValueError("Output record count mismatch")
    source.unlink()  # A completed job only retains results/checkpoints.


if __name__ == "__main__":
    main()
