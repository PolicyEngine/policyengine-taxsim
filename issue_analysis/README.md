# TAXSIM Issue Analysis Tracker

This directory tracks the diagnosis of discrepancies between PolicyEngine and TAXSIM.

## Status Legend
- `pending` - Not yet analyzed
- `in_progress` - Currently investigating
- `diagnosed` - Root cause identified
- `pe_correct` - PolicyEngine is correct, TAXSIM/TaxAct differs
- `pe_fix_needed` - PolicyEngine needs update (issue filed in policyengine-us)
- `taxsim_fix_needed` - policyengine-taxsim needs update (input/output mapping bug)
- `taxsim_bug` - Bug in NBER TAXSIM-35 (not our emulator)
- `ambiguous` - Needs further research
- `closed` - Resolved/closed

## Issue Tracker

| Issue | State | Year | Status | Root Cause | PE-US Issue |
|-------|-------|------|--------|------------|-------------|
| #592 | MT | 2024 | pe_fix_needed | MT eliminated federal income tax deduction in 2024 under SB 399. PE still adds $10,000 to itemized deductions. | [#6973](https://github.com/PolicyEngine/policyengine-us/issues/6973) |
| #591 | MO | 2024 | pe_correct | YAML expected $5,159.23 is wrong. PE $4,849.29 matches TaxAct $4,849. MO itemized correctly includes FICA taxes ($60,400 mortgage + $2,295 FICA = $62,695). | N/A |
| #604 | CO | 2024 | pe_correct | TaxAct failed to claim TABOR Sales Tax Refund ($354) and Senior Housing Credit ($708). PE correctly calculates both credits for taxpayers aged 70 with AGI $36,996. | N/A |
| #660 | NJ | 2024 | pe_correct | Issue filed with wrong state code (34=NC instead of 31=NJ). PE logic is correct. | N/A |
| #659 | CO | 2024 | pe_correct | PE correctly calculates CO Family Affordability Credit ($1,080). TaxAct may not have implemented this new 2024 credit. | N/A |
| #658 | CO | 2024 | pe_fix_needed | PE auto-applies CO Income-Qualified Senior Housing Credit ($752) without checking property ownership. TaxAct PDF shows $322 owed, not -$430.23 refund. | TBD |
| #657 | MS | 2024 | pe_fix_needed | TaxAct PDF shows $0 tax (not $147.97 in YAML). PE bugs: (1) spouse aged exemption missing for non-JOINT; (2) no optimal exemption allocation; (3) no optimal std ded allocation. | TBD |
| #569 | NM | 2024 | pe_correct | YAML wrong ($13,303). TAXSIM bug: doesn't apply 40% capital gains deduction. TaxAct shows $12,160 (taxable $256,521). PE $12,135 is correct (includes $26 CTC). | N/A |
| #573 | VT | 2024 | pe_fix_needed | PE applies 40% capital gains exclusion ($9,534) but publicly traded securities only qualify for $5,000 flat exclusion. TaxAct: -$315 refund. PE: -$476. | TBD |
| #596 | MN | 2024 | pe_correct | PE $3,418 matches YAML. Marriage credit: PE=$247 vs TaxAct=$144. PE follows M1MA instructions (SE Line 3 - Line 13). TaxAct may have bug. | N/A |
| #585 | IA | 2024 | pe_fix_needed | IA CDCC uses `ia_net_income` but form says use `ia_taxable_income` (IA 1040 Line 4). PE=$528, TaxAct=$720. Refund should be $1,352 not $1,160. | [#6977](https://github.com/PolicyEngine/policyengine-us/issues/6977) |
| #605 | IA | 2024 | pe_fix_needed | Same bug as #585: IA CDCC uses wrong income variable. PE=$4,321 matches YAML but TaxAct=$4,141 (after $180 CDCC). | [#6977](https://github.com/PolicyEngine/policyengine-us/issues/6977) |
| #595 | MS | 2024 | pe_correct | PE=$54 matches YAML. PE correctly optimizes between joint/separate filing, choosing joint (lower tax). MS 2024 rate: 4.7% on income > $10K. | N/A |
| #668 | MO | 2024 | pe_correct | PE=$0 matches YAML. TaxAct shows $80 because it failed to complete MO-A Section B (Private Pension). PE correctly claims $6,000 pension exemption for age 75 filer with $14,313 private pension. | N/A |
| #667 | MO | 2024 | pe_correct | PE=$54 matches YAML. TaxAct shows $245 because it failed to complete MO-A Section B (same error as #668). PE correctly claims $12,960 combined pension+SS exemption. | N/A |
| #666 | NJ | 2024 | closed | PE=$230 but TaxAct=$552. Bug: subtractions.yaml double-excludes SS income. Fixed upstream. | [#6979](https://github.com/PolicyEngine/policyengine-us/issues/6979) |
| #669 | IA | 2024 | taxsim_fix_needed | PE=$147,228 but TaxAct=$119,218. Bug in input_mapper.py: splits pension 50/50 between spouses. Iowa excludes pension for age 55+ only, so spouse (age 40) portion isn't excluded. | N/A (taxsim fix) |
| #619 | AZ | 2024 | diagnosed | PE $6 low (spurious $250 rebate), TAXSIM $90 high (DTC phaseout bug). Both wrong for different reasons. | [#7481](https://github.com/PolicyEngine/policyengine-us/issues/7481) |
| #664 | VA | 2024 | pe_fix_needed | VA Spouse Tax Adjustment not implemented. PE missing spousal exemption for joint filers. | [#6958](https://github.com/PolicyEngine/policyengine-us/issues/6958) |
| #671 | CT | 2024 | closed | Resolved. | N/A |
| #683 | DC | 2024 | diagnosed | DC discrepancy diagnosed in prior session. | N/A |
| #684 | DC | 2024 | closed | SE loss fix resolved the discrepancy. | N/A |
| #686 | DC | 2024 | diagnosed | DC discrepancy diagnosed in prior session. | N/A |
| #711 | - | 2021 | taxsim_bug | Does TAXSIM-35 incorrectly exclude 17-year-olds from 2021 expanded CTC? PE correctly includes them per ARPA. | N/A |
| #712 | - | 2024 | taxsim_bug | Does TAXSIM-35 incorrectly calculate OASDI on self-employment income? PE correctly applies 92.35% factor. | N/A |
| #714 | - | 2024 | taxsim_bug | Does TAXSIM-35 incorrectly apply EITC age limits? PE correctly follows current law (no upper age limit post-2021). | N/A |
| #715 | - | 2024 | closed | Additional Medicare Tax discrepancy. Known diff, backburnered. | N/A |
| #716 | GA | 2024 | pe_correct | GA surplus rebate timing convention question. PE assigns to eligibility year. Fixed upstream (commit 2c5d32e). | N/A |
| #717 | CA | 2024 | taxsim_bug | TAXSIM SALT add-back bug confirmed: 05ca.for includes state income tax in SALT excess, inflating CA itemized deductions. PE is correct. | N/A |
| #718 | VA | 2024 | pe_correct | VA rebate timing convention question. Similar to GA (#716). | N/A |
| #719 | AZ | 2024 | taxsim_bug | Does TAXSIM-35 use wrong phaseout rate for AZ Dependent Tax Credit? PE correctly phases out at statutory rate. | N/A |
| #655 | VT | 2024 | pending | | |
| #654 | AZ | 2024 | pending | | |
| #653 | DC | 2024 | pending | | |
| #652 | - | 2024 | ambiguous | HOH + 19yo dependent: TaxAct assumes HOH, PE uses Single (19yo non-student doesn't qualify per IRS). See #651. | N/A |
| #636 | DC | 2024 | pe_correct | YAML wrong: expects $28,444 (tax on full AGI). PE correctly applies $21,900 std ded -> $26,418 (matches TaxAct $26,419). | N/A |
| #651 | CT | 2024 | ambiguous | TaxAct: $905 (HOH), PE: $1,568 (Single). 19yo non-student doesn't qualify as child dependent for HOH per IRS rules. TaxAct may be incorrectly assuming HOH eligibility. | N/A |
| #650 | NJ | 2024 | pending | | |
| #649 | AR | 2024 | pending | | |
| #555 | MS | 2024 | pe_fix_needed | TaxAct PDF: $0 tax (optimal allocation). PE: $98.70 (50/50 split). Same root cause as #657 - no optimal exemption/deduction allocation. | TBD |
| #552 | AR | 2024 | pe_correct | PE $1,450 is correct. AR instructions say $6,000 pension exemption applies without age requirement ("recipient does not have to be retired"). TaxAct bug: not applying exemption. | N/A |
| #553 | KY | 2024 | pe_correct | PE $319 matches TaxAct $320. Family Size Tax Credit correctly $0 because Modified AGI = max(Fed AGI, KY AGI) = $76,518. Pension exclusion can't reduce Modified AGI below Fed AGI. | N/A |
| #580 | IA | 2024 | pe_correct | PE $31,924.23 matches YAML (with --disable-salt). TAXSIM limitation: no W-2 wages input, so QBID for high-income taxpayers can't be calculated correctly. TaxAct shows different QBID. | N/A |
| #551 | NE | 2024 | pe_correct | YAML $0 is correct. NE caps state tax at federal tax ($0 for LTCG/div-only income). PE returns $0 accidentally due to StateGroup crash (all contiguous states affected). | N/A (separate bug) |
| #560 | OK | 2024 | pe_fix_needed | PE misses $80 Sales Tax Relief Credit. Bug: ok_gross_income treats STCG/LTCG separately (max(0,STCG)+max(0,LTCG)=$18,713) instead of netting first (max(0,STCG+LTCG)=$6,402). Pushes income over $50K limit. | [#6975](https://github.com/PolicyEngine/policyengine-us/issues/6975) |
| #548 | MN | 2024 | pe_correct | PE $-3,066 refund matches YAML. MN CTC does NOT require earned income per statute 290.0661. Issue filer incorrectly claims earned income required. TaxAct appears to have a bug. | N/A |
| #549 | WV | 2024 | pe_fix_needed | TaxAct: $0, PE: -$120 refund. Bug: WV HEPTC creates phantom credit when household income is negative and no property taxes paid. | [#6948](https://github.com/PolicyEngine/policyengine-us/issues/6948) |
| #546 | MT | 2024 | pe_fix_needed | TaxAct: $0, PE: $277. Two bugs: (1) subtracting negative capital gains creates phantom income; (2) capital gains tax on negative gains produces negative tax. | [#6947](https://github.com/PolicyEngine/policyengine-us/issues/6947) |
| #545 | HI | 2024 | pe_fix_needed | TaxAct: -$440 refund (food/excise credit). PE: $0. Parameter threshold starts at 0, not -inf, so negative AGI gets $0 credit. | [#6946](https://github.com/PolicyEngine/policyengine-us/issues/6946) |
| #544 | DC | 2024 | pe_fix_needed | TaxAct: $0, PE: -$90 refund. Bug: dc_ptc creates phantom $90 credit when AGI is negative (ptax_offset becomes negative, making 0 - (-90) = $90). | [#6945](https://github.com/PolicyEngine/policyengine-us/issues/6945) |
