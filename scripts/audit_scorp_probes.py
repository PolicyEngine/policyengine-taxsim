"""Hosted-only diagnostic probes; never changes production calculations."""

import argparse
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
VARIABLES = """irs_gross_income above_the_line_deductions loss_ald limited_capital_loss
self_employment_tax_ald qualified_business_income qbid_amount
adjusted_net_capital_gain net_capital_gain taxable_income_less_qbid
net_investment_income state_and_local_sales_or_income_tax state_withheld_income_tax
state_sales_tax itemized_taxable_income_deductions tax_unit_itemizes
income_tax_before_credits income_tax_main_rates capital_gains_tax
employee_social_security_tax employer_social_security_tax employee_medicare_tax
employer_medicare_tax additional_medicare_tax self_employment_tax
partnership_s_corp_income total_self_employment_income""".split()


def cases(year):
    from refresh_dashboard import INPUT_COLUMNS

    probes = []

    def add(label, **values):
        row = dict.fromkeys(INPUT_COLUMNS, 0)
        row.update(year=year, state=0, mstat=1, page=45, idtl=2)
        row.update(values)
        row["taxsimid"] = 900000 + len(probes)
        if row["mstat"] == 2:
            row["sage"] = 45
        probes.append((label, row))

    for wages in (100000, 176100, 200000, 300000):
        add(f"wages-{wages}", pwages=wages)
    for joint in (False, True):
        for field in ("scorp", "psemp"):
            add(
                f"loss-{field}-joint-{joint}",
                mstat=2 if joint else 1,
                pwages=1000000,
                **{field: -1000000},
            )
    for st in (0, 5, 22, 33, 44):
        for mortgage in (0, 50000):
            add(
                f"niit-state-{st}-mortgage-{mortgage}",
                state=st,
                pwages=300000,
                intrec=100000,
                mortgage=mortgage,
            )
    for p, s, sc in (
        (200000, -100000, 0),
        (100000, 0, 0),
        (500000, -100000, -200000),
        (100000, 0, 100000),
        (0, 0, 200000),
        (200000, 0, 0),
        (0, 200000, 0),
    ):
        add(f"qbi-{p}-{s}-{sc}", mstat=2, pwages=400000, psemp=p, ssemp=s, scorp=sc)
    for stcg, ltcg in (
        (0, 100000),
        (-50000, 100000),
        (-150000, 100000),
        (100000, 0),
        (100000, -50000),
    ):
        add(f"capital-{stcg}-{ltcg}", pwages=300000, scorp=200000, stcg=stcg, ltcg=ltcg)
    ids = {
        107775,
        58240,
        104699,
        69124,
        105500,
        111323,
        111870,
        59073,
        59956,
        57982,
        79371,
        65315,
        53450,
        90818,
        77471,
        58607,
        62073,
        80598,
    }
    with (
        ROOT / f"dashboard/public/data/{year}/comparison_results_{year}.csv"
    ).open() as f:
        for r in csv.DictReader(f):
            if r["source"] == "taxsim" and int(float(r["taxsimid"])) in ids:
                probes.append(
                    (
                        f"actual-{int(float(r['taxsimid']))}",
                        {k: r.get(k, 0) for k in INPUT_COLUMNS},
                    )
                )
    return probes


def worker(year, output):
    sys.path.insert(0, str(ROOT))
    import pandas as pd
    from policyengine_taxsim.runners import PolicyEngineRunner, TaxsimRunner

    class InspectRunner(PolicyEngineRunner):
        def _extract_vectorized_results(
            self, sim, input_df, rebate_free_sim_factory=None
        ):
            result = super()._extract_vectorized_results(
                sim, input_df, rebate_free_sim_factory
            )
            for var in VARIABLES:
                if var in sim.tax_benefit_system.variables:
                    result["pe_" + var] = self._calc_tax_unit(sim, var, str(year))
            p = sim.tax_benefit_system.parameters(str(year)).gov.irs.ald.loss.max
            result["pe_loss_limit"] = [
                float(p.JOINT if int(m) == 2 else p.SINGLE) for m in input_df.mstat
            ]
            return result

    probes = cases(year)
    labels = {int(float(r["taxsimid"])): name for name, r in probes}
    data = pd.DataFrame([r for _, r in probes])
    for col in data:
        data[col] = pd.to_numeric(data[col]).fillna(0)
    ts = (
        TaxsimRunner(data.copy())
        .run(show_progress=False)
        .set_index("taxsimid")
        .to_dict("index")
    )
    pe = (
        InspectRunner(data.copy(), assume_w2_wages=True, scorp_treatment="passive")
        .run(show_progress=False)
        .set_index("taxsimid")
        .to_dict("index")
    )
    report = []
    for row in data.to_dict("records"):
        key = int(row["taxsimid"])
        report.append(
            dict(label=labels[key], input=row, taxsim=ts[key], policyengine=pe[key])
        )
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{year}: {len(report)} probes completed", flush=True)
    os._exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    output = ROOT / f"validation/probes-{args.year}.json"
    if args.worker:
        worker(args.year, output)
        return
    import psutil

    child = subprocess.Popen(
        [sys.executable, __file__, "--year", str(args.year), "--worker"],
        start_new_session=True,
    )
    start = time.monotonic()
    peak = 0
    try:
        while child.poll() is None:
            try:
                p = psutil.Process(child.pid)
                rss = p.memory_info().rss + sum(
                    c.memory_info().rss
                    for c in p.children(recursive=True)
                    if c.is_running()
                )
            except psutil.NoSuchProcess:
                rss = 0
            peak = max(peak, rss)
            if rss > 5 * 1024**3 or time.monotonic() - start > 900:
                raise RuntimeError("Probe worker exceeded memory/time guard")
            time.sleep(2)
        if child.returncode:
            raise RuntimeError(f"Probe worker exited {child.returncode}")
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    print(f"Peak RSS {peak / 1024**2:.0f} MiB", flush=True)


if __name__ == "__main__":
    main()
