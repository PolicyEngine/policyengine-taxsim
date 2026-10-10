# Input guide: running the emulator on your own data

This guide is for analysts who want to compute taxes for their own records, such as a survey extract, with policyengine-taxsim. It covers every input column the emulator reads, what it does with blanks and unexpected values, and a complete example that goes from a survey file to taxes merged back onto it, in Python, Stata and R.

The tables marked as generated are produced by `scripts/generate_docs_reference.py`, which runs the emulator's input code on test records and reads its mapping files. `tests/test_docs_reference.py` regenerates them and fails when the committed tables differ, so they show what the code in this commit does for the cases the generator tries.

Contents:

- [The input file](#the-input-file)
- [Which engine computes each record](#which-engine-computes-each-record)
- [Input columns](#input-columns)
- [How the emulator reads each column](#how-the-emulator-reads-each-column)
- [Blank cells, text and unknown columns](#blank-cells-text-and-unknown-columns)
- [What the emulator rejects](#what-the-emulator-rejects)
- [Values the emulator does not check](#values-the-emulator-does-not-check)
- [Dependents](#dependents)
- [Married couples](#married-couples)
- [Reading the output](#reading-the-output)
- [Worked example: from a survey file to taxes](#worked-example-from-a-survey-file-to-taxes)
- [State codes](#state-codes)

## The input file

Each row is one tax unit: a filer, a spouse if they file jointly, and their dependents. The emulator takes the same columns as NBER's TAXSIM-35:

- A CSV file with a header row, or a Stata `.dta` file with the `policyengine` subcommand.
- Column names in lowercase, exactly as listed below. They can be in any order.
- Only `year` is required. Every other column can be left out, and then takes the value shown in [How the emulator reads each column](#how-the-emulator-reads-each-column).
- Amounts are annual dollars for the tax year, as plain numbers: `52000`, not `$52,000`.

The smallest useful file:

```csv
taxsimid,year,state,mstat,page,pwages
1,2024,5,1,35,52000
```

Run it with any of these:

```bash
policyengine-taxsim < input.csv > output.csv                  # like taxsim35: stdin to stdout
policyengine-taxsim policyengine input.csv -o output.csv      # file to file; also reads and writes .dta
```

The file-to-file form is the safer choice for now. Until [#1412](https://github.com/PolicyEngine/policyengine-taxsim/pull/1412) is merged, a stdin run whose input has any record before 2021 prints three TAXSIM progress lines to stdout ahead of the CSV header, so the output file does not parse as CSV.
<!-- Remove the sentence above when #1412 merges. -->

## Which engine computes each record

The emulator has two engines. PolicyEngine US computes 2021 and later. A TAXSIM-35 executable from NBER, bundled with the package, computes earlier years. Not every interface switches between them:

| Interface | 2021 and later | Before 2021 |
|---|---|---|
| `policyengine-taxsim < in.csv > out.csv` | PolicyEngine | Bundled TAXSIM-35 |
| `policyengine-taxsim policyengine in.csv -o out.csv` | PolicyEngine | Bundled TAXSIM-35 |
| Python `StitchedRunner(df).run()` | PolicyEngine | Bundled TAXSIM-35 |
| Python `PolicyEngineRunner(df).run()` | PolicyEngine | PolicyEngine |
| R `policyengine_calculate_taxes()` | PolicyEngine | PolicyEngine |
| `policyengine-taxsim taxsim in.csv` | Bundled TAXSIM-35 | Bundled TAXSIM-35 |
| Web runner at policyengine.org/us/taxsim/run | PolicyEngine | TAXSIM-35, both on PolicyEngine's server |

`PolicyEngineRunner` and the R package compute years before 2021 with PolicyEngine, which this project validates against TAXSIM only from 2021 on. Use the command line or `StitchedRunner` when your data include earlier years.

NBER's own `taxsim35` command for Stata is separate software. It sends every record to TAXSIM-35, either a local `taxsim35.exe` or NBER's servers. The copy NBER served on 2026-10-09 contains no reference to PolicyEngine, so it does not switch engines by year. The year switch exists only in this package, in the interfaces marked above. See the [design document](design.md#routing-by-year) for how the switch works.

## Input columns

What each column means. The descriptions come from [`docs/reference/input_variables.yaml`](reference/input_variables.yaml), which the tests check against the columns the code reads. Where a note cites TAXSIM-35, it follows [NBER's input documentation](https://taxsim.nber.org/taxsimtest/).

<!-- BEGIN GENERATED: input-columns -->
#### Record and filing unit

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `taxsimid` | Record identifier, returned unchanged in the output so you can merge results back onto your data. | Number | Any non-negative number. Give every record its own value; if the column is left out, records are numbered 1, 2, 3, ... in file order. In Stata, store it as `double`. |
| `year` | Tax year. Required. | Four-digit year | A whole number. 2021 and later are computed by PolicyEngine; earlier years by the bundled TAXSIM-35 executable, which covers 1960 onward (state must be 0 before 1977, per TAXSIM-35). |
| `state` | State of residence, as a TAXSIM SOI code. | Code | 1 (Alabama) to 51 (Wyoming), in alphabetical order with DC as 9; 0 for no state tax. Never -1 (TAXSIM's every-state option), which records from 2021 on reject and earlier records answer wrongly. Use `state` or `statefip`, not both. |
| `statefip` | State of residence, as a FIPS code. An alternative to `state`. | Code | 1 (Alabama) to 56 (Wyoming), including 11 for DC; 0 or blank to use `state` instead. Codes that are not a state or DC (3, 7, 14, 43, 52) are rejected, as is a record with both `state` and `statefip` nonzero. |
| `mstat` | Filing status. | Code | 1 unmarried (filed as head of household when a dependent qualifies), 2 married filing jointly, 6 married filing separately. TAXSIM-35 also defines 8 (dependent taxpayer); see "Values the emulator does not check". |
| `page` | Age of the primary taxpayer on December 31 of the tax year. | Years | A whole number of years. |
| `sage` | Age of the spouse on December 31 of the tax year. Read only on joint returns (`mstat` 2). | Years | A whole number of years. TAXSIM-35 treats a nonzero `sage` on an unmarried return as an error. |
| `dependent_exemption` | Listed in the emulator's TAXSIM input definition, but neither engine reads it. Use `depx` and the dependent ages. | Number | Ignored. |

#### Dependents

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `depx` | Number of dependents. | Count | 0 to 11 on PolicyEngine rows. Pre-2021 TAXSIM rows receive ages for at most 10 dependents. |
| `age1` to `age11` | Age of dependent 1 on December 31 of the tax year. `age2` to `age11` hold the ages of dependents 2 to 11. | Years | A whole number of years. Ages are read only for the first `depx` dependents. Code an infant as 1, as TAXSIM-35 instructs. `age11` reaches PolicyEngine rows only; the TAXSIM-35 executable rejects it, so pre-2021 rows drop it. |
| `dep13` | TAXSIM-32 style count of dependents under 13. An alternative to the dependent ages. | Count | Counts are cumulative, so dep13 is at most dep17, which is at most dep18. Converted to ages 10 (under 13), 15 (13 to 16), 17 (17) and 21 (any of `depx` beyond `dep18`). PolicyEngine rows use the counts when the record gives no positive dependent age; pre-2021 rows use them only when the file has no age columns at all. |
| `dep17` | TAXSIM-32 style count of dependents under 17, including those under 13. | Count | See `dep13`. |
| `dep18` | TAXSIM-32 style count of dependents under 18, including those under 17. | Count | See `dep13`. |

#### Wages and self-employment

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `pwages` | Wage and salary income of the primary taxpayer. | Dollars per year | Any amount. |
| `swages` | Wage and salary income of the spouse. Read only on joint returns. | Dollars per year | Any amount. TAXSIM-35 requires zero on non-joint returns. |
| `psemp` | Self-employment income of the primary taxpayer, before self-employment tax. NBER's page describes it as not eligible for the qualified business income deduction, but the emulator and the bundled TAXSIM-35 build both apply the deduction to it. | Dollars per year | Any amount. |
| `ssemp` | Self-employment income of the spouse; see `psemp`. Read only on joint returns. | Dollars per year | Any amount. |

#### Business income (QBI)

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `pbusinc` | Primary taxpayer's active business income eligible for the qualified business income deduction without the specified-service phase-out. The emulator also applies self-employment tax to it; the bundled TAXSIM-35 build does not (see the design document's known differences). | Dollars per year | Any amount. |
| `sbusinc` | Spouse's active business income; see `pbusinc`. Read only on joint returns. | Dollars per year | Any amount. |
| `pprofinc` | Primary taxpayer's income from a specified service trade or business (SSTB), eligible for the qualified business income deduction subject to its phase-out. | Dollars per year | Any amount. |
| `sprofinc` | Spouse's SSTB income; see `pprofinc`. Read only on joint returns. | Dollars per year | Any amount. |
| `scorp` | S corporation and partnership profits (TAXSIM-35 describes this column as passive business income). | Dollars per year | Any amount; losses are entered as negative amounts. |

#### Investment and other income

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `dividends` | Qualified dividends (all dividends before 2003). Non-qualified dividends belong in `intrec`. | Dollars per year | Any amount. |
| `intrec` | Taxable interest received, and non-qualified dividends. | Dollars per year | Any amount. |
| `stcg` | Short-term capital gains or losses. | Dollars per year | Any amount; losses are negative. |
| `ltcg` | Long-term capital gains or losses. | Dollars per year | Any amount; losses are negative. |
| `otherprop` | Other property income in AGI that is subject to the net investment income tax, such as rent not eligible for the QBI deduction. | Dollars per year | Any amount; losses are negative. |
| `nonprop` | Other non-property income in AGI not subject to the net investment income tax (TAXSIM-35 lists alimony, non-wage fellowships and state tax refunds; adjustments such as IRA contributions go in as negative amounts). | Dollars per year | Any amount; adjustments are negative. |

#### Retirement and benefits

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `pensions` | Taxable pensions and IRA distributions. | Dollars per year | Any amount. |
| `gssi` | Gross Social Security benefits. | Dollars per year | Any amount. |
| `pui` | Unemployment compensation received by the primary taxpayer. | Dollars per year | Any amount. |
| `sui` | Unemployment compensation received by the spouse. Read only on joint returns. | Dollars per year | Any amount. |
| `transfers` | Non-taxable transfer income (welfare, workers' compensation, veterans' benefits, child support), which can affect state property tax rebates. | Dollars per year | Any amount. |

#### Deductions and expenses

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `rentpaid` | Rent paid, used for state renter credits and property tax rebates. | Dollars per year | Any amount. |
| `proptax` | Real estate taxes paid. | Dollars per year | Any amount. |
| `otheritem` | Other itemized deductions that TAXSIM-35 treats as AMT preferences (other state and local taxes, the preference share of medical expenses, other interest, miscellaneous). | Dollars per year | Any amount. |
| `mortgage` | Itemized deductions that are not AMT preferences (home mortgage interest, charitable contributions, deductible medical expenses, and so on). | Dollars per year | Any amount. |
| `childcare` | Child care expenses. | Dollars per year | Any amount. |

#### Output and options

| Column | Meaning | Type | Valid values |
|---|---|---|---|
| `idtl` | How much output to return for the record. | Code | 0 standard output, 2 full output, 5 a text report (stdin command, records from 2021 on). Use 2 for full output as a table. Any other value returns no tax amounts for the record on PolicyEngine rows. |
| `opt1` | A TAXSIM-35 option number, passed to the TAXSIM-35 executable for pre-2021 rows (for example 30, its PSL-conformance mode). | Code | See https://taxsim.nber.org/taxsimtest/options.html. PolicyEngine rows ignore it. |
| `opt1v` | The value for the option in `opt1`. | Number | See `opt1`. |
<!-- END GENERATED: input-columns -->

## How the emulator reads each column

Generated by running the emulator's input code on test records, so it shows what the code does rather than what it is meant to do.

- **Blank cell**: the value used when the column is present but the cell is empty or missing, on records computed by PolicyEngine.
- **Column left out**: the value used when the file has no such column.
- **PolicyEngine input**: the PolicyEngine US variable the column sets, and for whom. "Primary taxpayer" is the filer in `page`; "spouse" exists only on joint returns.
- **Pre-2021 rows**: whether the column reaches the TAXSIM-35 executable. Blank cells are written to it as 0, which TAXSIM-35 reads by its own rules (for example, it reads a taxpayer age of 0 as 40).

<!-- BEGIN GENERATED: input-handling -->
| Column | Blank cell | Column left out | PolicyEngine input (2021 and later) | Pre-2021 rows, to TAXSIM-35 |
|---|---|---|---|---|
| `taxsimid` | Blank in the output | Records numbered 1, 2, 3, ... | None: returned as `taxsimid` | Passed |
| `year` | The run stops with an error | The run stops with an error | The period every variable is computed for | Passed |
| `state` | 0 | 0 | `state_fips`, converted from the SOI code. State 0 is computed as Texas, which has no income tax, and reported as 0 | Passed |
| `statefip` | `state` is used | `state` is used | `state_fips` (converted to `state` first) | Converted to `state` first |
| `mstat` | 1; 0 also becomes 1 | 1 | 2: a spouse is added to the tax unit. 6: one adult, with `is_separated` and `cohabitating_spouses` set. 1, 3, 4, 5, 7, 8 and 9: one adult, treated as unmarried | Passed |
| `page` | 40; 0 also becomes 40 | 40 | `age` of the primary taxpayer | Passed |
| `sage` | 40; 0 also becomes 40 | 40 | `age` of the spouse (joint returns only) | Passed |
| `dependent_exemption` | Not used | Not used | Not used: no effect on PolicyEngine rows | Not passed |
| `depx` | 0 | 0 | Number of dependents added to the tax unit | Passed |
| `age1` | 10; 0 also becomes 10 | 10 | `age` of dependent 1 | Passed |
| `age2` | 10; 0 also becomes 10 | 10 | `age` of dependent 2 | Passed |
| `age3` | 10; 0 also becomes 10 | 10 | `age` of dependent 3 | Passed |
| `age4` | 10; 0 also becomes 10 | 10 | `age` of dependent 4 | Passed |
| `age5` | 10; 0 also becomes 10 | 10 | `age` of dependent 5 | Passed |
| `age6` | 10; 0 also becomes 10 | 10 | `age` of dependent 6 | Passed |
| `age7` | 10; 0 also becomes 10 | 10 | `age` of dependent 7 | Passed |
| `age8` | 10; 0 also becomes 10 | 10 | `age` of dependent 8 | Passed |
| `age9` | 10; 0 also becomes 10 | 10 | `age` of dependent 9 | Passed |
| `age10` | 10; 0 also becomes 10 | 10 | `age` of dependent 10 | Passed |
| `age11` | 10; 0 also becomes 10 | 0 | `age` of dependent 11 | Not passed |
| `dep13` | 0 | 0 | Dependent `age`s 10, 15, 17 and 21 (see `dep13`) | Converted to ages first |
| `dep17` | 0 | 0 | Dependent `age`s 10, 15, 17 and 21 (see `dep13`) | Converted to ages first |
| `dep18` | 0 | 0 | Dependent `age`s 10, 15, 17 and 21 (see `dep13`) | Converted to ages first |
| `pwages` | 0 | 0 | `employment_income` of the primary taxpayer | Passed |
| `swages` | 0 | 0 | `employment_income` of the spouse; ignored unless `mstat` is 2 | Passed |
| `psemp` | 0 | 0 | `self_employment_income` of the primary taxpayer, summed with `pbusinc` | Passed |
| `ssemp` | 0 | 0 | `self_employment_income` of the spouse; ignored unless `mstat` is 2 | Passed |
| `pbusinc` | 0 | 0 | `self_employment_income` of the primary taxpayer, summed with `psemp` | Passed |
| `sbusinc` | 0 | 0 | `self_employment_income` of the spouse; ignored unless `mstat` is 2 | Passed |
| `pprofinc` | 0 | 0 | `sstb_self_employment_income` of the primary taxpayer | Passed |
| `sprofinc` | 0 | 0 | `sstb_self_employment_income` of the spouse; ignored unless `mstat` is 2 | Passed |
| `scorp` | 0 | 0 | `partnership_s_corp_income`, split evenly between spouses on joint returns | Passed |
| `dividends` | 0 | 0 | `qualified_dividend_income`, split evenly between spouses on joint returns | Passed |
| `intrec` | 0 | 0 | `taxable_interest_income`, split evenly between spouses on joint returns | Passed |
| `stcg` | 0 | 0 | `short_term_capital_gains`, split evenly between spouses on joint returns | Passed |
| `ltcg` | 0 | 0 | `long_term_capital_gains`, split evenly between spouses on joint returns | Passed |
| `otherprop` | 0 | 0 | `rental_income` of the primary taxpayer | Passed |
| `nonprop` | Not used | Not used | Not used: no effect on PolicyEngine rows | Passed |
| `pensions` | 0 | 0 | `taxable_private_pension_income`, split evenly between spouses on joint returns, or all to the older spouse when only one has reached the age threshold (see below) | Passed |
| `gssi` | 0 | 0 | `social_security_retirement`, split evenly between spouses on joint returns, or all to the older spouse when only one has reached the age threshold (see below) | Passed |
| `pui` | 0 | 0 | `unemployment_compensation` of the primary taxpayer | Passed |
| `sui` | 0 | 0 | `unemployment_compensation` of the spouse; ignored unless `mstat` is 2 | Passed |
| `transfers` | 0 | 0 | `general_assistance` of the primary taxpayer | Passed |
| `rentpaid` | 0 | 0 | `rent` of the primary taxpayer | Passed |
| `proptax` | 0 | 0 | `real_estate_taxes` of the primary taxpayer | Passed |
| `otheritem` | 0 | 0 | `deductible_mortgage_interest` of the primary taxpayer, summed with `mortgage` | Passed |
| `mortgage` | 0 | 0 | `deductible_mortgage_interest` of the primary taxpayer, summed with `otheritem` | Passed |
| `childcare` | 0 | 0 | `tax_unit_childcare_expenses` of the tax unit | Passed |
| `idtl` | 0 | 0 | None: selects the output columns | Passed |
| `opt1` | Not used | Not used | Not used: no effect on PolicyEngine rows | Passed |
| `opt1v` | Not used | Not used | Not used: no effect on PolicyEngine rows | Passed |
<!-- END GENERATED: input-handling -->

On joint returns, pensions and Social Security are split evenly between spouses unless exactly one spouse has reached the age at which state retirement exclusions start. Then the older spouse gets the whole amount, so an age-based exclusion is not lost on the younger one. The ages:

<!-- BEGIN GENERATED: pension-split-ages -->
- Default threshold: 55, for `gssi` in every state and for `pensions` in states not listed below.
- `pensions` in GA: 62.
- `pensions` in KY: always split evenly.
<!-- END GENERATED: pension-split-ages -->

A few columns also switch on assumptions at run time, after the inputs above are built. The [design document](design.md#adjustments-at-run-time) lists them. The ones that depend on an input value: any `otherprop` turns off the QBI deduction on rental income; `rentpaid` in Minnesota assumes a Certificate of Rent Paid; and `rentpaid` in Maine is treated as including utilities.

## Blank cells, text and unknown columns

TAXSIM-35 accepts no missing values: "missing data can be represented by zeroes". The emulator is more lenient, which makes mistakes easier to miss:

- **Blank cells** take the values in the table above: 0 for amounts, 40 for adult ages, 10 for dependent ages, 1 for `mstat`, 0 for `state`.
- **Missing-value words** that pandas recognizes, such as `NA`, `N/A`, `NaN`, `null` and `#N/A`, are read as blank cells.
- **Any other text** stops the run, including Stata's `.` for missing and numbers with thousands separators (`"50,000"`). The error names the value: `could not convert string to float: '.'`.
- **Unknown or misspelled column names are ignored without a warning.** A column named `PWAGES` or `wages` is dropped, and the record is computed as if it had no wages. Column names are case-sensitive. The web runner warns about unrecognized columns; the command line and Python do not.

Recode missing values yourself before running, so every 0 is a choice. The [worked example](#worked-example-from-a-survey-file-to-taxes) does this.

## What the emulator rejects

These stop the whole run with an error naming the problem. Each one is covered by a test. The `state` checks apply to records from 2021 on; see below for earlier records.

| Input | Error |
|---|---|
| No `year` column | `Input data must contain a 'year' column` |
| A blank `year` | `Cannot convert non-finite values (NA or inf) to integer` from the command line and `StitchedRunner`; `cannot convert float NaN to integer` from `PolicyEngineRunner` |
| `state` outside 0 to 51, or not a whole number | `Record 1: 52 is not a valid TAXSIM SOI state code (0-51)` |
| `state` of -1 (TAXSIM's every-state option) | `TAXSIM state -1 (compute every state) is not supported` |
| `state` given as text, such as `CA` | `TAXSIM state code must be a number, got 'CA'` |
| `statefip` that is not a state or DC | `statefip must be a valid US state FIPS code (1-56, including DC) or 0` |
| Both `state` and `statefip` nonzero | `state 5 and statefip 6 are both nonzero; TAXSIM accepts only one of them` |
| Text in a numeric column, including `.` | `could not convert string to float: '.'` |

The R package is the exception for state codes: it converts two-letter abbreviations such as `"CA"` to SOI codes before calling the emulator.

Records before 2021 go to TAXSIM-35 without the `state` checks:

- A code TAXSIM-35 does not know, such as 52, stops the run with an error from TAXSIM-35.
- **`state` -1 is not rejected and gives a wrong answer.** TAXSIM-35 returns one row for every state, and the emulator keeps only the first, so the record comes back with Alabama's tax and `state` 1. Never use -1.

## Values the emulator does not check

The emulator computes these without complaint. Check for them yourself.

- **Filing status codes other than 1, 2 and 6.** On PolicyEngine rows they are computed as an unmarried filer; the table above shows which codes were tested. TAXSIM-35's code 8, a dependent filing their own return, therefore gets a full standard deduction instead of a dependent's. [#1218](https://github.com/PolicyEngine/policyengine-taxsim/pull/1218) proposes support for code 8.
- **Spouse columns on non-joint returns.** `sage`, `swages`, `ssemp`, `sbusinc`, `sprofinc` and `sui` are ignored unless `mstat` is 2. TAXSIM-35 treats a nonzero value as an error. Survey data that pair this year's marital status with last year's income can hit this.
- **`nonprop`.** PolicyEngine rows ignore it, so other non-property income (alimony received, fellowships) and adjustments (IRA contributions) entered there have no effect. Pre-2021 rows pass it to TAXSIM-35. [#1245](https://github.com/PolicyEngine/policyengine-taxsim/pull/1245) proposes mapping it.
- **`idtl` values other than 0, 2 and 5.** The record is computed but its output cells are blank.
- **Negative amounts.** They are passed to the engines as given.
- **Duplicate `taxsimid` values.** Both records are computed. Merging results back on `taxsimid` then fails or doubles up, so keep IDs unique.
- **Fractions in codes and counts.** On PolicyEngine rows, `year`, `mstat`, `page`, `sage`, `depx` and the dependent ages are cut to whole numbers: an age of 40.7 becomes 40.
- **Ages given for more dependents than `depx`.** Only the first `depx` ages are read.

## Dependents

- Set `depx` to the number of dependents and give their ages in `age1`, `age2`, and so on. PolicyEngine rows read up to 11; pre-2021 rows pass ages for up to 10 to TAXSIM-35.
- A dependent age of 0, or a blank one, is read as 10. **Code infants as 1**, as TAXSIM-35 instructs. Otherwise a newborn misses credits for young children, such as the 2021 child tax credit of $3,600 for children under 6 instead of $3,000.
- There is no input for full-time students. On PolicyEngine rows a dependent aged 19 or older is not a qualifying child for the earned income tax credit, so TAXSIM-35's advice to code students aged 20 to 23 as 19 does not carry over: a student counts for the EITC only if coded as 18 or younger.
- Files written for TAXSIM-32 can give counts instead of ages: `dep13`, `dep17` and `dep18` (cumulative). The emulator converts them to ages 10, 15, 17 and 21. On PolicyEngine rows the counts are used when the record has no positive age; on pre-2021 rows only when the file has no age columns.

## Married couples

- `mstat` 2 is a joint return with a spouse. Give the spouse's age in `sage` and their own earnings in `swages`, `ssemp`, `sbusinc`, `sprofinc` and `sui`.
- Household amounts with no spouse column (interest, dividends, capital gains, S corporation income) are split evenly between spouses. Pensions and Social Security follow the age rule above.
- `mstat` 6 is one spouse's separate return. It builds a one-adult tax unit: give only that spouse's income and leave the spouse columns at 0. PolicyEngine files it as married filing separately, or as head of household when a qualifying child lets the filer be treated as unmarried.

## Reading the output

Choose the output with `idtl`: 0 for the standard columns, 2 for full detail, 5 for a text report. Use 2 when you want a table. `idtl` 5 gives the text report only from the stdin command and only for records from 2021 on; other interfaces return those records as a table. For records before 2021, `idtl` 5 does not work: one such record returns only the standard columns, and two or more stop the run with `positional indexers are out-of-bounds`. The [design document](design.md#where-each-output-comes-from) lists every output column and how it is computed. The main ones:

| Column | Meaning |
|---|---|
| `taxsimid`, `year`, `state` | Echoed from the input |
| `fiitax` | Federal income tax, after credits; refundable credits make it negative |
| `siitax` | State income tax, after credits |
| `fica` | Social Security and Medicare taxes, employee and employer shares |
| `tfica` | The taxpayer's own payroll taxes: the employee share of Social Security and Medicare, and self-employment tax. On PolicyEngine rows it also includes employee state payroll taxes and contributions, which TAXSIM-35 leaves out |
| `frate`, `srate` | Federal and state marginal rates on wages, in percent. The bundled TAXSIM-35 build returns 0 for both, so ignore them on records before 2021 |
| `v10` | Federal adjusted gross income (with `idtl` 2 or 5) |

Things to know when you use the results:

- **Merge on `taxsimid`, not row order.** The command line and `StitchedRunner` return records in input order. `PolicyEngineRunner` and the R package currently return them grouped by year.
- **Round to cents.** PolicyEngine computes in 32-bit floating point. A value can come back as `4009.199951171875`; it means 4009.20.
- **A file mixing years before and after 2021 has both engines' columns.** Cells an engine doesn't produce are blank, and TAXSIM-35 adds a column named for its build stamp, such as `cd2026081819`.
- **Results depend on the versions installed.** Record the policyengine-taxsim and policyengine-us versions with your results. The [design document](design.md#versions-and-pinning) explains how to pin them.

## Worked example: from a survey file to taxes

This example starts from a survey-style extract with its own column names and codes, builds the TAXSIM input, computes taxes, and merges them back. The six households are made up for this guide. The files are in [`docs/examples/custom-dataset/`](examples/custom-dataset/); copy that folder and run the script for your language there.

The survey extract:

<!-- BEGIN GENERATED: example-survey-csv -->
```csv
hh_id,tax_year,state_fips,marital_status,age_head,age_spouse,num_children,child_age_1,child_age_2,child_age_3,wages_head,wages_spouse,self_emp_head,interest,dividends,pension,social_security,unemployment,rent_paid,property_tax,mortgage_interest,charity,childcare_cost
101,2023,6,1,38,36,2,4,9,,85000,42000,,300,,,,,,5500,12000,1500,6000
102,2023,36,5,27,,1,0,,,38000,,,,,,,,16800,,,,4200
103,2024,12,1,68,66,0,,,,,,,2500,1800,30000,34000,,,3200,,800,
104,2024,48,5,29,,0,,,,52000,,8000,120,,,,,13200,,,,
105,2023,39,1,44,41,3,2,6,15,60000,,,,,,,4000,14400,,,,3000
106,2019,42,3,51,,0,,,,47000,,,900,400,,,,,2100,6000,,
```
<!-- END GENERATED: example-survey-csv -->

It codes marital status 1 as married, gives state FIPS codes, leaves blanks for "none", and records one newborn as age 0 (household 102). The crosswalk in each language does the same five things:

1. Turns blank amounts into zeros.
2. Maps each survey concept to a TAXSIM column, recoding marital status to `mstat` and adding charity to mortgage interest in `mortgage`.
3. Recodes the newborn's age from 0 to 1, and missing ages to 0.
4. Checks for missing values, filing status codes and duplicate IDs, which the emulator would not catch.
5. Computes taxes and merges them back on `taxsimid`, rounded to cents.

### Python

Uses `StitchedRunner`, so household 106 (2019) goes to TAXSIM-35 like it would on the command line.

<!-- BEGIN GENERATED: example-python -->
```python
"""Turn a survey extract into TAXSIM input, compute taxes, and merge them back.

Run from this directory:  python crosswalk.py
survey_extract.csv is made up; swap in your own file and column names.
"""

import pandas as pd

from policyengine_taxsim.runners import StitchedRunner

survey = pd.read_csv("survey_extract.csv")

# 1. Blank amounts mean "none". TAXSIM input has no missing values, so make
#    them zeros.
survey_amounts = [
    "wages_head", "wages_spouse", "self_emp_head", "interest", "dividends",
    "pension", "social_security", "unemployment", "rent_paid",
    "property_tax", "mortgage_interest", "charity", "childcare_cost",
]  # fmt: skip
survey[survey_amounts] = survey[survey_amounts].fillna(0)

# 2. Map each survey concept to a TAXSIM column. This survey codes married
#    as 1; everyone else files as unmarried (head of household with a child).
married = survey["marital_status"] == 1
taxsim = pd.DataFrame(
    {
        "taxsimid": survey["hh_id"],
        "year": survey["tax_year"],
        "statefip": survey["state_fips"],  # FIPS codes; SOI codes go in `state`
        "mstat": married.map({True: 2, False: 1}),
        "page": survey["age_head"],
        "sage": survey["age_spouse"].where(married, 0).fillna(0),
        "depx": survey["num_children"].fillna(0),
        "pwages": survey["wages_head"],
        "swages": survey["wages_spouse"].where(married, 0),
        "psemp": survey["self_emp_head"],
        "intrec": survey["interest"],
        "dividends": survey["dividends"],
        "pensions": survey["pension"],
        "gssi": survey["social_security"],
        "pui": survey["unemployment"],
        "rentpaid": survey["rent_paid"],
        "proptax": survey["property_tax"],
        # Mortgage interest and charity are both itemized deductions that
        # are not AMT preferences, so both go in `mortgage`.
        "mortgage": survey["mortgage_interest"] + survey["charity"],
        "childcare": survey["childcare_cost"],
        "idtl": 2,  # full output
    }
)

# 3. Dependent ages. The emulator reads an age of 0 as "not given" (and uses
#    10), so code infants as 1, as TAXSIM-35 instructs.
for slot in (1, 2, 3):
    age = survey[f"child_age_{slot}"]
    taxsim[f"age{slot}"] = age.mask(age == 0, 1).fillna(0)

# 4. Check before running: the emulator does not reject most bad values.
assert taxsim.notna().all().all(), "recode every missing value first"
assert taxsim["mstat"].isin([1, 2, 6]).all(), "mstat must be 1, 2 or 6"
assert taxsim["taxsimid"].is_unique, "taxsimid must identify each record"

# 5. Keep the TAXSIM input for the record, then compute. StitchedRunner is
#    what the policyengine-taxsim command uses: 2021 and later go to
#    PolicyEngine, earlier years to TAXSIM-35.
taxsim.to_csv("taxsim_input.csv", index=False)
results = StitchedRunner(taxsim).run()

# 6. Merge back on taxsimid. Amounts are computed in 32-bit floating point,
#    so round them to cents. Leave taxsimid alone: it is an identifier.
amounts = ["fiitax", "siitax", "fica", "v10"]
taxes = results[["taxsimid", *amounts]].copy()
taxes[amounts] = taxes[amounts].astype(float).round(2)
merged = survey.merge(taxes, left_on="hh_id", right_on="taxsimid", how="left")
merged.drop(columns="taxsimid").to_csv("survey_with_taxes.csv", index=False)
print(merged[["hh_id", "tax_year", "fiitax", "siitax", "fica", "v10"]])
```
<!-- END GENERATED: example-python -->

### Stata

Writes the TAXSIM input as a Stata file and calls the `policyengine` subcommand, which reads and writes `.dta` directly, so no CSV parsing is involved. It stores the record ID and the amounts as `double`: Stata's default `float` type cannot hold every whole number above 16,777,216, so long survey IDs would collide. Stata's shell must be able to find `policyengine-taxsim`. If it can't, give the full path, for example `! /home/me/taxsim-env/bin/policyengine-taxsim` on Linux or macOS, or `! C:\taxsim-env\Scripts\policyengine-taxsim.exe` on Windows.

<!-- BEGIN GENERATED: example-stata -->
```stata
* Turn a survey extract into TAXSIM input, compute taxes, and merge them back.
* Run from this directory:  do crosswalk.do
* survey_extract.csv is made up; swap in your own file and variable names.
* Stata's shell must find the policyengine-taxsim command (see the guide).

import delimited using "survey_extract.csv", clear asdouble

* 1. Blank amounts mean "none". TAXSIM input has no missing values.
foreach v of varlist wages_head wages_spouse self_emp_head interest dividends ///
    pension social_security unemployment rent_paid property_tax ///
    mortgage_interest charity childcare_cost {
    replace `v' = 0 if missing(`v')
}

* 2. Map each survey concept to a TAXSIM variable. This survey codes married
*    as 1; everyone else files as unmarried. (dividends already has its
*    TAXSIM name.) Store identifiers and amounts as double: Stata's default
*    float type cannot hold every whole number above 16,777,216.
generate double taxsimid = hh_id
generate year = tax_year
generate statefip = state_fips
generate mstat = cond(marital_status == 1, 2, 1)
generate page = age_head
generate sage = cond(mstat == 2, age_spouse, 0)
replace sage = 0 if missing(sage)
generate depx = cond(missing(num_children), 0, num_children)
generate double pwages = wages_head
generate double swages = cond(mstat == 2, wages_spouse, 0)
generate double psemp = self_emp_head
generate double intrec = interest
generate double pensions = pension
generate double gssi = social_security
generate double pui = unemployment
generate double rentpaid = rent_paid
generate double proptax = property_tax
* Mortgage interest and charity are both non-AMT-preference itemized deductions.
generate double mortgage = mortgage_interest + charity
generate double childcare = childcare_cost
generate idtl = 2

* 3. Dependent ages: 0 reads as "not given" (age 10), so code infants as 1.
forvalues i = 1/3 {
    generate age`i' = child_age_`i'
    replace age`i' = 1 if age`i' == 0
    replace age`i' = 0 if missing(age`i')
}

* 4. Check before running: the emulator does not reject most bad values.
local taxsimvars taxsimid year statefip mstat page sage depx age1 age2 age3 ///
    pwages swages psemp intrec dividends pensions gssi pui rentpaid proptax ///
    mortgage childcare idtl
foreach v of local taxsimvars {
    assert !missing(`v')
}
assert inlist(mstat, 1, 2, 6)
isid taxsimid

* 5. Write the TAXSIM input and run the emulator on it. The policyengine
*    subcommand reads and writes Stata files directly.
preserve
keep `taxsimvars'
save "taxsim_input.dta", replace
! policyengine-taxsim policyengine taxsim_input.dta -o taxsim_results.dta
restore

* 6. Merge the results back on taxsimid and round amounts to cents.
merge 1:1 taxsimid using "taxsim_results.dta", ///
    keepusing(fiitax siitax fica v10) nogenerate
foreach v of varlist fiitax siitax fica v10 {
    replace `v' = round(`v', 0.01)
}
save "survey_with_taxes.dta", replace
list hh_id tax_year fiitax siitax fica v10
```
<!-- END GENERATED: example-stata -->

This script has not been run in Stata; the build machine has no Stata license. Its handoff to the emulator (a `.dta` file in, a `.dta` file out, merged on `taxsimid`) is tested by `tests/test_worked_example.py`, which runs the same command on the same input.

### R

Uses base R and the command line, so it needs no R packages and works offline once policyengine-taxsim is installed. The `policyenginetaxsim` R package is an alternative, but it installs Python packages from GitHub on first use and computes every year with PolicyEngine.

<!-- BEGIN GENERATED: example-r -->
```r
# Turn a survey extract into TAXSIM input, compute taxes, and merge them back.
# Run from this directory:  Rscript crosswalk.R
# survey_extract.csv is made up; swap in your own file and column names.
# Needs only base R and the policyengine-taxsim command on the PATH.

survey <- read.csv("survey_extract.csv")

# 1. Blank amounts mean "none". TAXSIM input has no missing values.
amounts <- c(
  "wages_head", "wages_spouse", "self_emp_head", "interest", "dividends",
  "pension", "social_security", "unemployment", "rent_paid",
  "property_tax", "mortgage_interest", "charity", "childcare_cost"
)
survey[amounts][is.na(survey[amounts])] <- 0

# 2. Map each survey concept to a TAXSIM column. This survey codes married
#    as 1; everyone else files as unmarried.
married <- survey$marital_status == 1
taxsim <- data.frame(
  taxsimid = survey$hh_id,
  year = survey$tax_year,
  statefip = survey$state_fips,  # FIPS codes; SOI codes go in `state`
  mstat = ifelse(married, 2, 1),
  page = survey$age_head,
  sage = ifelse(married & !is.na(survey$age_spouse), survey$age_spouse, 0),
  depx = ifelse(is.na(survey$num_children), 0, survey$num_children),
  pwages = survey$wages_head,
  swages = ifelse(married, survey$wages_spouse, 0),
  psemp = survey$self_emp_head,
  intrec = survey$interest,
  dividends = survey$dividends,
  pensions = survey$pension,
  gssi = survey$social_security,
  pui = survey$unemployment,
  rentpaid = survey$rent_paid,
  proptax = survey$property_tax,
  # Mortgage interest and charity are both non-AMT-preference itemized
  # deductions, so both go in `mortgage`.
  mortgage = survey$mortgage_interest + survey$charity,
  childcare = survey$childcare_cost,
  idtl = 2
)

# 3. Dependent ages: 0 reads as "not given" (age 10), so code infants as 1.
for (slot in 1:3) {
  age <- survey[[paste0("child_age_", slot)]]
  age[!is.na(age) & age == 0] <- 1
  age[is.na(age)] <- 0
  taxsim[[paste0("age", slot)]] <- age
}

# 4. Check before running: the emulator does not reject most bad values.
stopifnot(!anyNA(taxsim), all(taxsim$mstat %in% c(1, 2, 6)))
stopifnot(!anyDuplicated(taxsim$taxsimid))

# 5. Write the TAXSIM input, run the emulator, and read the results.
write.csv(taxsim, "taxsim_input.csv", row.names = FALSE)
status <- system2(
  "policyengine-taxsim",
  c("policyengine", "taxsim_input.csv", "-o", "taxsim_results.csv")
)
stopifnot(status == 0)
results <- read.csv("taxsim_results.csv")

# 6. Merge back on taxsimid and round amounts to cents. Leave taxsimid alone:
#    it is an identifier.
tax_columns <- c("fiitax", "siitax", "fica", "v10")
taxes <- results[c("taxsimid", tax_columns)]
taxes[tax_columns] <- round(taxes[tax_columns], 2)
merged <- merge(survey, taxes, by.x = "hh_id", by.y = "taxsimid", all.x = TRUE)
write.csv(merged, "survey_with_taxes.csv", row.names = FALSE)
print(merged[c("hh_id", "tax_year", "fiitax", "siitax", "fica", "v10")])
```
<!-- END GENERATED: example-r -->

### Result

All three scripts print the same taxes. This run used policyengine-taxsim 3.1.1 with policyengine-us 2.38.0 on Python 3.11; other versions can give different amounts.

| hh_id | tax_year | fiitax | siitax | fica | v10 |
|---|---|---|---|---|---|
| 101 | 2023 | 7327.00 | 2566.80 | 19431.00 | 127300.00 |
| 102 | 2023 | -2307.89 | -269.19 | 5814.00 | 38000.00 |
| 103 | 2024 | 1240.50 | 0.00 | 0.00 | 46505.00 |
| 104 | 2024 | 4984.14 | 0.00 | 9086.36 | 59554.82 |
| 105 | 2023 | -2084.00 | 1108.79 | 9180.00 | 64000.00 |
| 106 | 2019 | 4090.00 | 1482.81 | 7191.00 | 48300.00 |

Household 102, the single parent with a newborn, has negative federal and state tax because refundable credits exceed tax. Household 106 was computed by TAXSIM-35 because its tax year is 2019.

## State codes

`state` takes SOI codes; `statefip` takes FIPS codes. Give one or the other.

<!-- BEGIN GENERATED: state-codes -->
| SOI | State | FIPS | SOI | State | FIPS | SOI | State | FIPS | SOI | State | FIPS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AL | 1 | 2 | AK | 2 | 3 | AZ | 4 | 4 | AR | 5 |
| 5 | CA | 6 | 6 | CO | 8 | 7 | CT | 9 | 8 | DE | 10 |
| 9 | DC | 11 | 10 | FL | 12 | 11 | GA | 13 | 12 | HI | 15 |
| 13 | ID | 16 | 14 | IL | 17 | 15 | IN | 18 | 16 | IA | 19 |
| 17 | KS | 20 | 18 | KY | 21 | 19 | LA | 22 | 20 | ME | 23 |
| 21 | MD | 24 | 22 | MA | 25 | 23 | MI | 26 | 24 | MN | 27 |
| 25 | MS | 28 | 26 | MO | 29 | 27 | MT | 30 | 28 | NE | 31 |
| 29 | NV | 32 | 30 | NH | 33 | 31 | NJ | 34 | 32 | NM | 35 |
| 33 | NY | 36 | 34 | NC | 37 | 35 | ND | 38 | 36 | OH | 39 |
| 37 | OK | 40 | 38 | OR | 41 | 39 | PA | 42 | 40 | RI | 44 |
| 41 | SC | 45 | 42 | SD | 46 | 43 | TN | 47 | 44 | TX | 48 |
| 45 | UT | 49 | 46 | VT | 50 | 47 | VA | 51 | 48 | WA | 53 |
| 49 | WV | 54 | 50 | WI | 55 | 51 | WY | 56 |   |  |  |
<!-- END GENERATED: state-codes -->
