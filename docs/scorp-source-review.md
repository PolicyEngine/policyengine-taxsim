# Source verification of the discrepancy audit

Reviewed September 22, 2026. **The EITC merge blocker is confirmed. Several other numerical errors are confirmed, but the earlier blanket description of all differences as bugs was too broad.** This review supersedes the confidence labels in the initial audit.

## What was checked

1. Tax-year-specific IRS forms/instructions, statutory definitions and SSA limits, rather than using only current webpages.
2. The actual PolicyEngine-US 2.6.17 PyPI wheel source, plus previously captured hosted intermediate calculations. No local PE installation or model calculation.
3. Fresh isolated calls to the repository's macOS TAXSIM executable. `source-checks.json` records inputs, raw outputs and executable SHA-256. The output identifies compilation date `cd2026081819`; conclusions refer to this bundled build, not every TAXSIM version or the current NBER server.
4. Independent arithmetic from the tax forms, including a complete ordinary-income/qualified-gain AMT example. Reproduce with `scripts/verify_audit_sources.py /absolute/path/to/taxsimtest-osx.exe`.

## Confirmed PE errors in the pinned version

| Finding | Source and independent check | Scope |
|---|---|---|
| EITC investment-income test | [2021 Publication 596, printed p. 7, Worksheet 1](https://www.irs.gov/pub/irs-prior/p596--2021.pdf#page=7), lines 13–15: floor net passive income at zero before adding it to portfolio income. Household 109088 already has $19,589.78 interest/dividends, exceeding the $10,000 limit. Correct EITC is zero. | Confirmed regression exposed by the PR. PE's formula uses the shared NIIT base and lets passive losses cancel interest/dividends. |
| QBI loss netting | [2022 Form 8995-A instructions, printed pp. 5–6, Schedule C](https://www.irs.gov/pub/irs-prior/i8995a--2022.pdf#page=5) require qualified losses to offset other qualified business income. Synthetic joint return: $200,000 profit − $100,000 loss − $2,678.15 SE deduction = $97,321.85 QBI; 20% = $19,464.37, not PE's $39,464.37. | Confirmed under the test's qualified-business/sufficient-W-2 assumptions. PE's Person-level `qualified_business_income` floors away the spouse's loss. Suspended/nonqualified losses require separate treatment. |
| 2025 excess-business-loss threshold | [2025 Form 461, line 15](https://www.irs.gov/pub/irs-prior/f461--2025.pdf) explicitly specifies $313,000 single/$626,000 joint. Pinned PE source and hosted runtime both use $305,000/$610,000. | Confirmed stale parameter, independent of the passive switch. Assumes losses otherwise deductible after prior limitations. |
| AMT dividend double-counting | [2025 Form 6251, Part III](https://www.irs.gov/pub/irs-prior/f6251--2025.pdf#page=2), line 13 uses the qualified-dividend/capital-gain worksheet amount once. Actual case 53450: $1,259,627.91 LTCG + $82,236.83 qualified dividends = $1,341,864.74. PE `dwks09` includes dividends and `dwks10` adds them again, producing $1,424,101.63. | Confirmed worksheet defect, not a S-corp issue. The independent AMT calculation below shows neither model's final amount is correct. |

PE's omission of allocable NIIT deductions is also a **confirmed missing calculation when eligible expenses exist**. It does not imply every observed NIIT difference is a PE error: the input must establish deductible expenses paid and their allocation.

## Independent 2025 AMT calculation

Case 53450 is single, age 75; no QBI, foreign-tax credit, special-rate gains, investment-interest election or other AMT adjustments. All supplied dividends are qualified, consistent with TAXSIM's input definition.

Using the [2025 Form 1040 instructions, Qualified Dividends and Capital Gain Tax Worksheet and Tax Computation Worksheet](https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf), and [2025 Form 6251](https://www.irs.gov/pub/irs-prior/f6251--2025.pdf):

| Calculation | Amount |
|---|---:|
| AGI / AMTI before exemption | $1,666,886.72 |
| Standard deduction (including age increment) | $17,750.00 |
| Regular taxable income | $1,649,136.72 |
| Qualified dividends + LTCG | $1,341,864.74 |
| Regular ordinary taxable income | $307,271.98 |
| Ordinary regular tax: 35% × ordinary income − $30,452.75 | $77,092.44 |
| Preferential-rate tax, 15% bracket ending at $533,400 | $257,066.55 |
| Total regular tax | $334,158.99 |
| AMT exemption (fully phased out) | $0.00 |
| Ordinary AMTI | $325,021.98 |
| Ordinary AMT: 28% × ordinary AMTI − $4,782 | $86,224.15 |
| Tentative minimum tax, including preferential-rate tax | $343,290.70 |
| **AMT = tentative minimum tax − regular tax** | **$9,131.71** |
| PE AMT | $0.00 |
| Bundled TAXSIM AMT | $11,239.16 |

Calculations retain cents for model comparison; filing-form whole-dollar rounding would alter the last few dollars, not these conclusions. TAXSIM's additional discrepancy is numerically consistent with a stale preferential-rate threshold, but that internal cause is **not proven without its source**. Do not simply replace PE's result with TAXSIM's amount.

## Rechecked TAXSIM findings

These are observed **tax-law mismatches in the bundled executable**, not claims about Dan's intent or whether a new version has fixed them.

| Finding | Reproduction and authoritative support | Classification |
|---|---|---|
| Cross-business QBI loss | Fresh single-filer control: $400,000 wages, −$50,000 SE income, +$200,000 qualified S-corp income. AGI $550,000 agrees with allowing the loss; expected QBID $30,000 with sufficient W-2 wages, output $40,000. [Form 8995-A Schedule C](https://www.irs.gov/pub/irs-prior/i8995a--2022.pdf#page=5). | Confirmed loss-netting mismatch; no passive S-corp loss is needed for this control. |
| Excess business losses | Reproduced using active SE losses, avoiding passive-loss ambiguity. Statutory single thresholds on Form 461 line 15 are [2021 $262,000](https://www.irs.gov/pub/irs-prior/f461--2021.pdf), [2022 $270,000](https://www.irs.gov/pub/irs-prior/f461--2022.pdf), [2023 $289,000](https://www.irs.gov/pub/irs-prior/f461--2023.pdf), [2024 $305,000](https://www.irs.gov/pub/irs-prior/f461--2024.pdf), [2025 $313,000](https://www.irs.gov/pub/irs-prior/f461--2025.pdf). The executable allows unlimited loss in the first three controls, then $313,308.49/$322,706.71. | Confirmed law mismatch; may be an unsupported model limitation or indexing defect. |
| Wage FICA | Single-employer $300,000 wages in 2025: 2 × 6.2% × $176,100 + 2 × 1.45% × $300,000 + $900 Additional Medicare = $31,436.40; output $39,118.20. [SSA wage base and rates](https://www.ssa.gov/oact/cola/cbb.html). | Confirmed total-payroll mismatch under the single-employer assumption. The exact uncapped-employer amount fits the gap; internal implementation is inferred. Multiple employers can complicate employer-side caps. |
| Small SE earnings | Gross profit $404.319 × 92.35% = $373.39 net earnings; ordinary SE tax should be zero, output $57.13. [2025 Schedule SE instructions, Who Must File](https://www.irs.gov/pub/irs-prior/i1040sse--2025.pdf#page=1). | Confirmed for ordinary nonchurch self-employment without an optional-method election. |
| EITC/ACTC and S-corp loss | A $5,000 passive S-corp loss reduces credits as if earned income fell from $10,000 to $5,000. [IRC §32(c)(2)](https://www.law.cornell.edu/uscode/text/26/32#c_2) defines earned income as compensation plus SE earnings; [§24(d)](https://www.law.cornell.edu/uscode/text/26/24#d) uses earned income for ACTC. S-corp pass-through loss is not SE earnings. | Confirmed earned-income mismatch, conditional on the stated passive input meaning. The loss may separately affect AGI or be suspended; neither makes it negative wages/SE earnings. |
| 2021 other-dependent credit | Fresh zero-income control with one 18-year-old dependent returns $500 beyond the recovery rebate. [2021 Schedule 8812 instructions, p. 1](https://www.irs.gov/pub/irs-prior/i1040s8--2021.pdf#page=1) explicitly retain nonrefundable ODC. | Confirmed refundability mismatch, not the expanded refundable under-18 CTC. |
| NIIT deducted for standard filers / sales tax | [2022 Form 8960 instructions, pp. 12 and 14](https://www.irs.gov/pub/irs-prior/i8960--2022.pdf#page=12) require income taxes to be properly deducted on the regular return and exclude sales taxes. The no-mortgage CA and Texas controls violate these conditions. | Confirmed numerical mismatch in those controls. Sales-tax allocation is inferred from the amount, not inspected executable source. |

## Corrections and limits to the earlier wording

- **2025 NIIT “old $10,000 cap”: downgrade to an inferred mechanism.** The $95 result is consistent with the earlier cap, but a final NIIT value alone does not prove the code's cap or uniquely determine the correct allocation. IRS permits reasonable allocation methods. Taxes paid versus current liability is another input assumption.
- **Additional Medicare placement and `tfica`: output compatibility issues.** TAXSIM's documentation defines total FICA separately from taxpayer FICA and says federal liability includes Additional Medicare. The bundled executable behaves differently across years. PE's inclusion of state payroll in `tfica` is an emulator mapping issue, not proof its state payroll law is wrong.
- **Deduction selection: not yet a confirmed bug.** [NBER's test-version documentation](https://taxsim.nber.org/taxsimtest/) says it optimizes itemization including state income tax and iterates federal/state liabilities. A federal-only disadvantage is insufficient to prove the overall choice wrong.
- **Capital-gain attribution to business losses: missing facts.** Form 461 permits business-attributable gains; neither “all capital gains” nor “none” is correct for every household. Separate input assumptions from formula defects.
- **State cases remain hypotheses unless independently derived from the relevant state forms.** MD local-tax choices, VT asset eligibility, rebate timing and pension/rent imputations are not established bugs merely because outputs differ. AR, NY, MN and other anomalies remain open, not cleared.
- **Use the correct TAXSIM documentation.** The older `/taxsim35/` page calls `scorp` active; the `/taxsimtest/` page used by this repository calls it passive. Pages also contain stale/inconsistent field descriptions. Record the executable build and raw outputs rather than treating either webpage as executable truth.
- **Scope:** confirmed PE findings concern the pinned 2.6.17 build. We have not established that every issue persists on current PE main, or on a newer TAXSIM executable. A source-backed numerical mismatch does not prove whether it is an unintended defect versus a documented modeling limitation.

**Merge decision unchanged:** resolve the confirmed EITC regression first. Neither overall agreement nor TAXSIM agreement alone is a correctness test. No calculation fixes, merges, or production data refreshes were made in this verification.
