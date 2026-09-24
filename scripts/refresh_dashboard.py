"""Reproducible dashboard refresh with streaming I/O and isolated model workers.

The coordinator never imports PolicyEngine. Each worker handles one batch and
exits after atomically saving its result, releasing all model caches to the OS.
"""

import argparse
from collections import Counter
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
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
# TAXSIM input sources: one row per tax unit, reused for every tax year (the
# year column is set per run). Populace is the benchmark population. The
# archived Enhanced CPS stays available as a secondary dataset because the
# Populace build it replaced lacks the eCPS's high-income tail.
DATASETS = {
    "populace": {
        "label": "Populace US 2024",
        "source": ROOT / "populace_households.csv",
        # Written by scripts/convert_h5_to_taxsim.py: build id, Hugging Face
        # revision and sha256, and the certified model used to read the H5.
        "provenance": ROOT / "populace_households.json",
        "records": 79729,
        # Populace records populate more inputs (itemized deductions,
        # transfers), so 5,000-record workers exceeded the 5 GiB budget.
        "batchSize": 2000,
        # Drill-down IDs are a hash-ranked, state-stratified draw from the
        # source, so they are stable across years and refreshes.
        "heldSample": False,
    },
    "ecps": {
        "label": "Enhanced CPS (archived)",
        "source": ROOT / "cps_households.csv",
        "provenance": None,
        "records": 111347,
        "batchSize": 5000,
        # Drill-down IDs are held at the published dashboard sample.
        "heldSample": True,
        "description": (
            "TAXSIM inputs built in April 2025 (4ccfead, vectorized_validation.py) "
            "from the Enhanced CPS, which policyengine-us-data archived on "
            "2026-07-02; Alabama recoded from state 0 to 1 in September 2026."
        ),
    },
}
DEFAULT_DATASET = "populace"
COMPARISON_NOTE = (
    "PolicyEngine's own comparison of its TAXSIM emulator against NBER's "
    "taxsimtest binary on identical inputs. Agreement rates are not error "
    "statistics endorsed by NBER or Dan Feenberg."
)
SAMPLE_SIZE = 3000
SAMPLE_STATE_MINIMUM = 20
# Headline agreement rates, in the order match_flags returns them.
RATE_KEYS = (
    "federalMatchPct",
    "stateMatchPct",
    "federalMatchPctRel",
    "stateMatchPctRel",
    "stateMatchPctRelNet",
)
# Kept for callers that predate multiple datasets.
SOURCE = DATASETS["ecps"]["source"]
EXPECTED_RECORDS = DATASETS["ecps"]["records"]
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


def check_source(path):
    """Validate the TAXSIM inputs before any model runs; return the row count.

    TAXSIM reads state 0 as "no state tax" and stops at other invalid codes.
    Every eCPS household has a state, so reject state 0, any other code that
    is not an integer from 1 to 51, and any state without households.
    """
    counts = Counter()
    invalid = {}
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != INPUT_COLUMNS:
            raise ValueError("Source columns differ from the TAXSIM input columns")
        for row in reader:
            try:
                state = float(row["state"])
            except ValueError:
                state = math.nan
            if state.is_integer() and 1 <= state <= len(STATES):
                counts[int(state)] += 1
            else:
                invalid.setdefault(row["state"], row["taxsimid"])
    if invalid:
        examples = ", ".join(
            f"{code!r} (taxsimid {id})" for code, id in invalid.items()
        )
        raise ValueError(f"Source has invalid TAXSIM state codes: {examples}")
    missing = [code for i, code in enumerate(STATES, 1) if not counts[i]]
    if missing:
        raise ValueError(f"Source has no households in {' '.join(missing)}")
    return sum(counts.values())


def drilldown_sample(path, size=SAMPLE_SIZE, minimum=SAMPLE_STATE_MINIMUM):
    """Deterministic drill-down sample of taxsimids from a source CSV.

    Each state contributes its proportional share of ``size`` (at least
    ``minimum`` households, or all of them if fewer), taking the records with
    the smallest sha256 rank of their taxsimid. The draw depends only on the
    source, so every year and every rerun shows the same households.
    """
    by_state = {}
    with Path(path).open(newline="") as stream:
        for row in csv.DictReader(stream):
            key = str(int(float(row["taxsimid"])))
            rank = hashlib.sha256(f"taxsim-drilldown:{key}".encode()).hexdigest()
            by_state.setdefault(int(float(row["state"])), []).append((rank, key))
    total = sum(len(items) for items in by_state.values())
    chosen = set()
    for items in by_state.values():
        items.sort()
        quota = max(minimum, round(size * len(items) / total))
        chosen.update(key for _, key in items[:quota])
    return chosen


