Changelog
All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

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
