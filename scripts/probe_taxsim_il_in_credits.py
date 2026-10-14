"""Temporary CI probe for #1206: Illinois and Indiana state credits (v39).

On a Mac with Rosetta 2 reinstalled under macOS 27, build cd2026100817 gives
IL 2021-2023 and IN 2021-2022 returns state credits that no rule there
supports (a single IL renter with no children: v39 270.36; every IN 2021
return: 135.18), where the same build and inputs gave 0.00 on macOS 26, as
the August build cd2026081819 still does. This prints what each platform's
bundled build returns, so the hosted runners show whether the values depend
on the platform. It never fails the job.
"""

import os
import platform
import sys

import pandas as pd

from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

COLUMNS = [
    "taxsimid",
    "year",
    "state",
    "mstat",
    "page",
    "sage",
    "depx",
    "pwages",
    "swages",
]
COLUMNS += ["intrec", "rentpaid", "age1", "age2", "age3", "idtl"]
# taxsimid, year, SOI state, mstat, page, sage, depx, pwages, swages, intrec,
# rentpaid, age1, age2, age3. 14 = IL, 15 = IN, 5 = CA (control).
RECORDS = [
    (1, 2021, 14, 1, 38, 0, 0, 34571.43, 0, 0, 9549.01, 0, 0, 0),
    (2, 2022, 14, 1, 38, 0, 0, 34571.43, 0, 0, 9549.01, 0, 0, 0),
    (3, 2023, 14, 1, 38, 0, 0, 34571.43, 0, 0, 9549.01, 0, 0, 0),
    (4, 2021, 14, 2, 46, 19, 2, 33523.81, 0, 0, 0, 15, 14, 0),
    (5, 2021, 15, 1, 49, 0, 0, 34571.43, 0, 0, 0, 0, 0, 0),
    (6, 2022, 15, 1, 49, 0, 0, 34571.43, 0, 0, 0, 0, 0, 0),
    (7, 2021, 15, 2, 45, 46, 3, 52380.95, 38552.38, 1156.57, 0, 18, 18, 18),
    (8, 2024, 15, 1, 49, 0, 0, 34571.43, 0, 0, 0, 0, 0, 0),
    (9, 2021, 5, 1, 38, 0, 0, 34571.43, 0, 0, 9549.01, 0, 0, 0),
]


def main():
    df = pd.DataFrame([list(r) + [2] for r in RECORDS], columns=COLUMNS)
    runner = TaxsimRunner(df)
    out = runner.run(show_progress=False)
    out["taxsimid"] = out["taxsimid"].astype(float).astype(int)
    shown = out.set_index("taxsimid")[
        ["year", "state", "staxbc", "v39", "v40", "siitax"]
    ]
    header = (
        f"TAXSIM build {getattr(runner, 'binary_build_date', 'unknown')} on "
        f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
    )
    table = shown.to_string()
    print(header)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(f"### IL/IN credit probe\n\n{header}\n\n```\n{table}\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