def dataset_metadata(name):
    """Provenance of a dataset's TAXSIM inputs, recorded in every summary."""
    spec = DATASETS[name]
    source = spec["source"]
    meta = {
        "id": name,
        "label": spec["label"],
        "source": source.name,
        "sourceSha256": digest(source),
        "records": spec["records"],
    }
    if spec.get("description"):
        meta["description"] = spec["description"]
    if spec["provenance"] is not None:
        provenance = json.loads(spec["provenance"].read_text())
        if provenance.get("outputSha256") != meta["sourceSha256"]:
            raise ValueError(
                f"{spec['provenance'].name} does not describe {source.name}; "
                "regenerate both with scripts/convert_h5_to_taxsim.py"
            )
        if provenance.get("records") != spec["records"]:
            raise ValueError(f"{spec['provenance'].name} record count differs")
        meta.update(
            {
                k: provenance[k]
                for k in (
                    "buildId",
                    "hfRepo",
                    "hfRevision",
                    "hfCommit",
                    "h5File",
                    "h5Sha256",
                    "dataYear",
                    "certifiedBy",
                    "conversionModel",
                    "converterSha256",
                )
                if k in provenance
            }
        )
    return meta


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
    from policyengine_taxsim.core.utils import get_state_code

    data = pd.read_csv(input_path)

    class LoggedTaxsimRunner(TaxsimRunner):
        def _execute_taxsim(self, input_file, output_file):
            result = super()._execute_taxsim(input_file, output_file)
            if result.stderr:
                print("TAXSIM stderr:", result.stderr, flush=True)
            return result

    ts = LoggedTaxsimRunner(data).run(show_progress=False)
    expected_ids = set(data.taxsimid)
    if ts.taxsimid.duplicated().any() or set(ts.taxsimid) != expected_ids:
        missing = expected_ids - set(ts.taxsimid)
        print(
            "TAXSIM returned",
            len(ts),
            "rows; extra IDs",
            list(set(ts.taxsimid) - expected_ids)[:10],
            flush=True,
        )
        print(
            "Missing input records:",
            data[data.taxsimid.isin(missing)].head(5).to_json(orient="records"),
            flush=True,
        )
        raise ValueError("TAXSIM lost or duplicated household IDs")
    pe_input = data.copy()
    # Request detailed PE output (including staxbc), without changing tax inputs.
    pe_input["idtl"] = 5
    pe = PolicyEngineRunner(
        pe_input, logs=False, assume_w2_wages=True, disable_salt=False
    ).run(show_progress=False)
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
                "state_code": get_state_code(raw["state"]),
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
    # taxsimtest prints its build stamp (e.g. cd2026081819) as an output column.
    builds = sorted(
        f for f in fields if len(f) == 12 and f[:2] == "cd" and f[2:].isdigit()
    )
    if builds:
        metadata = {**metadata, "taxsimtestBuild": builds[-1]}
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
                    if taxsim["state_code"] not in STATES:
                        raise ValueError(f"Household {key} has no valid state code")
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
    expected_sample_ids = sample_ids & seen if metadata.get("limit", 0) else sample_ids
    if sampled_ids != expected_sample_ids:
        raise ValueError("Incomplete drill-down sample")

    def percentages(tally):
        return [round(100 * n / tally[0], 1) for n in tally[1:]]

    summary = dict(zip(RATE_KEYS, percentages(counts)))
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
        {
            **metadata,
            "records": counts[0],
            "outputSha256": digest(full),
            "rates": {k: summary[k] for k in RATE_KEYS},
        },
    )
    print(
        json.dumps({k: v for k, v in summary.items() if k != "stateBreakdown"}),
        flush=True,
    )
    return counts[0]


def _release_provenance(folder):
    records = [
        json.loads(path.read_text())
        for path in sorted(Path(folder).glob("provenance_*.json"))
    ]
    if not records:
        raise ValueError(f"No provenance_*.json files in {folder}")
    for r in records:
        # Releases publish full-population results only, never smoke runs.
        if r.get("limit") or r.get("records") != r["dataset"]["records"]:
            raise ValueError(
                f"{r['year']} provenance covers {r.get('records')} of "
                f"{r['dataset']['records']} records; release full runs only"
            )
    for key in ("dataset", "emulatorCommit", "policyengineUsVersion"):
        if len({json.dumps(r.get(key), sort_keys=True) for r in records}) != 1:
            raise ValueError(f"Provenance files disagree on {key}")
    return records


def release_title(folder):
    """Title of a staged comparison release."""
    first = _release_provenance(folder)[0]
    return (
        f"TAXSIM comparison: {first['dataset']['label']}, {first['generatedAt'][:10]}"
    )


