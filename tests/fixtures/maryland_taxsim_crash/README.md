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

## Source-level diagnosis

A native GDB run of the September 9 Linux binary stops at address `0x498c9b`,
`mdtax22`, `taxsim.f:14163`. The faulting instruction is a scalar double
subtraction from an uninitialized local stack operand. GDB reports:

- `subh = 4.2439915834127416e-314`
- `subw = 6.3659873728958169e-314`
- `subt = 6782.1240234374645`
- `subs = 0`

The current publisher-hosted source (https://taxsim.nber.org/out2psl/taxsim.f,
header build 2026092316, retrieved 2026-09-23 America/New_York, SHA256
`e6831b5726ff0b6d94dfddd804370e5174609616faeba39da3ab1f5c62e24e1f`)
contains the same two-income subtraction branch at lines 14356–14357. It
computes pension exclusions in `subt` and `subs`, but subtracts `subh` and
`subw`, which have no initialization or assignment in `mdtax22`. The line
numbers differ because this published source is newer than the tested binary.
The source itself is not redistributed here.

The affected branch requires joint filing, exactly one elderly taxpayer and
a positive pension exclusion. Removing every other financial input still
reproduces the crash. Reversing the two records, running either alone, or
running the Maryland record twice succeeds. Other preceding states can also
trigger it; this is not a Delaware tax-rule problem.

Debugger evidence: https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35944272752
Controlled runtime-correction experiment is implemented in
`scripts/pinpoint_maryland_taxsim.py`; it changes only the two local operands
before the faulting expression, leaving the executable file unmodified.
