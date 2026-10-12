"""DIAGNOSTIC ONLY (branch diag/hash-seed-segfault, never merged).

Repeats test_runner_output_is_independent_of_hash_seed's two concurrent
PolicyEngineRunner children to catch the SIGSEGV seen in CI run 38193095063.
Each child prints phase markers so the log shows how far it got, and runs
with faulthandler on so a crash prints the Python stack of every thread.
Results go to $DIAG_OUT; the test fails at the end if any child failed.
"""

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from test_deterministic_ordering import (
    RECORDS,
    _child_env,
    _seeds_with_opposite_set_order,
)

REPEATS = int(os.environ.get("DIAG_REPEATS", "8"))
DIAG_OUT = Path(os.environ.get("DIAG_OUT", "diag_out"))

CHILD = textwrap.dedent(
    """\
    import atexit
    import faulthandler
    import resource
    import sys
    import time

    faulthandler.enable(all_threads=True)
    T0 = time.monotonic()


    def mark(label):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
        print(f"@@MARK {label} t={time.monotonic() - T0:.1f}s maxrss={rss:.0f}MB",
              file=sys.stderr, flush=True)


    atexit.register(mark, "atexit-handler")
    mark("start")
    import pandas as pd

    from policyengine_taxsim.runners.policyengine_runner import (
        PolicyEngineRunner,
    )

    mark("imported")
    input_path, out_path = sys.argv[1], sys.argv[2]
    df = pd.read_csv(input_path)
    result = PolicyEngineRunner(df).run(show_progress=False)
    mark("run-returned")
    with open(out_path, "w") as f:
        f.write(result.to_json(orient="split"))
    mark("json-written")
    """
)


@pytest.mark.parametrize("rep", range(REPEATS))
def test_diag_concurrent_children(rep):
    out = DIAG_OUT / f"rep{rep}"
    out.mkdir(parents=True, exist_ok=True)
    seeds = _seeds_with_opposite_set_order()
    (out / "input.csv").write_text(RECORDS)
    (out / "child.py").write_text(CHILD)

    processes = {}
    started = time.monotonic()
    for seed in seeds:
        with open(out / f"seed_{seed}.log", "w") as log:
            processes[seed] = subprocess.Popen(
                [
                    sys.executable,
                    str(out / "child.py"),
                    str(out / "input.csv"),
                    str(out / f"seed_{seed}.json"),
                ],
                env={**_child_env(seed), "PYTHONFAULTHANDLER": "1"},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    results = {}
    for seed, process in processes.items():
        process.wait(timeout=1800)
        log_text = (out / f"seed_{seed}.log").read_text()
        markers = [line for line in log_text.splitlines() if "@@MARK" in line]
        results[seed] = {
            "returncode": process.returncode,
            "pid": process.pid,
            "elapsed": round(time.monotonic() - started, 1),
            "last_marker": markers[-1] if markers else None,
            "json_exists": (out / f"seed_{seed}.json").exists(),
        }
    with open(DIAG_OUT / "summary.jsonl", "a") as f:
        f.write(json.dumps({"rep": rep, "results": results}) + "\n")
    failed = {s: r for s, r in results.items() if r["returncode"] != 0}
    assert not failed, json.dumps(failed, indent=2)
