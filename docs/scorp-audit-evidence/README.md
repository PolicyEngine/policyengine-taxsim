# Audit evidence

`cases.json.gz` contains:

- Five yearly alignment summaries (3,000 identical sampled households/year).
- All federal/state relative failures and all EITC/state outputs changed by the passive switch, with input and TAXSIM/active/passive output rows.
- Forty-eight synthetic/actual probes per year, plus extended 2025 AMT/payroll probes.

Read with Python's standard library; no PE model installation is necessary:

```python
import gzip, json
with gzip.open("docs/scorp-audit-evidence/cases.json.gz", "rt") as f:
    audit = json.load(f)
print(audit["years"]["2025"]["summary"]["stateCounts"])
```

Source runs: 35685604478, 35685926063, 35687204125. Underlying behavior tested is PR #1199 commit e7b62028; diagnostic branches add output inspection only. PE-US 2.6.17.

The raw `firstDifference` classification uses a $1 threshold and can classify float32 rounding at extreme incomes as an AGI discrepancy. Use the report and full output records to investigate causes. Raw `v13` is not a reliable itemization flag in every TAXSIM year. No category in this inventory is automatically cleared for a parity fix.
