# S-corp end-to-end validation

The `S-corp end-to-end alignment` workflow uses the bundled TAXSIM executable.
It exercises the installed CLI, stdin mode and local FastAPI `/run` and
`/run/stream` endpoints with real model calculations. API tests do not deploy
an endpoint, call the pre-2021 remote fallback, send email or subscribe anyone.

It runs on manual dispatch and on pull requests that change the workflow, the
alignment script, the interface tests, the S-corp classification
(`policyengine_taxsim/core/scorp.py` and `scorp_reform.py`), the refresh code
the alignment script reuses (`scripts/refresh_dashboard.py`), the environment
check (`scripts/check_pinned_environment.py`) or the pinned dashboard
requirements. Other code on the S-corp path (the runners, CLI, API and variable
mappings) does not trigger it; the `scorp-validation` job in the main CI
workflow runs the S-corp unit tests for every pull request, including on the
dashboard pin. Dispatch this workflow manually to check such a change end to
end.

## policyengine-us versions covered

Every job runs on two policyengine-us releases:

- **`dashboard-pin`**: the locked dashboard refresh environment in
  `scripts/dashboard-refresh-requirements.txt`, which pins policyengine-us
  2.6.17. That release predates the EITC investment-income fix in 2.10.1
  (pe-us#9572), so these jobs run with the emulator's backport of it
  (`policyengine_taxsim/core/scorp_reform.py`). Python, requirements, install
  steps and refresh flags match the dashboard refresh. After installing
  (including the interface job's test-only packages: pytest, modal, fastapi
  and httpx), the job runs `pip check` and fails if any installed package
  differs from its pin.
- **`latest`**: the same requirements with policyengine-us upgraded to the
  newest release (2.10.1 or later, along with whatever dependencies it
  requires), where the native formula runs unchanged. It runs `pip check` and
  reports the installed policyengine-us and policyengine-core versions.

One interface case (wages $8,000, interest $12,500 and an S-corp loss of
$6,000, in 2025) checks the backport end to end. TAXSIM gives no EITC, and
neither does PE on either release. Without the backport, PE on the pin nets the
loss against the interest, which brings investment income under the $11,950
limit, and gives a $352.18 EITC: the $649 maximum less 7.65% of the $3,880 of
AGI above $10,620 (26 USC 32(a)(2); Rev. Proc. 2024-40, section 3.06). The
three passive-mode interface tests then fail.

Releases that Python 3.10 resolves (policyengine-us 1.x, which also lack the
passive input) are not run end to end here. The `scorp-validation` job runs the
S-corp unit tests on them.

## Sample alignment

Each year job recomputes the same 3,000 dashboard sample households in active
and passive modes, keeping the W-2 assumption enabled in both. Fresh workers
process 500 rows at a time under the existing 5 GiB RSS / 4 GiB disk guards.
There are ten sample jobs, five years on each release, and at most four run
concurrently. Seven-day JSON artifacts (`scorp-alignment-<year>-<release>`)
contain the policyengine-us and policyengine-core versions, match counts,
resource use, gains/losses in federal matches and the largest remaining
residuals. These are sample results, not full-population estimates.
The workflow does not publish or modify the dashboard.

## Separate payroll discrepancy

The bundled TAXSIM reports $39,118.20 FICA for a single 2025 filer with $300,000
wages. PE reports $31,436.40 in both S-corp modes. The $7,681.80 difference is
exactly 6.2% of wages above the $176,100 Social Security wage base, consistent
with an uncapped employer component in this TAXSIM output. This is independent
of the NIIT classification switch and is explicitly accounted for in the
interface assertions; NIIT, federal income tax, QBI, AGI and the EITC still require
agreement with TAXSIM (or the expected active-mode NIIT difference).

PE's figure follows two capped 6.2% Social Security contributions, two uncapped
1.45% Medicare contributions, and the employee-only $900 Additional Medicare
Tax. We do not change this payroll treatment to match the binary.

Sources: [SSA contribution base](https://www.ssa.gov/oact/COLA/cbb.html),
[IRS Medicare rates](https://www.irs.gov/publications/p15),
[IRS Additional Medicare Tax](https://www.irs.gov/taxtopics/tc560),
[TAXSIM output definitions](https://taxsim.nber.org/taxsimtest/).
