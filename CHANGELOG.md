## [2.26.10] - 2026-07-01

### Fixed

- Route MFJ pension to the older spouse when spouses straddle the state's pension-exclusion age (GA 62, default 55), instead of a flat 55 that stranded the exclusion for a GA 65/61 couple. Scoped to the pension field; gssi keeps the default age.


## [2.26.9] - 2026-06-24

### Fixed

- Description: Zero PE's imputed Medicare Part B premiums (medical_expense_health_insurance_premiums) so they don't inflate state medical exemptions/deductions, restoring TAXSIM/TaxAct parity for elderly itemizers (MA, OK, OH).


## [2.26.8] - 2026-06-23

### Changed

- Document the MFJ spousal income allocation rule (50/50 for interest/dividends/capital gains/S-corp; age-aware for pensions and Social Security) and its TAXSIM-alignment caveats on the dashboard Variable Mappings (input) page.


## [2.26.7] - 2026-06-23

### Fixed

- Fix both-young MFJ pension/Social Security split: the Microsimulation runner now splits these 50/50 when both spouses are on the same side of the elderly-eligibility line (previously it dumped them on the primary filer when both were under the threshold), restoring per-person state exclusions for age-independent states (e.g. KY, OK). Mixed-age allocation to the older spouse is unchanged.


## [2.26.6] - 2026-06-23

### Fixed

- Fix --disable-salt to exclude state income tax from the federal SALT deduction, matching TAXSIM-35 (which deducts mortgage interest and property tax federally but not state income tax). The previous three-pass re-introduced the computed state tax as fixed federal SALT, overshooting TAXSIM by the full state-tax amount on every itemizing record. On a 60-record itemizing sample this cut the mean federal mismatch from ~$1,185 (0/60 within $15) to $0 (60/60 exact).


## [2.26.5] - 2026-06-22

### Changed

- Recolor the PolicyEngine favicon/app icon from the legacy blue mark to the current teal brand, keeping the white rounded-card frame.

### Fixed

- Fix the dashboard favicon: prefix the icon path with the basePath so the PolicyEngine icon resolves under /us/taxsim instead of 404ing at the domain root.


## [2.26.4] - 2026-06-22

### Changed

- Redesign the validation dashboard with an instrument-readout visual language: a deep-teal console hero stating the live result, JetBrains Mono tabular figures for all metrics, and a calibration color scale that surfaces diverging states.


## [2.26.3] - 2026-06-22

### Changed

- Default the validation dashboard to the 1%-of-income tolerance, serve precomputed full-eCPS summary metrics, and link full per-year comparison CSVs from a GitHub Release.


## [2.26.2] - 2026-06-22

### Fixed

- Cap TAXSIM dependent age columns at age10 (age11+ is rejected by taxsimtest with STOP 901), allowing comparison runs that include records with 11+ dependents.


## [2.26.1] - 2026-06-04

### Fixed

- Stop adding the Additional Medicare Tax (Form 8959) to `fiitax` so PE's output aligns with NBER TAXSIM-35 (`taxsimtest`), which reports AddMed in the separate `addmed` column per Form 1040 Line 23 / Schedule 2 Line 11. The prior behavior caused PE to overshoot TAXSIM by ~$412K (95% of the remaining federal mismatch) on the eCPS n=2000 TY 2025 sample. AddMed continues to flow through the `v44` output (`employee_medicare_tax + additional_medicare_tax`).


## [2.26.0] - 2026-06-04

### Added

- Bump `policyengine-us` to `>=1.711.0` (picks up the upstream fix that unwires UT Homeowner/Renter Relief from TC-40 refundable credits, per Utah Tax Commission TC-90CB/TC-90H). Add integration test pinning the TAXSIM `otherprop` → PE-US `rental_income` + NIIT routing against IRC § 1411(c)(1)(A)(i) and the TAXSIM-35 binary.


## [2.25.1] - 2026-06-04

### Fixed

- Route TAXSIM `otherprop` to PE-US `rental_income` so passive rents/royalties enter the NIIT base, and suppress the auto-QBID gate to match TAXSIM's convention.


## [2.25.0] - 2026-06-03

### Added

- Dashboard match-rate toggle for ±$15 vs ±1%-of-gross-income tolerance.


## [2.24.0] - 2026-06-02

### Added

