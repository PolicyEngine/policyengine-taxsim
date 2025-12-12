# TAXSIM Issue Analysis Tracker

This directory tracks the diagnosis of discrepancies between PolicyEngine and TAXSIM.

## Status Legend
- `pending` - Not yet analyzed
- `in_progress` - Currently investigating
- `diagnosed` - Root cause identified
- `pe_correct` - PolicyEngine is correct, TAXSIM/TaxAct differs
- `pe_fix_needed` - PolicyEngine needs update (issue filed in policyengine-us)
- `ambiguous` - Needs further research

## Issue Tracker

| Issue | State | Year | Status | Root Cause | PE-US Issue |
|-------|-------|------|--------|------------|-------------|
| #660 | NJ | 2024 | pe_correct | Issue filed with wrong state code (34=NC instead of 31=NJ). PE logic is correct. | N/A |
| #659 | CO | 2024 | pe_correct | PE correctly calculates CO Family Affordability Credit ($1,080). TaxAct may not have implemented this new 2024 credit. | N/A |
| #658 | CO | 2024 | pending | | |
| #657 | MS | 2024 | pe_fix_needed | TaxAct PDF shows $0 tax (not $147.97 in YAML). PE bugs: (1) spouse aged exemption missing for non-JOINT; (2) no optimal exemption allocation; (3) no optimal std ded allocation. | TBD |
| #655 | VT | 2024 | pending | | |
| #654 | AZ | 2024 | pending | | |
| #653 | DC | 2024 | pending | | |
| #652 | - | 2024 | pending | | |
| #651 | CT | 2024 | pending | | |
| #650 | NJ | 2024 | pending | | |
| #649 | AR | 2024 | pending | | |

## Directory Structure

```
issue_analysis/
├── README.md              # This file - tracks all issues
├── templates/
│   └── finding.md         # Template for documenting findings
└── issues/
    ├── 660_nj_joint_elderly.md
    ├── 659_co_hoh.md
    └── ...
```
