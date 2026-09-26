# PolicyEngine TAXSIM emulator vs. BLS's published TAXSIM outputs: CE PUMD 2021–2023

> **PolicyEngine's own comparison.** PolicyEngine ran this analysis on BLS's public-use files. BLS and NBER did not produce, review or endorse it. Numbers were generated on 2026-09-23.

## Summary

- **What was compared.** 116,984 tax-unit records for tax years 2021–2023 from the Consumer Expenditure Survey's NTAXI files, the TAXSIM inputs and outputs BLS publishes. Each record was run through the PolicyEngine TAXSIM emulator and through NBER's current `taxsimtest` build. Both are compared with BLS's published federal and state income tax.
- **Emulator vs. BLS.** Records within $10, all three years pooled:
  - federal: 54.9% for the emulator vs. 58.2% for NBER's current TAXSIM build;
  - state: 57.5% vs. 60.3%.

  For tax year 2022 the emulator matches BLS's federal figure slightly more often than current TAXSIM (66.5% vs. 65.5%). Weighted federal totals are 94–97% of BLS's; state totals are 93–101%.
- **Most disagreement is with TAXSIM's own history, not the emulator.** Today's TAXSIM reproduces BLS's published federal figures for only 36–67% of records, depending on the release (state: 47–69%). BLS's figures come from TAXSIM runs made for each release (the NTAXI files are dated September 2023 and October 2024), and TAXSIM changes from build to build: the September 2026 update alone changes state tax in 109 of 1,560 test records (policyengine-taxsim #1206). For some releases BLS also defined the output differently. For example, the 2021 federal figure in the 2021 file excludes the recovery rebate.
- **Three emulator fixes came out of this work** and raise its agreement with current TAXSIM on these records from 73.2% to 85.2% (federal) and from 68.9% to 71.4% (state):
  - `otheritem`, now routed alongside `mortgage` (PR #1205);
  - TAXSIM-32 dependent counts (`dep13`/`dep17`/`dep18`), which were ignored (PR #1217);
  - the `mstat` 8 dependent filer (PR #1218).
- **The NTAXI files have data issues worth BLS's attention.** In the 2022 and 2023 releases the detail outputs sit one TAXSIM column off their labels, and FILESTAT 8 is still used although the dictionary retires it in 2018.

## Results

### Agreement with BLS's published outputs (share of records within $10)

The federal column puts every source on BLS's basis for each release. For the 2021 PUMD current-year file that means tax before the 2021 recovery rebate (TAXSIM `fiitax + cares`), which is what that file's FTAXO matches (57.8% of records for current TAXSIM, vs. 7.3% for `fiitax`). The 2021 prior-year run in the 2022 file includes the rebate.

"taxsimtest" is NBER's current build. "main" is the emulator before the fixes. "fixed" is the emulator after them.

| Tax year | BLS file (period) | Records | Federal: taxsimtest | Federal: main | Federal: fixed | State: taxsimtest | State: main | State: fixed |
|---|---|---|---|---|---|---|---|---|
| 2021 | 2021 CY | 24,574 | 57.8% | 42.9% | 49.3% | 54.0% | 49.8% | 51.0% |
| 2021 | 2022 PY | 23,308 | 65.7% | 48.3% | 56.1% | 68.7% | 61.8% | 63.4% |
| 2022 | 2022 CY | 23,308 | 66.6% | 60.0% | 67.6% | 66.1% | 62.3% | 64.2% |
| 2022 | 2023 PY | 22,897 | 64.3% | 57.9% | 65.3% | 65.4% | 61.7% | 63.4% |
| 2023 | 2023 CY | 22,897 | 36.2% | 32.2% | 36.5% | 47.4% | 45.5% | 45.7% |

### Weighted totals (FINLWT21/4 per quarterly file)

| Tax year | BLS file (period) | Federal BLS total | Federal taxsimtest/BLS | Federal fixed/BLS | State BLS total | State taxsimtest/BLS | State fixed/BLS |
|---|---|---|---|---|---|---|---|
| 2021 | 2021 CY | $1,075.5B | 0.950 | 0.950 | $327.1B | 0.964 | 0.932 |
| 2021 | 2022 PY | $852.7B | 0.956 | 0.950 | $357.1B | 0.980 | 0.948 |
| 2022 | 2022 CY | $1,316.9B | 0.973 | 0.967 | $335.5B | 0.944 | 1.007 |
| 2022 | 2023 PY | $1,525.2B | 0.974 | 0.966 | $379.1B | 0.941 | 0.999 |
| 2023 | 2023 CY | $1,494.7B | 0.948 | 0.941 | $369.6B | 0.968 | 0.981 |

### Emulator agreement with current TAXSIM (share within $10)

| Tax year | BLS file (period) | Records | Federal: main | Federal: fixed | State: main | State: fixed |
|---|---|---|---|---|---|---|
| 2021 | 2021 CY | 24,574 | 68.0% | 78.5% | 69.1% | 71.9% |
| 2021 | 2022 PY | 23,308 | 66.3% | 78.7% | 68.2% | 71.2% |
| 2022 | 2022 CY | 23,308 | 78.2% | 90.3% | 67.1% | 69.5% |
| 2022 | 2023 PY | 22,897 | 76.4% | 89.1% | 67.8% | 69.9% |
| 2023 | 2023 CY | 22,897 | 77.3% | 89.7% | 72.4% | 74.6% |

### Where the fixes matter (emulator vs. current TAXSIM, all years)

| Group | Records | Federal: main | Federal: fixed | State: main | State: fixed |
|---|---|---|---|---|---|
| adult dependents (depx > dep18) | 21,483 | 23.9% | 68.4% | 65.6% | 75.4% |
| mstat 8 (dependent filer) | 5,420 | 58.0% | 99.8% | 50.9% | 52.9% |
| other | 46,090 | 92.7% | 93.3% | 75.5% | 75.5% |
| otheritem > 0 | 43,991 | 78.6% | 83.1% | 66.0% | 67.5% |

### By state and year: emulator ("fixed") vs. BLS, share within $10

States without an income tax, and records whose state BLS suppressed, have zero state tax in every source.

| State | Records | Federal 2021 | Federal 2022 | Federal 2023 | State 2021 | State 2022 | State 2023 |
|---|---|---|---|---|---|---|---|
| (suppressed) | 9,847 | 54.0% | 72.6% | 46.1% | 100.0% | 100.0% | 100.0% |
| AK | 1,926 | 31.6% | 43.0% | 27.3% | 100.0% | 100.0% | 100.0% |
| AL | 1,943 | 56.2% | 73.8% | 44.5% | 43.0% | 37.9% | 36.9% |
| AZ | 2,531 | 57.9% | 75.8% | 49.2% | 45.4% | 62.1% | 35.1% |
| CA | 14,424 | 54.9% | 67.3% | 32.8% | 50.5% | 62.6% | 27.7% |
| CO | 2,182 | 53.4% | 58.2% | 23.5% | 0.0% | 0.0% | 0.6% |
| CT | 1,969 | 42.5% | 50.4% | 28.2% | 30.3% | 27.8% | 18.8% |
| DC | 195 | 34.0% | 43.8% | 36.0% | 30.2% | 39.1% | 16.0% |
| DE | 130 | 53.2% | 71.1% | 40.0% | 31.2% | 0.0% | 0.0% |
| FL | 7,275 | 60.0% | 76.2% | 44.7% | 100.0% | 100.0% | 100.0% |
| GA | 2,320 | 53.4% | 65.8% | 31.7% | 23.6% | 22.8% | 21.6% |
| HI | 2,344 | 49.8% | 57.7% | 29.8% | 0.4% | 1.5% | 0.2% |
| IA | 95 | 57.1% | 53.8% | 7.1% | 31.0% | 23.1% | 7.1% |
| IL | 3,343 | 54.5% | 64.9% | 32.6% | 1.3% | 3.2% | 2.0% |
| IN | 449 | 61.6% | 89.2% | 48.8% | 81.3% | 0.0% | 0.0% |
| KS | 960 | 43.3% | 61.9% | 42.1% | 35.0% | 60.8% | 28.9% |
| KY | 1,166 | 58.8% | 73.6% | 38.1% | 66.8% | 65.4% | 31.2% |
| LA | 2,155 | 67.7% | 87.4% | 43.0% | 52.5% | 67.2% | 28.9% |
| MA | 3,669 | 54.3% | 65.6% | 28.3% | 18.3% | 16.1% | 9.5% |
| MD | 2,548 | 44.3% | 61.3% | 29.8% | 42.3% | 55.3% | 21.6% |
| MI | 2,931 | 53.9% | 67.7% | 38.5% | 47.5% | 62.0% | 7.8% |
| MN | 1,991 | 38.4% | 51.1% | 25.2% | 8.1% | 1.9% | 1.0% |
| MO | 1,646 | 46.9% | 55.5% | 32.4% | 38.7% | 19.6% | 11.4% |
| MS | 480 | 50.5% | 76.0% | 60.7% | 69.8% | 77.7% | 51.7% |
| NC | 5,063 | 56.6% | 70.1% | 37.8% | 47.6% | 67.9% | 36.6% |
| NE | 1,881 | 45.4% | 55.3% | 31.0% | 45.8% | 57.1% | 26.3% |
| NH | 179 | 29.7% | 40.8% | 31.0% | 100.0% | 100.0% | 100.0% |
| NJ | 1,915 | 48.3% | 59.7% | 30.6% | 47.8% | 91.3% | 33.7% |
| NV | 1,326 | 54.5% | 65.2% | 28.0% | 100.0% | 100.0% | 100.0% |
| NY | 6,218 | 55.7% | 68.7% | 40.8% | 36.1% | 46.8% | 0.8% |
| OH | 4,109 | 51.0% | 61.8% | 35.6% | 56.0% | 66.7% | 42.2% |
| OK | 779 | 48.3% | 70.9% | 42.5% | 50.6% | 68.1% | 16.6% |
| OR | 1,834 | 44.5% | 55.3% | 32.6% | 33.1% | 48.7% | 23.7% |
| PA | 3,954 | 51.6% | 62.2% | 30.1% | 93.6% | 95.5% | 95.2% |
| SC | 1,371 | 52.6% | 67.3% | 46.1% | 50.2% | 47.9% | 44.0% |
| SD | 740 | 47.0% | 62.8% | 30.6% | 100.0% | 100.0% | 100.0% |
| TN | 950 | 43.0% | 73.3% | 45.0% | 100.0% | 100.0% | 100.0% |
| TX | 6,564 | 56.2% | 72.8% | 39.8% | 100.0% | 100.0% | 100.0% |
| UT | 2,684 | 50.9% | 62.6% | 34.6% | 62.6% | 65.5% | 30.7% |
| VA | 2,662 | 47.9% | 68.3% | 37.4% | 23.0% | 65.9% | 29.3% |
| WA | 2,364 | 42.5% | 50.3% | 29.0% | 100.0% | 92.8% | 92.2% |
| WI | 3,176 | 54.1% | 66.5% | 34.6% | 45.1% | 60.0% | 28.0% |
| WV | 696 | 51.4% | 73.5% | 46.7% | 65.8% | 65.2% | 25.7% |

## Why BLS's numbers differ from today's TAXSIM

These are observations from rerunning BLS's inputs; BLS's run settings are not published in the files.

- **2021 current-year federal (2021 PUMD):** FTAXO excludes the 2021 recovery rebate. It matches current TAXSIM `fiitax + cares` in 57.8% of records and `fiitax` in 7.3%.
- **2023 current-year (2023 PUMD):** only 36% of federal and 47% of state figures match current TAXSIM. Rerunning TAXSIM with the tax year set to 2022 matches fewer records (27% federal), so BLS did not simply run the prior year's law. The cause is unidentified.
- **Payment-year rebates:** current TAXSIM, in default mode, books one-time state rebates in the year they are paid. The emulator books them in the liability year (TAXSIM's `opt(30)` convention). Colorado's 2021 rebate therefore shows a median emulator − TAXSIM gap of −$757 in 2021 and +$750 in 2022.
- **The current TAXSIM build disagrees with BLS where BLS agrees with the emulator:**
  - **Maryland:** the current build returns roughly double the state-only tax. For a $200K single filer in 2023: TAXSIM $15,746, BLS $7,729, emulator $8,982. The emulator zeroes Maryland local tax because TAXSIM input carries no county.
  - **New York:** for some high-income 2022–2023 families the current build returns large negative state tax (e.g. −$60,698), where BLS published $15,728 and the emulator gives $15,952.

## Remaining known emulator vs. TAXSIM differences

Each of these is documented in the repository or the linked PRs.

- **2021 credit for other dependents:** TAXSIM pays it to filers with no tax liability. The 2021 Schedule 8812 instructions call it "a nonrefundable credit for other dependents (ODC)", and the emulator treats it as nonrefundable. This is the main reason adult-dependent records agree less in 2021: TAXSIM's larger refundable credit accounts, within $10, for 79% of those mismatches.
- **2021 CTC for 17-year-olds under count inputs:** given dependent counts, TAXSIM allows the $3,000 2021 CTC only for `dep17` children. The 2021 instructions extend it to children "who have not attained age 18 by the end of 2021"; TAXSIM itself allows it when given explicit ages; the emulator allows it.
- **`otheritem` in eight states:** AR, DE, IA (2020–22), KS, ME, MS, NC and WI (2023+). TAXSIM leaves `otheritem`, but not `mortgage`, out of the state itemized deduction; the emulator treats them alike.
- **Additional Medicare Tax:** TAXSIM folds it into federal tax for 2021–2023; the emulator reports it separately in every year.
- **Suppressed-state records:** the emulator simulates them in Texas and takes PolicyEngine's sales-tax deduction, which TAXSIM does not take at state 0.
- **Dependent-filer standard deduction:** TAXSIM's minimum lags the IRS amount by a year in 2022–2024. PolicyEngine follows the IRS (Rev. Proc. 2021-45, 2022-38, 2023-34).

## Data

- **Source.** BLS Consumer Expenditure Survey public-use microdata (PUMD), interview files `intrvw21.zip`, `intrvw22.zip` and `intrvw23.zip` from https://www.bls.gov/cex/pumd_data.htm, downloaded 2026-09-22. Each contains four quarterly NTAXI files (tax-unit TAXSIM inputs and outputs), 70,779 tax-unit rows in total. FMLI supplies FINLWT21 weights.
- **Periods.** For each row BLS ran TAXSIM twice: for the current tax year (`*_CY`, equal to the PUMD year) and for the prior tax year (`*_PY`). This comparison covers every run for tax years 2021–2023, 116,984 in all:
  - 2021: 2021 PUMD CY and 2022 PUMD PY
  - 2022: 2022 PUMD CY and 2023 PUMD PY
  - 2023: 2023 PUMD CY

  2023 has no prior-year run because the NTAXI series ends with the 2023 PUMD.
- **Inputs.** NTAXI inputs map to TAXSIM variables following Curtin (2017), ["Calculating Inputs for the NBER TAXSIM model, using the CE PUMD"](https://www.bls.gov/cex/research_papers/pdf/curtin-calculating-inputs-for-the-nber-taxsim-model-using-the-consumer-expenditure-survey-public-use-microdata.pdf). Its 22 variables are TAXSIM-9's 22 inputs in order. Dividend income cannot be isolated in CE, so BLS sets DIVINC to 0 everywhere.

| NTAXI | TAXSIM | NTAXI | TAXSIM |
|---|---|---|---|
| AGE_TP / AGE_SP | page / sage | TAXPENS | pensions |
| FILESTAT | mstat | SOSSECB | gssi |
| SOI_ST | state | NONTXINC | transfers |
| DEPCNT | depx | RNTPAID | rentpaid |
| DEPUND13 / 17 / 18 | dep13 / dep17 / dep18 | PROPTXPD | proptax |
| WAGE_HD / WAGE_SP | pwages / swages | AMTDEDCT | otheritem |
| DIVINC | dividends | CHLDCARE | childcare |
| OTHTXINC | otherprop | OTHDEDCT | mortgage |

- **Outputs compared.** Federal income tax after credits (FTAXO → `fiitax`) and state income tax after credits (STAXO → `siitax`).

## Sources compared

- **BLS**: the TAXSIM outputs published in NTAXI. BLS computed these when each PUMD release was produced; the TAXSIM build it used is not documented in the files.
- **taxsimtest (current)**: NBER's `taxsimtest` build cd2026081819 (August 2026), bundled with the emulator, run on the same inputs. It shows how much of any gap is TAXSIM itself changing since BLS ran it.
- **Emulator, before**: policyengine-taxsim at v2.31.3 (`f9717eb`), which ignored `otheritem` and TAXSIM-32 dependent counts and treated `mstat` 8 as single.
- **Emulator, after**: `main` at `cef2b2f` plus the three fixes from this work:
  - `otheritem` routed with `mortgage` (PR #1205);
  - TAXSIM-32 dependent counts honored (PR #1217);
  - `mstat` 8 dependent filers (PR #1218).

Agreement means the two sources are within $10 of each other for a record. Weighted totals use FINLWT21/4 per quarterly file.

## Data-quality findings in the NTAXI files

1. **The 2022 and 2023 PUMD detail outputs sit one TAXSIM column off their labels.** Each BLS column was matched against today's taxsimtest columns on the same inputs:
   - In the 2021 PUMD, labels line up (FICA_CY = `fica` in 90% of rows; CHDTX = `v22` in 96%).
   - In the 2022 and 2023 PUMD files (CY and PY), each detail variable holds the TAXSIM output one position earlier. Match rates below are for the 2022 PUMD CY run; other runs show the same pattern:
     - FDAGI (AGI) holds `tfica`: 94% exact.
     - STAGI (state AGI) holds `v31`: 100%.
     - EITCR holds the child care credit `v24`: 95%.
     - AMTIN holds the EITC `v25`: 92%.
     - SSTDD holds `v33`: 89%.
     - SITDD holds `v34`: 86%.

     FTAXO and STAXO appear correctly placed.
2. **FILESTAT 8 is still in use.** The CE dictionary says the dependent-taxpayer code ended in 2018Q2. The 2021–2023 files still code 3,239 tax-unit rows (4.6%) as FILESTAT 8, and no row uses code 3 (head of household). TAXSIM infers head of household from dependents.
3. **Two records crash taxsimtest.** They are the same New Jersey tax unit in tax years 2022 and 2023: `mstat` 8, age 65, $7,265 of wages, nothing else. The current build segfaults on both, and they are excluded from the taxsimtest columns.
4. **5,979 rows have a suppressed state** (SOI_ST = 0). TAXSIM computes no state tax for them. The emulator simulates them in Texas; see the caveats.


## Caveats

- Agreement within $10 is strict. Most BLS values are rounded to whole dollars, and TAXSIM outputs cents.
- BLS's TAXSIM version and options for each release are not documented in the files. "Current TAXSIM" is one build (cd2026081819) and is itself changing; see policyengine-taxsim #1206 and #1208.
- Weighted totals scale FINLWT21 by 1/4 per quarterly file. That is adequate for comparing sources with each other, but these are not official annual CE estimates.
- The "fixed" emulator is `main` at `cef2b2f` plus #1205, #1217 and #1218, which were open at the time of writing.

## Reproducing

From the repository root:

```bash
scripts/ce_pumd_download.sh ce_data 21 22 23
python scripts/ce_pumd_comparison.py build ce_data ce_out
python scripts/ce_pumd_comparison.py taxsim ce_out
for y in 2021 2022 2023; do python scripts/ce_pumd_comparison.py emulator ce_out --label fixed --year $y; done
python scripts/ce_pumd_comparison.py report ce_out --label fixed
```

`build` maps NTAXI to TAXSIM inputs as in the table above. `taxsim` runs the bundled binary in chunks and isolates any records that crash it. `report` prints the agreement tables; the federal comparison is put on BLS's basis for each release.