- TaxsimRunner now passes through `opt1` and `opt1v` columns to the TAXSIM-35 binary, enabling callers to toggle TAXSIM behaviors (e.g., `opt1=30, opt1v=1` switches one-time rebate timing to PE's liability-year convention).


## [2.23.1] - 2026-06-02

### Fixed

- PolicyEngineRunner now sets `mn_renters_credit_qualifying_crp = True` for MN tax units with `rentpaid > 0`, matching Minn. Stat. § 290.0693 (the CRP is documentation, not a substantive eligibility gate).


## [2.23.0] - 2026-05-29

### Added

- Add 2025 comparison results to the dashboard (3,000-record eCPS sample).


## [2.22.0] - 2026-05-28

### Added

- Restore `idtl=5` (TAXSIM full-text labeled-section output) to the cli stdin/stdout flow. Previously only the legacy `exe.py` entry point handled it; current cli always emitted CSV. Mixed-idtl inputs interleave labeled-text and CSV rows in original input order.


## [2.21.12] - 2026-05-28

### Fixed

- Lower the pension/SS age-aware split threshold from 60 to 55 to match Colorado's 55+ pension subtraction (so mixed-age couples ages 55-59 each claim the state per-person exclusion). Higher-threshold states (DE 60, GA 62, MD 65) are unaffected.
- Run `--disable-salt` in three passes so PE's federal Schedule A keeps state-tax SALT (matching TAXSIM-35's single-pass methodology) while state computation remains SALT-disabled. Eliminates the iterated-vs-single-pass state-tax mismatch in PE-vs-TAXSIM federal comparisons.


## [2.21.11] - 2026-05-27

### Fixed

- Map the TAXSIM `otherprop` input to PE-US `miscellaneous_income` so "Other Property" income flows into federal AGI (previously silently dropped).


## [2.21.10] - 2026-05-26

### Fixed

- Update bundled macOS TAXSIM-35 binary to a build that supports TY 2025 (previously failed with `STOP 1`).


## [2.21.9] - 2026-05-26

### Fixed

- Route CLI status messages (dataset setup, microsim progress, "Results saved") to stderr so they don't contaminate piped CSV output on stdout.


## [2.21.8] - 2026-05-25

### Changed

- Suppress benign Hugging Face Hub anonymous-request warnings during CLI runs.

### Fixed

- Allocate Social Security (`gssi`) using the same age-aware rule as pensions: in mixed-age MFJ households, keep the full amount on the primary filer so state per-person SS exclusions (CO, MD, etc.) reach the qualifying spouse.


## [2.21.7] - 2026-05-25

### Fixed

- Allow duplicate `taxsimid` values in input data to support TAXSIM-35 panel and multi-state workflows.


## [2.21.6] - 2026-05-14

### Fixed

- Strip whitespace from CSV column headers on input so columns with leading/trailing spaces (e.g. ` ltcg ,`) are recognized rather than silently dropped, matching what TAXSIM-style users expect.


## [2.21.5] - 2026-05-14

### Fixed

- Fix v32 (State AGI) output returning $0 for Montana — route `taxsim_v32_state_agi` to `mt_agi_joint` (the tax-unit-level MT AGI that applies to joint, single, and HoH filers) instead of the default `state_agi` path, which reads the person-level `mt_agi_indiv` (defined only for MFS-on-same-return) and returns 0 for everyone else.


## [2.21.4] - 2026-05-12

### Changed

- Add comment-style guidance to /diagnose-issue Step 9: phrase findings as questions, link primary sources (statute / Rev. Proc. / GitHub permalinks to PE variables), anchor claims to code not assertion.
- Add Step 6 input-parity warning to /diagnose-issue skill: when running direct Simulation, map every non-zero TAXSIM input from txpydata.csv before drawing conclusions. Includes the TAXSIM-to-PE variable cross-walk.


## [2.21.3] - 2026-05-11

### Changed

- Audit and tighten the /diagnose-issue slash command: add Step 0 pre-triage (Q-vs-bug / version compare / existing PE-US tracking), require primary-source fetches for credit/deduction disagreements, mandate direct PE queries (no inference), and drop stale references.


## [2.21.2] - 2026-05-09

### Changed

- Migrated dashboard from `@policyengine/design-system` to `@policyengine/ui-kit/legacy`.


## [2.21.1] - 2026-04-28

### Changed

- Updated GitHub Actions workflows for Node 24-compatible action runtimes.


## [2.21.0] - 2026-04-23

### Removed

- Remove `exe.py` PyInstaller entry point and `.spec` file — unused standalone-binary build path. The `export_household` / `generate_household` helpers stay (still used by `tests/test_state_output_adapters.py`).


## [2.20.1] - 2026-04-23

### Changed

- Unify `sctc` output adapter to use pe-us `state_ctc` aggregate (gov.states.household.state_ctcs) instead of duplicated per-state mapping. OK/MN component-split overrides are preserved in the resolver.


## [2.20.0] - 2026-04-21

### Added

- Map TAXSIM pprofinc/sprofinc inputs to PolicyEngine sstb_self_employment_income for per-category SSTB QBID computation.


## [2.19.1] - 2026-04-20

### Fixed

- Split household aggregate income inputs (intrec, dividends, pensions, gssi, stcg, ltcg, scorp) evenly between spouses in the Microsimulation runner when mstat=2, matching the existing input_mapper.py convention. Closes #665 and #838.


