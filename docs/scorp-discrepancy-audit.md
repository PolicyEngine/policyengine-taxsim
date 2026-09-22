# Pre-merge discrepancy audit — PR #1199

**Decision: do not merge.** The passive S-corp switch improves TAXSIM agreement but exposes an EITC regression. Passing interface tests and a higher match rate do not establish tax-law correctness. PR #1199 remains draft; no production dashboard refresh or model behavior change was made during this audit.

## Scope and evidence

- Pinned PolicyEngine-US 2.6.17; same bundled TAXSIM executable used by the dashboard.
- 3,000 identical sampled households per year, 2021–2025 (15,000 household-year comparisons), active versus passive S-corp treatment, W-2 assumption enabled, native SALT behavior.
- Detailed sample run: https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35685604478
- 48 targeted cases per year, including synthetic controls and large residuals: https://github.com/PolicyEngine/policyengine-taxsim/actions/runs/35685926063
- Heavy calculations ran on hosted Actions with a 5 GiB memory guard, fresh workers, and at most two simultaneous year jobs. No local PE model was installed or run.
- `audit_scorp_probes.py` reproduces the targeted comparisons. Compressed evidence alongside this report preserves the failing sampled records and probe outputs. These are diagnostics, not an assertion that every discrepancy has a proven cause.
- The public dashboard still contains the full September 21 refresh using **active** S-corp treatment. Passive results here are a validation sample, not replacement full-population dashboard data.

## Merge-blocking regression

2021 California household **109088** receives **$660.40 of EITC only after the passive switch**. Its $7,147.17 interest plus $12,442.61 dividends already exceed the $10,000 investment-income limit. Mapping its negative S-corp income into the shared NIIT base makes that base negative; PE's `eitc_relevant_investment_income` then lets passive losses offset portfolio income. Active PE and TAXSIM correctly return zero EITC for this case.

