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