def release_notes(folder, run_url=""):
    """Markdown notes for a staged comparison release, from its provenance files."""
    records = _release_provenance(folder)
    first = records[0]
    data = first["dataset"]
    years = sorted(r["year"] for r in records)
    lines = [
        f"**{COMPARISON_NOTE}**",
        "",
        f"**Population.** {data['label']}: {data['records']:,} TAXSIM records, one "
        f"per tax unit, scored under each tax year's law ({years[0]}–{years[-1]}).",
    ]
    if "buildId" in data:
        lines.append(
            f"Built from `{data['buildId']}`: `{data['hfRepo']}` at revision "
            f"`{data['hfRevision']}` (commit `{data['hfCommit']}`), file "
            f"`{data['h5File']}`, sha256 `{data['h5Sha256']}`. The H5 was read with "
            + ", ".join(f"{k} {v}" for k, v in data["conversionModel"].items())
            + f", the model version {data['certifiedBy']} certifies for this build."
        )
    elif data.get("description"):
        lines.append(data["description"])
    lines += [
        f"TAXSIM inputs: `{data['source']}`, sha256 `{data['sourceSha256']}`.",
        "",
        "**Environment.** "
        f"PolicyEngine US {first['policyengineUsVersion']}, PolicyEngine Core "
        f"{first['policyengineCoreVersion']}, emulator commit "
        f"`{first['emulatorCommit']}`; NBER taxsimtest "
        f"{first.get('taxsimtestBuild', '(build not reported)')}, sha256 "
        f"`{first['taxsimBinarySha256']}`. Flags: assume_w2_wages="
        f"{first['assumeW2Wages']}, disable_salt={first['disableSalt']}.",
        "",
        "| Year | Federal, within $15 | State, within $15 | Federal, within 1% "
        "of income | State, within 1% of income | State net of rebates, within 1% |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: r["year"]):
        rates = r["rates"]
        lines.append(
            f"| {r['year']} | "
            + " | ".join(f"{rates[k]:.1f}%" for k in RATE_KEYS)
            + " |"
        )
    lines += [
        "",
        "Income is the dashboard's gross-income proxy; records with no positive "
        "income use the $15 tolerance. Each CSV has two rows per record "
        "(`source` = `taxsim` / `policyengine`); each provenance JSON records "
        "model versions, input and output hashes, and resource use.",
    ]
    if run_url:
        lines += ["", f"[Generation run]({run_url})"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2)
    parser.add_argument("--release-notes", type=Path, metavar="DIR")
    parser.add_argument("--release-title", type=Path, metavar="DIR")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--year", type=int, choices=range(2021, 2026))
    parser.add_argument("--dataset", choices=sorted(DATASETS), default=DEFAULT_DATASET)
    parser.add_argument("--work-dir", type=Path, default=Path("refresh-work"))
    parser.add_argument(
        "--batch-size", type=int, help="Households per worker (default: the dataset's)"
    )
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
    if args.release_notes:
        sys.stdout.write(release_notes(args.release_notes, args.run_url))
        return
    if args.release_title:
        print(release_title(args.release_title))
        return
    if args.batch_size is None:
        args.batch_size = DATASETS[args.dataset]["batchSize"]
    if args.year is None or not 1 <= args.batch_size <= 10000 or args.limit < 0:
        parser.error("A year, batch size 1–10000, and nonnegative limit are required")
    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work).free < args.min_disk_gb * 1024**3:
        raise RuntimeError("Insufficient free disk space")
    spec = DATASETS[args.dataset]
    source = spec["source"]
    expected_records = spec["records"]
    if check_source(source) != expected_records:
        raise ValueError(f"Expected {expected_records} source households")
    identity = {
        "source": source.name,
        "sourceSha256": digest(source),
        "dataset": dataset_metadata(args.dataset),
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
    if spec["heldSample"]:
        held = (
            ROOT
            / "dashboard/public/data"
            / args.dataset
            / str(args.year)
            / f"comparison_results_{args.year}.csv"
        )
        with held.open() as f:
            sample_ids = {str(int(float(row["taxsimid"]))) for row in csv.DictReader(f)}
    else:
        sample_ids = drilldown_sample(source)
    parts = []
    processed = 0
    peak = 0
    with source.open(newline="") as stream:
        rows = (dict(row, year=args.year) for row in csv.DictReader(stream))
        if args.limit:
            # Cover every state in the smoke test.
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
                    writer.writerows(batch)
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
    expected = min(args.limit, expected_records) if args.limit else expected_records
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
        # These rates compare PolicyEngine with NBER's taxsimtest binary on
        # identical inputs. NBER has not endorsed them as error statistics.
        "comparisonNote": COMPARISON_NOTE,
    }
    actual = summarize(parts, work / "output", args.year, metadata, sample_ids)
    if actual != expected:
        raise ValueError("Output record count mismatch")


if __name__ == "__main__":
    main()
