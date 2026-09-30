"""Compare the emulator with BLS's published TAXSIM outputs in the CE PUMD.

The BLS Consumer Expenditure Survey public-use microdata (PUMD) interview
files carry NTAXI tables: one row per tax unit with the TAXSIM inputs BLS
built and the TAXSIM outputs it published, for the current tax year (*_CY)
and the prior tax year (*_PY). Input construction follows Curtin (2017),
"Calculating Inputs for the NBER TAXSIM model, using the CE PUMD", whose 22
variables are TAXSIM-9's 22 inputs in order.

Steps (each writes into OUT_DIR):

    python scripts/ce_pumd_comparison.py build    CE_DIR OUT_DIR
    python scripts/ce_pumd_comparison.py taxsim   OUT_DIR
    python scripts/ce_pumd_comparison.py emulator OUT_DIR --label fixed --year 2021
    python scripts/ce_pumd_comparison.py report   OUT_DIR --label fixed [--label other]

CE_DIR holds the unzipped interview releases (intrvw21/, intrvw22/, ...),
e.g. from scripts/ce_pumd_download.sh. Only tax years >= 2021 are compared,
the years the emulator computes with PolicyEngine.
"""

import argparse
import glob
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

# NTAXI input -> TAXSIM input (Curtin 2017; ages and TAXSIM-32 dependent
# counts replace T65CT from 2018).
INPUT_MAP = {
    "AGE_TP": "page",
    "AGE_SP": "sage",
    "FILESTAT": "mstat",
    "SOI_ST": "state",
    "DEPCNT": "depx",
    "DEPUND13": "dep13",
    "DEPUND17": "dep17",
    "DEPUND18": "dep18",
    "WAGE_HD": "pwages",
    "WAGE_SP": "swages",
    "DIVINC": "dividends",
    "OTHTXINC": "otherprop",
    "TAXPENS": "pensions",
    "SOSSECB": "gssi",
    "NONTXINC": "transfers",
    "RNTPAID": "rentpaid",
    "PROPTXPD": "proptax",
    "AMTDEDCT": "otheritem",
    "CHLDCARE": "childcare",
    "OTHDEDCT": "mortgage",
}
INT_INPUTS = ["page", "sage", "mstat", "state", "depx", "dep13", "dep17", "dep18"]
TAXSIM_COLUMNS = ["taxsimid", "year"] + list(INPUT_MAP.values()) + ["idtl"]

