# S-corp end-to-end validation

The `S-corp end-to-end alignment` workflow uses the pinned dashboard model
environment and the bundled TAXSIM executable. It exercises the installed CLI,
stdin mode and local FastAPI `/run` and `/run/stream` endpoints with real model
calculations. API tests do not deploy an endpoint, call the pre-2021 remote
fallback, send email or subscribe anyone.

Each year job recomputes the same 3,000 dashboard sample households in active
and passive modes, keeping the W-2 assumption enabled in both. Fresh workers
process 500 rows at a time under the existing 5 GiB RSS / 4 GiB disk guards.
At most two sample jobs run concurrently. Seven-day JSON artifacts contain
match counts, resource use, gains/losses in federal matches and the largest
remaining residuals. These are sample results, not full-population estimates.
The workflow does not publish or modify the dashboard.

## Separate payroll discrepancy

The bundled TAXSIM reports $39,118.20 FICA for a single 2025 filer with $300,000
wages. PE reports $31,436.40 in both S-corp modes. The $7,681.80 difference is
exactly 6.2% of wages above the $176,100 Social Security wage base, consistent
with an uncapped employer component in this TAXSIM output. This is independent
of the NIIT classification switch and is explicitly accounted for in the
interface assertions; NIIT, federal income tax, QBI and AGI still require
agreement with TAXSIM (or the expected active-mode NIIT difference).

PE's figure follows two capped 6.2% Social Security contributions, two uncapped
1.45% Medicare contributions, and the employee-only $900 Additional Medicare
Tax. We do not change this payroll treatment to match the binary.

Sources: [SSA contribution base](https://www.ssa.gov/oact/COLA/cbb.html),
[IRS Medicare rates](https://www.irs.gov/publications/p15),
[IRS Additional Medicare Tax](https://www.irs.gov/taxtopics/tc560),
[TAXSIM output definitions](https://taxsim.nber.org/taxsimtest/).
