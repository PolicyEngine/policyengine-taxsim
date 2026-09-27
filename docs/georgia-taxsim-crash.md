# Georgia TAXSIM crash during the 2024 smoke test

The September Linux binary (`cd2026090910`, SHA256
`8aa880aeea33fd501f669d42125615e3b2a0ab19c17d93a76457e9de16615059`)
crashed in `gatax24` at `taxsim.f:8120` during
[run 35945130451](https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35945130451).

The fault address is `0x4baf37`. Disassembly shows a floating-point addition
reading stack offset `-0x60(%rbp)`. The binary's DWARF information identifies
that location (CFA offset -112) as local double `old`, first declared at line
8120. The routine contains no write to that stack location before reading it.
This is the low-income credit expression, which adds `old` to the filer and
dependent counts. The published September 23 source initializes `old` from
`d(9)+d(10)` immediately before this expression; the September 9 binary does
not. Source: https://taxsim.nber.org/out2psl/taxsim.f . The source file is not
redistributed here.

This is an execution defect in native TAXSIM. It does not establish that
PolicyEngine's Georgia tax calculation is legally correct or incorrect.

The recovery workflow uses the hash-pinned previous binary for Georgia and
Maryland in 2024–2025, records each TAXSIM row's binary hash, and preserves the
verified 2021–2023 artifacts. A preflight executes every remaining TAXSIM batch
before expensive PolicyEngine calculations. The preflight artifact retains the
reduced Georgia input and previous-binary output.

The hosted diagnostic reduced the crash to two records: North Carolina taxsimid
23725 followed by Georgia taxsimid 26161. The previous binary completes the
same pair. The input is committed at
`tests/fixtures/georgia_taxsim_crash/2024.csv`.
[Preflight run](https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35953332152)
validated all 111,347 tax units in each of 2024 and 2025 using the fallbacks.
