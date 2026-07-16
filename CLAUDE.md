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

- **Interest, dividends, capital gains, S-corp income → always split 50/50.**
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

## Running tests

```bash
pytest tests/
```
