# policyengine-taxsim

See [PolicyEngine/CLAUDE.md](../CLAUDE.md) for org-wide conventions.

## Evidence rules for filing issues and PRs (any repo)

Hard requirements, born of pe-us #8830/#8911 — an issue that asserted the 2021
OK Form 511 omitted IRC §401 pensions while citing the exact page that lists
them first; it merged unreviewed and had to be reverted (#9009).

1. **Verbatim extraction or it didn't happen.** Any claim about what a statute,
   form, or instruction says must be backed by the operative language extracted
   mechanically (`pdftotext -layout`, statute HTML) and pasted into the filing
   as a labeled blockquote (document, year, page). A citation link alone is not
   evidence.
2. **Negative claims ("X is not listed") require extracting the full relevant
   section** and showing the absence. **Year-change claims ("added in year Y")
   require both years' documents extracted and diffed.**
3. **Engine outputs (TAXSIM, TaxAct, PE) generate hypotheses, never evidence.**
   Do not backfill a legal narrative to explain engine behavior.
4. **Test expectations must come from an external ground truth** (TaxAct PDF,
   TAXSIM binary output, worked example in official instructions) — never from
   the hypothesis being encoded. Premise-derived tests are circular.
5. **Verify each quote's scope, not just its existence** — name the section/
   heading it sits under and who it applies to (pe-us #8831 quoted real lines
   but from the wrong section, producing a wrong carve-out that merged).
6. **Re-read the cited page after drafting**, before posting: does it still
   support the claim as written?

The full workflow (extraction how-tos, pre-filing checklist) lives in
`.claude/commands/diagnose-issue.md` (Critical Rules 5–8, Step 7, Step 9).

## Changelog

**Never manually edit `CHANGELOG.md`.** It is auto-generated on merge by towncrier.

Instead, add a fragment file in `changelog.d/`:

```bash
echo "Description of change." > changelog.d/<branch-name>.<type>.md
```

Fragment types and their semver bumps:
- `breaking` → **major** (reserved for breaking API changes)
- `added` → **minor**
- `removed` → **minor**
- `changed` → **patch**
- `fixed` → **patch**

Fragment names can be anything (branch name, issue number, short description). Examples:
- `changelog.d/add-new-endpoint.added.md`
- `changelog.d/fix-age-default.fixed.md`
- `changelog.d/123.fixed.md`

## Spousal income allocation (MFJ)

TAXSIM gives several income types as a single household column with no
per-spouse split. For married-filing-jointly records, the emulator allocates
them between spouses by this rule (evidence-backed against the NBER
`taxsimtest` binary; see taxsim issues #774, #924, #965, #966):

- **Interest, dividends, capital gains, S-corp income, nonprop → always split
  50/50.** (nonprop is signed; see "TAXSIM nonprop" below.)
- **Pensions and Social Security → age-aware:**
  - Both spouses on the **same side** of the elderly-eligibility line (both
    qualify, or both do not) → **split 50/50**.
  - **Mixed-age** (one qualifies, one does not) → assign the **whole amount to
    the older spouse**, so age-based state exclusions (CO 55, DE 60, GA 62,
    MD 65) reach the qualifying filer.

Rationale: 50/50 matches TAXSIM and gives both spouses age-*independent*
per-person exclusions (e.g. KY, OK), while the mixed-age exception protects
age-*based* exclusions from being half-wasted on an ineligible younger spouse.
The full age-aware rule lives in `runners/policyengine_runner.py` (the
Microsimulation/CLI path), keyed on `_AGE_GATED_SPLIT_AGE` (55, the lowest
state threshold). Note the single-household path in `core/input_mapper.py`
(`income_types_to_split`) currently splits these types 50/50 *unconditionally*
— correct for same-age couples but not yet age-aware for mixed-age pensions/SS;
align it with the runner if that path is used for mixed-age elderly records.

## TAXSIM nonprop (signed other income)

TAXSIM `nonprop` is "Other non-property income in AGI not subject to Medicare
NIIT" (alimony, nonwage fellowships, itemizers' state refunds), and
adjustments (alimony paid, IRA contributions, NOLs) "can be entered here as
negative income". `nonprop_parts` in `core/utils.py` routes it, and both
emulator paths use it (taxsim #1424, #1245):

- **Positive → `miscellaneous_income`**, except **`alimony_income` in AL, AR
  and MS** (`NONPROP_ALIMONY_STATES`). PE-US's gross-income lists for those
  three states name alimony but not miscellaneous income, so
  `miscellaneous_income` would go untaxed there while taxsimtest taxes
  nonprop. Drop a state from the set once PE-US adds `miscellaneous_income`
  to its list.
- **Negative → `alimony_expense`** (magnitude), an uncapped above-the-line
  deduction. PE-US floors each gross-income source at zero, so a negative
  income variable would be lost.
- Do **not** route positive nonprop to `alimony_income` elsewhere: PE-US gives
  alimony treatment taxsimtest does not give nonprop. Georgia excludes it as
  retirement income at 62+, and Pennsylvania tax forgiveness and Rhode Island
  property-tax relief add alimony on top of income that already holds it.

Known taxsimtest divergences (documented in `tests/test_nonprop_mapping.py`
and taxsim #1424, not emulated):

- taxsimtest counts nonprop as earned income for the EITC and the refundable
  CTC; IRC 32(c)(2)(A) covers only employee compensation and self-employment
  earnings. The same treatment moves state EITCs and the WI married-couple
  credit.
- PE-US counts a spouse's half of nonprop toward the OH joint filing credit's
  qualifying income; taxsimtest does not.
- PE-US's household-income credits in MI, WI and AZ move with nonprop as they
  do with interest; taxsimtest's move with interest but not with nonprop.
- Arkansas: PE-US applies no adjustments to Arkansas income (`ar_agi_indiv` is
  gross income minus exemptions), so negative nonprop does not lower Arkansas
  tax; taxsimtest's does.

## Married filing separately (mstat 6)

TAXSIM-35 mstat 6 is one spouse's separate return ("6. separate (married)";
TAXSIM rejects nonzero `sage`/`swages` for it). Both emulator paths
(`runners/policyengine_runner.py` and `core/input_mapper.py`, keyed on
`MSTAT_MARRIED_SEPARATE`) build a **single-person tax unit** — never a spouse —
with the head's `is_separated` and the unit's `cohabitating_spouses` set:

- PE-US then computes filing status SEPARATE, or HEAD_OF_HOUSEHOLD when a
  qualifying child lets IRC 7703(b) treat the filer as unmarried. taxsimtest
  does the same (mstat 6 with a child gets HOH deduction, brackets, EITC).
- `cohabitating_spouses` gives the IRC 86(c)(1)(C) zero Social Security base,
  which taxsimtest applies to mstat 6, NJ's half property-tax deduction for
  separate filers sharing a main home (which taxsimtest does not apply), and
  AZ's property-tax-credit table for claimants living with others (which moves
  PE the same direction as taxsimtest). The
  zero base covers a filer who "does not live apart from his spouse at all
  times during the taxable year"; a TAXSIM row cannot say the filer lived apart
  all year, so the emulator assumes they did not, as taxsimtest does.

Known taxsimtest divergences (documented in
`tests/test_married_filing_separately.py`, not emulated): Additional Medicare
threshold ($200k vs the §3101(b)(2)(B) $125k), the 2025 senior deduction
(allowed vs §151(d)(5)(C)(v)'s joint-return requirement), childless EITC
(PE-US allows it via `eitc.eligibility.separate_filer`), mstat 6 with a
non-qualifying-child dependent (taxsimtest HOH, PE-US SEPARATE), and NY
2022-2025, where taxsimtest returns siitax 0 (staxbc -1e20) for every mstat 6
record without dependents (records with dependents are computed normally).

## Running tests

```bash
pytest tests/
```

Tests marked `slow` are wall-clock benchmarks with absolute time limits
(`TestBenchmark` in `tests/test_performance.py`). `tests/conftest.py` skips
them unless a `-m` expression is given, so they stay out of CI, where runner
speed decided whether they passed (#1429). Run them on request:

```bash
pytest tests/ -m slow
```

Do not add a test that compares elapsed time with a fixed number of seconds to
the default run. Check structure instead (count calls, as
`test_extract_builds_dataframe_without_row_loop` does).