## [2.19.0] - 2026-04-16

### Added

- Split CTC output into v22 (non-refundable) and actc (refundable) to match TAXSIM convention. For fully-refundable years (e.g. 2021 ARPA), v22 reports the total CTC; for other years, v22 is capped at state tax liability and actc reports the additional refundable portion.


## [2.18.2] - 2026-04-06

### Fixed

- Sum person-level state variables to tax-unit level in output resolver, fixing broadcasting errors for joint filers in states like MT and CO.


## [2.18.1] - 2026-03-30

### Fixed

- Recognize dependent age and count columns; use full Enhanced CPS dataset.


## [2.18.0] - 2026-03-29

### Added

- Add pre-built Enhanced CPS sample dataset and dataset documentation to the web runner.
- Added support for Stata (.dta) file format. Input and output files are auto-detected by extension; all CLI subcommands now accept .dta files alongside CSV.

### Changed

- Update Stata code examples on landing page and docs to use idiomatic TAXSIM conventions (! shell escape, txpydata.raw/output.raw filenames, explicit delimiter).

### Fixed

- Include Additional Medicare Tax (0.9% on wages above $200K/$250K) in fiitax output to match TAXSIM's treatment.
- Handle missing parameter errors gracefully in PolicyEngineRunner instead of crashing.
- Move TAXSIM-only umbrella outputs onto explicit per-state adapters and align scalar and vectorized state output resolution.


## [2.17.2] - 2026-03-29

### Changed

- Upgrade Next.js from 15 to 16.


## [2.17.1] - 2026-03-26

### Changed

- Deploy TAXSIM API on Modal and wire dashboard to use it instead of requiring a local server.


## [2.17.0] - 2026-03-24

### Added

- Add remote TAXSIM-35 runner for seamless pre-2021 support in the web runner.


## [2.16.0] - 2026-03-23

### Added

- Add web runner for browser-based CSV processing.


## [2.15.2] - 2026-03-23

### Changed

- Match dashboard header to policyengine-app-v2 design.


## [2.15.1] - 2026-03-20

### Fixed

- Consolidate CI workflows into a single dependency chain.


## [2.15.0] - 2026-03-20

### Added

- Add chunked processing for large datasets and multi-year support.
- Add TAXSIM-compatible marginal tax rate computation (frate, srate, ficar) via wage perturbation.

### Fixed

- Fix changelog fragment check to diff against base branch, and chain publish workflow after versioning via workflow_run.


## [2.14.0] - 2026-03-07

### Added

- Added ruff formatter with CI check and Makefile target.


## [2.13.3] - 2026-03-06

### Fixed

- Add macOS troubleshooting note for PATH issues when using policyengine-taxsim from Stata, SAS, or other programs.


## [2.13.2] - 2026-03-04

### Fixed

- Restore basePath for embedded context at policyengine.org.


## [2.13.1] - 2026-03-04

### Changed

- Convert dashboard from Vite to Next.js with Tailwind CSS v4, add PolicyEngine header, and use design system tokens.


## [2.13.0] - 2026-03-02

### Added

- Add StitchedRunner for year-based routing to PE or TAXSIM.


## [2.12.0] - 2026-02-26

### Added

- Added GA4 analytics (shared `G-2YHG89FY0N` property) and Vercel Analytics script to the dashboard.


## [2.11.0] - 2026-02-26

### Added

- Add --assume-w2-wages CLI flag to align QBID calculation with TAXSIM's S-Corp handling by bypassing the W-2 wage cap.


## [2.10.3] - 2026-02-26

### Fixed

- Fixed Vercel SPA rewrites to correctly serve the dashboard at /us/taxsim.


## [2.10.2] - 2026-02-26

### Fixed

- Fixed deploy-pages CI workflow to use bun instead of npm, resolving build failures from stale lockfile.


## [2.10.1] - 2026-02-26

### Fixed

- Fixed deploy-pages CI workflow to use bun instead of npm, resolving build failures from stale lockfile.


## [2.10.0] - 2026-02-26

### Added

- Added landing page to the CPS dashboard explaining what policyengine-taxsim is and how to install/use it from Python, R, and Stata.


## [2.9.1] - 2026-02-25

### Fixed

- Pin Python version constraint in R wrapper setup_policyengine() to avoid failure on Python 3.14+ machines.


## [2.9.0] - 2026-02-24

### Added

- Add /diagnose-issue slash command and issue analysis tracker.


## [2.8.1] - 2026-02-19

### Fixed

- Fix CLI entry point: `policyengine-taxsim` command now works after click group refactor.


## [2.8.0] - 2026-02-19

### Added

- Add policyengine-us version pinning and version reporting to R wrapper.


