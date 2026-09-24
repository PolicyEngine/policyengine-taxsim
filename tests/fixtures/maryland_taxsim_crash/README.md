# September Linux TAXSIM batch-dependent Maryland crash

These two-record inputs were reduced from ECPS source rows 75,000–79,999 by
`scripts/diagnose_maryland_taxsim.py`. TAXSIM IDs 76239 (Delaware) followed by
76431 (Maryland) reproduce SIGFPE in `mdtax22_`, `taxsim.f:14163`, for both years
with Linux build cd2026090910, SHA256
`8aa880aeea33fd501f669d42125615e3b2a0ab19c17d93a76457e9de16615059`.

```sh
ulimit -c 0
resources/taxsimtest/taxsimtest-linux.exe < tests/fixtures/maryland_taxsim_crash/2024.csv
```

The previous Linux binary (SHA256
`00a321d2467ba011992f8b83c6e485a9b710c48fca4262a23fec1de26942a89b`)
completes both fixtures. It also returns all 1,310 Maryland inputs with finite
federal/state/rebate outputs in each year. Running all Maryland inputs alone
with the new Linux binary succeeds too, so the failure depends on batch
context. The new macOS binary completes these two-record fixtures.

Evidence: https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35943808341
Tracking issue: https://github.com/PolicyEngine/policyengine-taxsim/issues/1214

This demonstrates an execution regression, not which Maryland tax formula is
legally correct. Cross-record state leakage is a hypothesis; the exact upstream
arithmetic expression has not been inspected.
