"""Run one batch of households through an installed policyengine-taxsim release.

This file is run by ``alignment_history.py measure`` with the interpreter of an
isolated environment that holds one policyengine-taxsim / policyengine-us pair,
as ``python -I alignment_worker.py ...``. ``-I`` keeps this checkout off
``sys.path``, so the release under test is the only emulator that can import.

Only the standard library and the release under test are used here: older
releases expose fewer ``PolicyEngineRunner`` options, so the options are passed
only when the installed signature accepts them, and the applied settings are
written next to the outputs.
"""

import csv
import gzip
import importlib.metadata
import inspect
import json
import os
import platform
import sys
import traceback

# The dashboard refresh (scripts/refresh_dashboard.py) runs PolicyEngine with
# these options; the alignment history scores every release the same way.
REQUESTED = {"logs": False, "assume_w2_wages": True, "disable_salt": False}
# PE detail level 5, as the refresh requests; it changes no tax input.
OUTPUT_DETAIL = 5
OUTPUTS = ("fiitax", "siitax", "srebate")


def versions():
    found = {}
    for name in ("policyengine-taxsim", "policyengine-us", "policyengine-core"):
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return found


def scorp_default():
    """The S-corp NIIT treatment the release applies by default, if it has one."""
    try:
        from policyengine_taxsim.core.scorp import validate_scorp_treatment
    except ImportError:
        return None
    return validate_scorp_treatment(None)


def main(input_path, output_path, settings_path, years):
    import pandas as pd
    from policyengine_taxsim.runners import PolicyEngineRunner

    accepted = inspect.signature(PolicyEngineRunner.__init__).parameters
    options = {k: v for k, v in REQUESTED.items() if k in accepted}
    data = pd.read_csv(input_path)
    expected = set(data.taxsimid)
    errors = {}
    rows = []
    for year in years:
        frame = data.copy()
        frame["year"] = year
        frame["idtl"] = OUTPUT_DETAIL
        try:
            result = PolicyEngineRunner(frame, **options).run(show_progress=False)
            if result.taxsimid.duplicated().any() or set(result.taxsimid) != expected:
                raise ValueError("PolicyEngine lost or duplicated household IDs")
            missing = [c for c in OUTPUTS if c not in result.columns]
            if missing:
                raise ValueError(f"PolicyEngine output lacks {', '.join(missing)}")
            if result[list(OUTPUTS)].isna().any().any():
                raise ValueError("PolicyEngine returned missing tax outputs")
        except Exception as error:  # Record the failure; score the other years.
            errors[str(year)] = "".join(
                traceback.format_exception_only(type(error), error)
            ).strip()[-2000:]
            continue
        for record in result[["taxsimid", *OUTPUTS]].to_dict("records"):
            rows.append({"year": year, **record})
    with gzip.open(output_path, "wt", newline="") as stream:
        writer = csv.DictWriter(stream, ["taxsimid", "year", *OUTPUTS])
        writer.writeheader()
        writer.writerows(rows)
    with open(settings_path, "w") as stream:
        json.dump(
            {
                "versions": versions(),
                "pythonVersion": platform.python_version(),
                "applied": options,
                "unsupported": sorted(set(REQUESTED) - set(options)),
                "scorpTreatment": scorp_default(),
                "policyengineOutputDetail": OUTPUT_DETAIL,
                "errors": errors,
            },
            stream,
            indent=2,
        )
    sys.stdout.flush()
    sys.stderr.flush()
    # Skip the slow teardown of the model graph; exit releases the memory.
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--versions":
        print(json.dumps(versions()))
        sys.exit(0)
    main(sys.argv[1], sys.argv[2], sys.argv[3], [int(y) for y in sys.argv[4:]])
