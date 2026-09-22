"""Read-only, stdlib tax-form checks; no PE model execution or installation."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(binary):
    evidence = json.load(gzip.open(ROOT / 'docs/scorp-audit-evidence/cases.json.gz', 'rt'))
    x = next(x for x in evidence['extra2025Probes'] if x['label'] == 'actual-53450')
    i = x['input']
    # 2025 1040 QDCG worksheet and Form 6251 Part III. No foreign tax,
    # investment-interest election, 28% gains, section 1250 gains or QBI.
    gain = i['ltcg'] + i['dividends']
    agi = sum(i[k] for k in ['ltcg', 'stcg', 'dividends', 'intrec', 'pensions']) + .85 * i['gssi']
    taxable = agi - 17750
    ordinary = taxable - gain
    capital_tax = (533400 - ordinary) * .15 + (gain - (533400 - ordinary)) * .20
    regular = ordinary * .35 - 30452.75 + capital_tax
    tentative = (agi - gain) * .28 - 4782 + capital_tax
    manual = {'agi': agi, 'qualifiedDividendsPlusLTCG': gain,
              'ordinaryTaxableIncome': ordinary, 'regularTax': regular,
              'tentativeMinimumTax': tentative, 'amt': tentative - regular,
              'peAMT': x['policyengine']['v27'], 'taxsimAMT': x['taxsim']['v27']}
    assert round(manual['amt'], 2) == 9131.71
    # The IRS worksheet requires the passive basket to be floored before
    # adding interest and dividends, not after all income types are combined.
    inv = 7147.17236328125 + 12442.6064453125 + max(0, -3748790.875)
    assert inv > 10000
    def calc(**kw):
        row = dict(taxsimid=1, year=2025, state=0, mstat=1, page=35,
                   sage=0, depx=0, age1=0, pwages=0, psemp=0, ssemp=0,
                   scorp=0, idtl=2)
        row.update(kw)
        f = io.StringIO(); w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader(); w.writerow(row)
        p = subprocess.run([str(binary)], input=f.getvalue(), text=True,
                           capture_output=True, check=True, timeout=15)
        result = next(csv.DictReader(io.StringIO(p.stdout)))
        return {'input': row, 'output': {k.strip(): float(v) for k, v in result.items()}}
    cases = {
        'payroll_300k': calc(pwages=300000),
        'se_under_400_net': calc(psemp=404.319),
        'qbi_cross_business_loss': calc(pwages=400000, psemp=-50000, scorp=200000),
        'child_baseline': calc(pwages=10000, depx=1, age1=8),
        'child_scorp_loss': calc(pwages=10000, depx=1, age1=8, scorp=-5000),
        'odc_2021': calc(year=2021, depx=1, age1=18),
    }
    for year in range(2021, 2026):
        cases[f'loss_{year}'] = calc(year=year, pwages=1000000, psemp=-1000000)
    result = {'binarySHA256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'manual2025AMT': manual, 'eitcInvestmentIncomeMinimum': inv,
              '2025StatutoryFICA300kWages': 2 * .062 * 176100 + 2 * .0145 * 300000 + .009 * 100000,
              'cases': cases}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