## [2.7.3] - 2026-02-19

### Changed

- Updated README Quick Start and installation instructions to use uv and virtual environments.


## [2.7.2] - 2026-02-18

### Changed

- Require policyengine-us >= 1.552.0 to ensure deterministic results (no random takeup draws in the country package).


## [2.7.1] - 2026-02-07

### Fixed

- Relax generate phase scaling test threshold from 3x to 5x to avoid flaky failures on slow CI runners.


## [2.7.0] - 2026-02-07

### Added

- Use unified state variables instead of per-state iteration for ~10x fewer calculation calls. Add CPS-like benchmark (2000 records, all states, full output).


## [2.6.1] - 2026-02-07

### Changed

- Replace yaml-changelog with towncrier for changelog generation. Fragments in `changelog.d/` replace `changelog_entry.yaml`.


Changelog
All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [2.6.0] - 2026-02-06 23:00:28

### Added

- Vectorize PolicyEngineRunner for ~100x speedup on large inputs.
- Add performance regression tests.
- Cache load_variable_mappings() with lru_cache.

## [2.5.0] - 2026-01-04 20:50:20

### Added

- Add R package wrapper (policyenginetaxsim) for running the emulator from R

## [2.4.1] - 2025-12-02 01:09:47

### Fixed

- Fix glob and node-forge security vulnerabilities (GHSA-5j98-mcp5-4vw2, GHSA-5gfm-wpxj-wjgq)

## [2.4.0] - 2025-09-25 20:34:26

### Added

- Remove special cases from the variable mappings.

## [2.3.0] - 2025-09-24 13:28:56

### Added

- Remove not mapped output Variables from the household breakdown.

## [2.2.0] - 2025-09-09 23:40:23

### Added

- Set benefit program values to 0 in the PolicyEngine runner.

## [2.1.5] - 2025-09-09 13:55:29

### Fixed

- Fix dependent age default.

## [2.1.4] - 2025-09-08 23:22:54

### Fixed

- Add head, spouse and dependent tags in the PolicyEngine runner.

## [2.1.3] - 2025-09-05 18:12:04

### Added

- Initialize versioning.

## [2.1.2] - 2025-09-05 14:55:43

### Fixed

- Make taxsimid optional.

## [2.1.1] - 2025-09-05 14:28:53

### Fixed

- Export Data button.

## [2.1.0] - 2025-09-03 19:32:49

### Added

- Clean up the variable_mappings file.

## [2.0.0] - 2025-09-03 18:41:32

### Added

- Documentation for the dashboard.

## [1.1.3] - 2025-09-01 17:59:24

### Fixed

- Fix unemployment compensation mapping.

## [1.1.2] - 2025-08-27 16:17:40

### Fixed

- Handling of floats for year inputs.

## [1.1.1] - 2025-08-26 22:28:10

### Fixed

- Fix idtl 5 when running the comparison.

## [1.1.0] - 2025-08-26 22:12:03

### Added

- Remove Colorado Note from the dashboard.

## [1.0.0] - 2025-08-26 21:56:12

### Added

- Frontend Dashboard for comparing PolicyEngine and TAXSIM results.
- CLI for comparing PolicyEngine and TAXSIM results.

## [0.2.0] - 2025-07-29 14:27:02

### Added

- Add is_tax_unit_dependent to each dependent in the household in the yaml generator.

## [0.1.1] - 2025-07-18 18:21:31

### Added

- Initialize versioning.

### Fixed

- Add missing taxcalc dependency to fix import errors in CI.

## [0.1.0] - 2025-07-18 17:29:10

### Added

- Initialized changelogging



[2.6.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.5.0...2.6.0
[2.5.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.4.1...2.5.0
[2.4.1]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.4.0...2.4.1
[2.4.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.3.0...2.4.0
[2.3.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.2.0...2.3.0
[2.2.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.5...2.2.0
[2.1.5]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.4...2.1.5
[2.1.4]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.3...2.1.4
[2.1.3]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.2...2.1.3
[2.1.2]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.1...2.1.2
[2.1.1]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.1.0...2.1.1
[2.1.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/2.0.0...2.1.0
[2.0.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/1.1.3...2.0.0
[1.1.3]: https://github.com/PolicyEngine/policyengine-taxsim/compare/1.1.2...1.1.3
[1.1.2]: https://github.com/PolicyEngine/policyengine-taxsim/compare/1.1.1...1.1.2
[1.1.1]: https://github.com/PolicyEngine/policyengine-taxsim/compare/1.1.0...1.1.1
[1.1.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/0.2.0...1.0.0
[0.2.0]: https://github.com/PolicyEngine/policyengine-taxsim/compare/0.1.1...0.2.0
[0.1.1]: https://github.com/PolicyEngine/policyengine-taxsim/compare/0.1.0...0.1.1