[IRC §32(i)(2)](https://www.law.cornell.edu/uscode/text/26/32#i_2) counts positive net passive-activity income separately from interest/dividends and positive net capital gains. Fix the EITC income definition, with regression coverage for both positive and negative passive income. Do not simply remove losses from NIIT to hide this interaction.

The other three lost federal matches are the same Alaska household **111323** in 2021–2023. Correcting $74,713.47 of NIIT exposes pre-existing QBI and Additional Medicare discrepancies that previously partly cancelled. Those are not evidence that its old NIIT treatment was correct.

## Confirmed federal findings

### QBI loss netting: both models need attention

- **PE:** clips QBI at zero per person before combining spouses. Synthetic 2022 MFJ, $400,000 wages, $200,000 primary SE profit and $100,000 spouse SE loss: TAXSIM QBID $19,464.37; PE $39,464.37. The $20,000 excess is the omitted negative QBI. Household 111323 has a $465,478.06 deduction gap.
- **TAXSIM:** also drops losses, but at a different aggregation level: net negative SE income can disappear before being combined with positive S-corp income. Household 59073 has $289,861.50 of net SE losses and positive S-corp income; TAXSIM's deduction exceeds PE by $57,972.60, exactly 20% of those losses.
- Passive business income can still qualify for QBI. Neither making S-corp income passive nor the W-2 assumption resolves loss netting.

[Form 8995-A, Schedule C](https://www.irs.gov/instructions/i8995a) requires allocation of qualified business losses against positive QBI. Correct the upstream calculation; do not force one model to copy the other's clipping error.

### Excess business losses

Synthetic single filer with $1 million wages and $1 million otherwise allowable business loss:

| Year | IRS single threshold | PE applied | TAXSIM implied |
|---|---:|---:|---:|
| 2021 | $262,000 | $262,000 | No limit |
| 2022 | $270,000 | $270,000 | No limit |
| 2023 | $289,000 | $289,000 | No limit |
| 2024 | $305,000 | $305,000 | $313,308.49 |
| 2025 | $313,000 | $305,000 | $322,706.71 |

Joint thresholds are twice these amounts. PE's 2025 parameter is stale; TAXSIM's implementation differs more broadly.

TAXSIM additionally treats supplied net capital gains as available to offset business losses. PE excludes portfolio capital gains from this basket. Inputs cannot identify which capital gains actually arose from a business. For 2025 household **107775**, the AGI gap is $2,880,250.04 and federal tax gap $715,640.68; NIIT and QBID are zero in both models. This is predominantly a business-loss/capital-gain attribution issue, not a remaining S-corp NIIT error.

[Form 461](https://www.irs.gov/instructions/i461) limits eligible capital gains to those attributable to a business and applies after at-risk and passive-activity loss rules. The emulator switch does not implement all §469 restrictions, basis, or carryovers; results assume input losses are otherwise allowable. Missing facts cannot be resolved by indiscriminate parity changes.

### NIIT deductions

PE omits allocable deductions from its NIIT base. TAXSIM makes deductions, but isolated probes show incorrect cases:

- $300,000 wages + $100,000 interest, no state tax: both $3,800 NIIT.
- Same income in CA/MA/NY in 2022: TAXSIM $3,705; PE $3,800. With $50,000 mortgage expense, the $95 deduction is consistent with allocating $2,500 of the deductible $10,000 SALT to investment income. Without mortgage, TAXSIM still subtracts $95 despite taking the standard deduction.
- Texas 2022: TAXSIM $3,778.22, reflecting a sales-tax allocation; PE $3,800. Sales tax is not deductible for NIIT.
- CA 2025: TAXSIM still uses a $10,000 SALT amount for NIIT even when regular-tax itemization uses the higher 2025 cap. PE still omits the allocation altogether.

[Form 8960](https://www.irs.gov/instructions/i8960) allows properly deductible expenses allocated reasonably to investment income and expressly excludes sales taxes. Both model changes and explicit assumptions are needed; subtracting all SALT would be wrong.

### Payroll and output definitions

- **TAXSIM employer Social Security is uncapped.** In 2025, single filer with $300,000 wages: TAXSIM `fica` $39,118.20 versus PE $31,436.40. The $7,681.80 gap is exactly 6.2% of wages above the $176,100 cap. [SSA taxable maximum](https://www.ssa.gov/oact/COLA/cbb.html).
- **TAXSIM charges SE tax below the $400 net-earnings threshold.** Gross SE income $404.319 gives net earnings about $373.39: TAXSIM $57.13, PE zero. [Schedule SE instructions](https://www.irs.gov/instructions/i1040sse).
- **PE `tfica` includes employee state payroll taxes** through `employee_payroll_tax`; TAXSIM's output is federal. Separate the emulator output definition from underlying state benefit financing.
- **Additional Medicare output changes by year in TAXSIM.** On $300,000 wages, TAXSIM includes $900 in `fiitax` during 2021–2023, excludes it in 2024–2025. PE excludes it in all these years. Treat this as output compatibility, not changing the underlying tax. The existing regression test only covered 2024.

### Credits and deductions

- **TAXSIM treats negative S-corp income like a loss of earned income for EITC/ACTC.** For a single 35-year-old with one 8-year-old child and $10,000 wages in 2025, changing S-corp income from $0 to −$5,000 reduces TAXSIM EITC from $3,400 to $1,700 and ACTC from $1,125 to $375. Passive S-corp losses do not belong in earned income. This differs from the new PE investment-income regression above.
- **2021 TAXSIM other-dependent credit behaves as refundable.** Household 5062 has zero taxable income and an 18-year-old dependent: TAXSIM gives $500, PE zero. The other-dependent credit remains nonrefundable. [IRS 2021 guidance](https://www.irs.gov/irb/2021-29_IRB).
- **CDCC:** household 111323 gets $600 from TAXSIM but zero from PE; spouse has negative SE income. Inspect the spouse earned-income limit and any assumed student/disability status rather than assume the higher credit is right.
- **Deduction choice:** household 77471, DC 2025, TAXSIM uses $10,000 itemized deductions despite reporting $34,700 standard deduction; PE uses standard. Moving the identical TAXSIM case to state 0 makes it use standard and removes the $9,139 regular-tax gap. This is state-dependent deduction selection; determining whether it reflects combined federal/state optimization needs further validation.
- **AMT:** household 53450, CA 2025, TAXSIM has $11,239.16 AMT; PE zero. Income and regular taxable income agree. Hosted internal probes trace an upstream worksheet defect: `dwks09` includes qualified dividends in the capital-gain amount and `dwks10` adds them again when positive short-term gains leave room. Here `dwks13` is $1,424,101.63 instead of the $1,341,864.75 qualified-dividend/LTCG amount, double-counting $82,236.83 of dividends. This understates ordinary AMT income. The exact corrected AMT and any residual TAXSIM difference still need a Form 6251 calculation. This case has no S-corp income.
- Output columns such as `v19` are not necessarily identical concepts in both models. At very high incomes PE float32 rounding also produces several-dollar differences. Do not count every nonzero intermediate-column delta as a distinct legal error.

## State inventory and disposition

All sampled state failures are retained in the evidence inventory, including inputs and output deltas. Grouping by first differing field is triage, not proof of causation. Confirmed representative mechanisms and unresolved clusters:

| State/group | Finding and next step |
|---|---|
| MD | TAXSIM includes local tax; emulator explicitly removes it. Example 20128, 2022: identical $2,171.33 state tax before credits, but TAXSIM adds $1,498.15 = 3.2% × $46,817.39 taxable income. County rates vary; choose/document a local-tax assumption, not a federal model patch. |
| AR | Plain-wage household 34268, 2022: same $120,301.43 taxable income, TAXSIM tax before credits $1,539.80 versus PE $5,727.57. Reproduces outside the batch and across Linux/macOS. Additional pension and high-income cases need separate review; do not treat all AR gaps as one bug. |
| NY | Household 4231, 2022: TAXSIM tax before credits $19,327.24 but final tax −$17,906.02, despite zero reported credit/rebate. Removing the dependent removes the large reduction; it persists in 2023 and disappears in 2024. Separately PE's tax-before-credit amount differs by $805.21 (recapture). Exact TAXSIM credit mechanism remains unresolved. |
| MN | 2021–2022 elderly cases have unexpectedly low TAXSIM taxable income. Household 14546, 2022: federal AGI about $43,731; PE state taxable $24,871 after standard deduction and $4,260 SS subtraction; TAXSIM zero. Later-year SS law must not be applied retroactively. |
| VT | TAXSIM assumes a 40% capital-gain exclusion where PE uses the $5,000 exclusion. Example 57343 has $153,971.42 state-taxable-income gap. The percentage exclusion depends on asset type/holding period absent from TAXSIM inputs. |
| Rebate states | CO, CT, DE, GA, HI, ID, IL, IN, MA, MD, ME, MT, NM, SC, VA and AZ include varying rebate/payment-year or output-placement gaps. Recompute `siitax + srebate` before judging parity. This removes only some failures, not all. |
| MI | Pension phase-in/age allocation, income-loss treatment and refundable-credit differences. Existing issue #1159 discusses disagreement with TAXSIM/TaxAct on the retirement-law update. |
| MO/AZ/WI/MT | Elderly homeowner/renter/homestead credits need consistent rent/property-tax assumptions. MT household 97325 shows a negative credit producing positive tax on zero taxable income; investigate income floors. |
| CA/MA/OR/PA | Large business-loss cases often inherit federal or state loss-netting differences. PA categories require their own loss rules. CA also has a 2021 high-income deduction discrepancy. |
| HI/NM/DC | Large high-income state tax-before-credit gaps remain, beyond the federal AGI differences; statutory rate/capital-gain worksheets still need case-by-case verification. |
| NE | $2,000-per-child refundable credit gaps begin in 2024; verify new credit implementation and eligibility assumptions. |
| CT/IL/MN/NJ/NY/CO/DC | Additional earned-income/child-credit differences, some downstream of federal earned-income treatment and some state-specific. |
| MS/LA/WV/VA and remaining small clusters | Preserved in the complete inventory; pension, income-base, credit and rebate differences require targeted state-form checks. They are not cleared for parity changes. |

Useful primary references: [Maryland 2022 rates](https://www.marylandtaxes.gov/reports/static-files/revenue/incometaxsummary/summary22.pdf), [Arkansas tax forms](https://www.dfa.arkansas.gov/office/taxes/income-tax-administration/individual-income-tax/forms/), [New York 2022 instructions](https://www.tax.ny.gov/forms/html-instructions/2022/it/it201i-2022.htm), [Vermont capital-gain bulletin](https://tax.vermont.gov/sites/tax/files/documents/TB60.pdf).

## Required before merge

1. Fix and regression-test the new EITC investment-income interaction in single and batch paths, on supported PE/Python combinations.
2. Rerun active/passive diagnostics and account for every newly changed credit/state result; do not rely only on the headline match rate.
3. Keep separate issues/fixes for upstream PE tax-law bugs, TAXSIM executable bugs, and emulator output assumptions. No change should knowingly copy an incorrect tax rule just to improve agreement.
4. Do not label the published dashboard passive until a complete, memory-bounded refresh with recorded versions/settings has actually completed.
5. Keep unresolved state/AMT/deduction findings explicitly open. This report inventories them; it does not claim a full legal certification of all 15,000 records or every state formula.

## Five-year results

Match means absolute federal/state error below 1% of the dashboard gross-income proxy (or at most $15 if the proxy is nonpositive). The proxy excludes S-corp income. These percentages are not dollar-accuracy or legal-correctness measures.

| Year | Federal matches active → passive | Passive state failures | Federal within $15, passive |
|---|---:|---:|---:|
| 2021 | 2654 → 2935 / 3,000 | 330 | 2409 / 3,000 |
| 2022 | 2663 → 2945 / 3,000 | 320 | 2459 / 3,000 |
| 2023 | 2664 → 2946 / 3,000 | 204 | 2458 / 3,000 |
| 2024 | 2695 → 2950 / 3,000 | 118 | 2550 / 3,000 |
| 2025 | 2693 → 2948 / 3,000 | 102 | 2521 / 3,000 |

Aggregate federal agreement rises **89.13% → 98.16%**; 1,359 gained matches and 4 lost. AGI, QBID, FICA and `tfica` are unchanged between modes within $1. EITC changes in four household-years, all household 109088: +$660.40 (2021), +$88.93 (2023), +$188.25 (2024), +$241.97 (2025). Only the first breaches the dashboard relative threshold.

State tax changes occur in IA (five cases each in 2021/2022), LA (seven in 2021), and MN (five each in 2024/2025). IA/LA have federal-tax deduction interactions; MN has its own 1% NIIT above $1 million from 2024. See [Minnesota NIIT](https://www.revenue.state.mn.us/net-investment-income-tax-niit). These effects mean the switch is not federal-NIIT-only.

### Complete state failure counts

| State | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|
| AR | 20 | 16 | 15 | 14 | 14 |
| AZ | 3 | 2 | 2 | 0 | 0 |
| CA | 42 | 5 | 5 | 5 | 5 |
| CO | 22 | 21 | 1 | 2 | 1 |
| CT | 3 | 3 | 1 | 1 | 1 |
| DC | 0 | 0 | 0 | 4 | 2 |
| DE | 0 | 12 | 0 | 0 | 0 |
| GA | 3 | 3 | 3 | 3 | 0 |
| HI | 22 | 21 | 14 | 10 | 8 |
| ID | 7 | 46 | 1 | 0 | 0 |
| IL | 11 | 13 | 3 | 3 | 3 |
| IN | 0 | 22 | 0 | 0 | 0 |
| LA | 8 | 0 | 0 | 0 | 3 |
| MA | 5 | 4 | 5 | 5 | 5 |
| MD | 6 | 26 | 27 | 27 | 25 |
| ME | 21 | 18 | 0 | 0 | 0 |
| MI | 9 | 1 | 12 | 12 | 12 |
| MN | 23 | 23 | 1 | 1 | 1 |
| MO | 1 | 1 | 1 | 1 | 1 |
| MS | 1 | 1 | 0 | 0 | 0 |
| MT | 33 | 2 | 33 | 0 | 0 |
| NE | 0 | 0 | 0 | 3 | 3 |
| NJ | 3 | 2 | 2 | 2 | 2 |
| NM | 46 | 42 | 12 | 7 | 2 |
| NY | 17 | 28 | 55 | 9 | 2 |
| OR | 1 | 1 | 2 | 1 | 0 |
| PA | 3 | 3 | 3 | 3 | 3 |
| SC | 13 | 0 | 0 | 0 | 0 |
| VA | 2 | 0 | 2 | 1 | 3 |
| VT | 3 | 3 | 3 | 3 | 5 |
| WI | 1 | 1 | 1 | 1 | 1 |
| WV | 1 | 0 | 0 | 0 | 0 |