SOI = (
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()


def build(ce_dir, out_dir):
    """NTAXI rows -> one TAXSIM input record per (tax unit, tax year >= 2021)."""
    frames = []
    for path in sorted(glob.glob(os.path.join(ce_dir, "intrvw*", "ntaxi*.csv"))):
        df = pd.read_csv(path, dtype={"NEWID": str})
        df["pumd_year"] = 2000 + int(Path(path).parent.name[-2:])
        df["qfile"] = Path(path).stem
        frames.append(df)
    if not frames:
        sys.exit(f"No intrvw*/ntaxi*.csv files under {ce_dir}")
    ntaxi = pd.concat(frames, ignore_index=True)
    weights = pd.concat(
        [
            pd.read_csv(p, usecols=["NEWID", "FINLWT21"], dtype={"NEWID": str})
            for p in sorted(glob.glob(os.path.join(ce_dir, "intrvw*", "fmli*.csv")))
        ],
        ignore_index=True,
    ).drop_duplicates("NEWID")
    ntaxi = ntaxi.merge(weights, on="NEWID", how="left")

    inputs, published = [], []
    for period in ("CY", "PY"):
        rows = ntaxi[ntaxi[f"TAXYR_{period}"] >= 2021].reset_index(drop=True)
        inp = pd.DataFrame({"year": rows[f"TAXYR_{period}"].astype(int)})
        for ce_col, ts_col in INPUT_MAP.items():
            inp[ts_col] = rows[ce_col].astype(float)
        inp[INT_INPUTS] = inp[INT_INPUTS].astype(int)
        inp["idtl"] = 2
        pub = rows[
            ["NEWID", "TAX_UNIT", "pumd_year", "qfile", "SOI_ST", "FINLWT21"]
        ].copy()
        pub["period"] = period
        pub["tax_year"] = inp["year"]
        pub["fiitax"] = rows[f"FTAXO_{period}"].astype(float)
        pub["siitax"] = rows[f"STAXO_{period}"].astype(float)
        inputs.append(inp)
        published.append(pub)
    inp = pd.concat(inputs, ignore_index=True)
    pub = pd.concat(published, ignore_index=True)
    inp.insert(0, "taxsimid", np.arange(1, len(inp) + 1))
    pub.insert(0, "taxsimid", inp["taxsimid"])
    os.makedirs(out_dir, exist_ok=True)
    inp[TAXSIM_COLUMNS].to_csv(os.path.join(out_dir, "inputs.csv"), index=False)
    pub.to_csv(os.path.join(out_dir, "bls_outputs.csv"), index=False)
    print(f"{len(inp):,} records:", inp["year"].value_counts().sort_index().to_dict())


def _taxsim_executable():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

    runner = TaxsimRunner.__new__(TaxsimRunner)
    return str(runner._detect_taxsim_executable())


def taxsim(out_dir, chunk=2000):
    """Run taxsimtest on the raw inputs (it accepts dep13/dep17/dep18) in
    chunks, bisecting any chunk that crashes or hangs so only the offending
    records are dropped; their taxsimids go to taxsimtest_failed.csv."""
    exe = os.path.abspath(_taxsim_executable())
    inp = pd.read_csv(os.path.join(out_dir, "inputs.csv"))
    tmp = tempfile.mkdtemp()
    failed = []

    def run(df):
        fin, fout = os.path.join(tmp, "in.csv"), os.path.join(tmp, "out.csv")
        df.to_csv(fin, index=False)
        try:
            with open(fin) as i, open(fout, "w") as o:
                done = subprocess.run(
                    [exe],
                    stdin=i,
                    stdout=o,
                    stderr=subprocess.DEVNULL,
                    timeout=max(30, len(df) / 20),
                )
        except subprocess.TimeoutExpired:
            return None
        if done.returncode != 0:
            return None
        # Keep the header and numeric rows; the binary can print notes and
        # d3/d4 debug lines on stdout.
        lines = [
            line
            for line in open(fout)
            if line.startswith("taxsimid") or (line[:1].isdigit() and "," in line)
        ]
        res = pd.read_csv(io.StringIO("".join(lines)))
        res = res[[c for c in res.columns if not c.startswith("cd")]]
        return res if len(res) == len(df) else None

    def run_or_bisect(df):
        res = run(df)
        if res is not None:
            return [res]
        if len(df) == 1:
            failed.append(int(df["taxsimid"].iloc[0]))
            return []
        half = len(df) // 2
        return run_or_bisect(df.iloc[:half]) + run_or_bisect(df.iloc[half:])

    parts = []
    for start in range(0, len(inp), chunk):
        parts += run_or_bisect(inp.iloc[start : start + chunk])
    pd.concat(parts, ignore_index=True).to_csv(
        os.path.join(out_dir, "taxsimtest.csv"), index=False
    )
    pd.Series(failed, name="taxsimid").to_csv(
        os.path.join(out_dir, "taxsimtest_failed.csv"), index=False
    )
    print(f"taxsimtest: {len(inp) - len(failed):,} records, {len(failed)} failed")


def emulator(out_dir, label, year):
    from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

    inp = pd.read_csv(os.path.join(out_dir, "inputs.csv"))
    inp = inp[inp["year"] == year]
    res = PolicyEngineRunner(inp, logs=False).run(show_progress=False)
    res.to_csv(os.path.join(out_dir, f"emulator_{label}_{year}.csv"), index=False)
    print(f"emulator {label} {year}: {len(res):,} records")


def _outputs(path_or_glob):
    frames = [pd.read_csv(p) for p in sorted(glob.glob(path_or_glob))]
    df = pd.concat(frames, ignore_index=True)
    df["taxsimid"] = df["taxsimid"].astype(float).astype(int)
    return df.set_index("taxsimid")


def merged(out_dir, labels):
    df = pd.read_csv(os.path.join(out_dir, "bls_outputs.csv"), dtype={"NEWID": str})
    df = df.set_index("taxsimid")
    sources = {"taxsimtest": _outputs(os.path.join(out_dir, "taxsimtest.csv"))}
    for label in labels:
        sources[label] = _outputs(os.path.join(out_dir, f"emulator_{label}_*.csv"))
    # BLS's 2021 PUMD current-year FTAXO excludes the 2021 recovery rebate:
    # it matches taxsimtest `fiitax + cares`, not `fiitax`. Every other
    # release includes the rebate. Put all sources on BLS's basis.
    pre_rebate = (df["pumd_year"] == 2021) & (df["period"] == "CY")
    for name, out in sources.items():
        out = out.reindex(df.index)
        df[f"fiitax_{name}"] = out["fiitax"] + np.where(
            pre_rebate, out["cares"].fillna(0), 0
        )
        df[f"siitax_{name}"] = out["siitax"]
    df["st"] = df["SOI_ST"].map(lambda s: SOI[s - 1] if 1 <= s <= 51 else "(none)")
    df["w"] = df["FINLWT21"] / 4
    df["release"] = df["pumd_year"].astype(str) + " " + df["period"]
    return df


def _within(df, tax, source, ref, tol=10):
    s = df[tax] if source == "bls" else df[f"{tax}_{source}"]
    r = df[tax] if ref == "bls" else df[f"{tax}_{ref}"]
    ok = s.notna() & r.notna()
    return ((s - r)[ok].abs() <= tol).mean()


def _md(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def report(out_dir, labels):
    df = merged(out_dir, labels)
    sources = ["taxsimtest"] + labels
    rows = []
    for (ty, rel), g in df.groupby(["tax_year", "release"]):
        row = [ty, rel, f"{len(g):,}"]
        row += [
            f"{100 * _within(g, t, s, 'bls'):.1f}%"
            for t in ("fiitax", "siitax")
            for s in sources
        ]
        rows.append(row)
    print("Share within $10 of BLS's published outputs\n")
    print(
        _md(
            ["Tax year", "BLS file (period)", "Records"]
            + [f"{t}: {s}" for t in ("Federal", "State") for s in sources],
            rows,
        )
    )
    last = labels[-1] if labels else "taxsimtest"
    rows = []
    for st, g in df.groupby("st"):
        row = [st, f"{len(g):,}"]
        for t in ("fiitax", "siitax"):
            for ty in sorted(df["tax_year"].unique()):
                gy = g[g["tax_year"] == ty]
                row.append(
                    f"{100 * _within(gy, t, last, 'bls'):.1f}%" if len(gy) else ""
                )
        rows.append(row)
    years = sorted(df["tax_year"].unique())
    print(f"\nBy state and tax year ({last} vs BLS, share within $10)\n")
    print(
        _md(
            ["State", "Records"]
            + [f"{t} {y}" for t in ("Federal", "State") for y in years],
            rows,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="step", required=True)
    b = sub.add_parser("build")
    b.add_argument("ce_dir")
    b.add_argument("out_dir")
    t = sub.add_parser("taxsim")
    t.add_argument("out_dir")
    e = sub.add_parser("emulator")
    e.add_argument("out_dir")
    e.add_argument("--label", required=True)
    e.add_argument("--year", type=int, required=True)
    r = sub.add_parser("report")
    r.add_argument("out_dir")
    r.add_argument("--label", action="append", default=[])
    args = parser.parse_args()
    if args.step == "build":
        build(args.ce_dir, args.out_dir)
    elif args.step == "taxsim":
        taxsim(args.out_dir)
    elif args.step == "emulator":
        emulator(args.out_dir, args.label, args.year)
    else:
        report(args.out_dir, args.label)


if __name__ == "__main__":
    main()
