# TAXSIM Issue Diagnosis Workflow

You are helping diagnose discrepancies between PolicyEngine and TAXSIM tax calculations.

## Critical Rules

1. **Compare current PE vs TaxAct.** Only the current PE-US install matters for diagnosis; the reporter's PE version in `output.txt` is useful for triage (Step 0b) but never for the actual comparison. True TAXSIM-proper output is rarely in the bundle — don't pretend to compare against it if it isn't there.
2. **NEVER post GitHub issues, comments, or PRs without explicit user confirmation.** Always show draft content first and wait for approval.
3. **Phrase TAXSIM issues as questions** (e.g., "Does TAXSIM-35 incorrectly apply...?" not "TAXSIM-35 incorrectly applies...").
4. **Verify against primary sources, not search summaries.** When PE and TaxAct disagree on a specific credit or deduction, fetch the actual statute text + current-year form PDF + instructions booklet (see Step 7). Web-search summaries about state tax law are routinely wrong or stale.

## Repositories

You have access to two local repositories:
1. **policyengine-taxsim** (`/Users/pavelmakarchuk/policyengine-taxsim`) - The TAXSIM emulator
2. **policyengine-us** (`/Users/pavelmakarchuk/policyengine-us`) - The US tax rules implementation

GitHub:
- https://github.com/PolicyEngine/policyengine-taxsim (issues are filed here)
- https://github.com/PolicyEngine/policyengine-us (fixes go here)

## Issue Structure

Each issue at https://github.com/PolicyEngine/policyengine-taxsim/issues contains:
1. **Title pattern**: `{STATE} {filing_status} {year} {income_description}` (e.g., "NJ joint 2024 elderly 129Kintrec")
2. **Description/Comments** - Often contains diagnostic hints, suspected root cause, or specific observations from the filer (READ THIS CAREFULLY - it often points to the problem)
3. **TaxAct PDFs** - Federal 1040, the state form, and any relevant schedules
4. **TAXSIM reference files** - Available at `taxsim.nber.org/out2psl/{issue_number}/`. Typical contents: `txpydata.csv` (input), `output.txt` (PE emulator output with version banner), `<issue>.txt` (full run log), and one or more PDFs. There is **no YAML file** — don't expect one.

**IMPORTANT**: The issue description often contains the filer's analysis of what's wrong. Start by reading the description carefully before diving into code.

### TAXSIM Reference Files

Fetch all TAXSIM data in ONE batch (the server is unreliable, minimize requests):

```bash
ISSUE={issue_number}
mkdir -p /tmp/taxsim_$ISSUE && cd /tmp/taxsim_$ISSUE

# Batch download all files
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/" -o index.html
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/$ISSUE.txt" -o $ISSUE.txt &
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/output.txt" -o output.txt &
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/txpydata.csv" -o txpydata.csv &
wait

# Download any PDFs
grep -oP 'href="\K[^"]+\.pdf' index.html | while read pdf; do
  curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/$pdf" -o "$pdf" &
done
wait
```

Then work ENTIRELY from local files - no more network calls to TAXSIM.

## Diagnostic Steps

### Step 0: Pre-diagnosis triage (DO THIS FIRST — it short-circuits a lot of work)

Three quick checks before any file downloads or PE runs. If any of them fires, you may be done in 5 minutes instead of an hour.

**0a. Is this a bug report or an informational question?**

Read the issue body. If the reporter is asking *what PE does* or *how PE handles X* (e.g., "What does PE use for fuel cost?") without claiming a specific wrong value, this is **informational**. Skip the full diagnosis — answer their question directly with code references, draft a comment, and confirm before posting. Don't file a PE-US issue.

If the body claims a specific discrepancy ("PE returns $X, TaxAct returns $Y, should be $Z"), it's a **bug claim** — continue.

**0b. Is this already fixed in current PE?**

```bash
# Reporter's PE-US version (printed in <issue>.txt near the top)
grep -A1 "policyengine-us" /tmp/taxsim_$ISSUE/$ISSUE.txt | head -3

# Local PE-US version
pip show policyengine-us | grep -i version
```

If the local version is much newer than the reporter's, grep the changelog for relevant state/feature work in the gap:

```bash
cd /Users/pavelmakarchuk/policyengine-us && grep -in "<state-name>\|<state-abbrev>" CHANGELOG.md | head -20
```

If a relevant fix landed between the reporter's version and yours, run a quick PE-direct test with the current version (Step 3) to confirm the issue no longer reproduces. If it doesn't reproduce, close with a brief "after model adjustments, the values now align" comment and stop.

**0c. Is there already an open PE-US issue or PR tracking this?**

```bash
gh search issues --repo PolicyEngine/policyengine-us "<state> <variable-or-symptom>" --include-prs \
  --json number,title,state,url
```

Try a few queries (state name, specific PE variable, taxsim issue number). If there's an existing tracking issue or open PR that addresses this, just cross-link with a short comment ("Will be addressed here: <PR link>") and stop.

Only if all three checks say "still relevant, fresh problem" do you go to Step 1.

### Step 1: Read the Issue
- Fetch the issue from GitHub (`gh issue view {number} --repo PolicyEngine/policyengine-taxsim`)
- Read the description carefully for diagnostic hints
- Note any specific numbers mentioned (PE vs TaxAct values)

Treat the issue body as a *hypothesis*, not as fact. If the reporter cites a specific PE value, confirm it appears in the bundled `output.txt` before building a diagnosis around it. Reporters sometimes mix up cases. If the cited value isn't there, work from what `output.txt` actually shows.

### Step 2: Verify the Input Parameters
**CRITICAL**: Before deep-diving into code, verify the TAXSIM input parameters are correct!

Common data entry errors to check:
- **State code**: TAXSIM uses alphabetical numbering (1-51), NOT FIPS codes!
- **Filing status (mstat)**: `1=single`, `2=joint`, `6=dependent`. Note: TAXSIM has no separate HoH code — **PE infers HoH from `mstat=1` with `depx≥1`**. So `mstat=1, depx=0` is true single; `mstat=1, depx≥1` is HoH. Most recent issues are HoH despite `mstat=1`.
- **Ages (page/sage)**: Required for age-based provisions

### Step 3: Test with PolicyEngine Directly
Run a quick test to see what PE actually calculates:

```bash
# Create test CSV
echo "taxsimid,year,state,mstat,page,sage,depx,pwages,swages,intrec,idtl
{id},{year},{state},{mstat},{page},{sage},{depx},{pwages},{swages},{intrec},2" > /tmp/test.csv

# Run PE
python policyengine_taxsim/cli.py policyengine /tmp/test.csv -o /tmp/output.csv
cat /tmp/output.csv
```

### Step 4: Comparison table

Compare current PE values against the TaxAct PDF. **Every PE value in the table must come from a direct PE query (Step 3 CSV output or a `Simulation.calculate(...)` call)** — never infer a PE value from gaps between other variables. If you want the pension deduction, query `me_pension_income_deduction` directly; don't subtract AGI − federal AGI.

| Variable | Current PE (queried) | TaxAct (PDF) | Who's right? |
|----------|----------------------|--------------|--------------|
| siitax   |                      |              |              |
| fiitax   |                      |              |              |
| v10      |                      |              |              |
| v32      |                      |              |              |
| v36      |                      |              |              |

**If v32=0 for a state tax issue**: The state isn't being set correctly. Check the state code!

### Step 5: Extract and Analyze TaxAct PDF Forms (MANDATORY)

**THIS STEP IS CRITICAL AND MUST NOT BE SKIPPED.**

The TaxAct PDFs contain the actual filled-out tax forms — this is the ground truth. Issues usually bundle multiple PDFs (federal 1040, the state form, and any relevant schedules). Iterate them:

```bash
python3 -c "
import fitz, glob
for path in sorted(glob.glob('/tmp/taxsim_$ISSUE/*.pdf')):
    print(f'=== FILE: {path} ===')
    doc = fitz.open(path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f'--- Page {page_num + 1} ---')
        print(page.get_text())
"
```

#### What to Look For in the PDF:

1. **Filing Status** - Which box is checked?
2. **Exemptions** - Total amount and how allocated between spouses
3. **Standard/Itemized Deductions** - Amount and allocation
4. **Income by Line** - Wages, interest, dividends, etc. for each spouse
5. **Taxable Income** - Final taxable income for each spouse
6. **Tax Due** - The actual tax calculated on the form
7. **Credits** - Which credits were claimed and amounts

**If the reporter's claim and the PDF differ, the PDF is correct.** Numeric claims in issue bodies are sometimes paraphrased or based on a stale PE run.

### Step 6: Deep Dive if Needed

If the basic test shows incorrect values, drop into a direct `Simulation` to inspect individual variables.

**WARNING — input parity is critical.** If you write a `Simulation` situation that omits one of the TAXSIM inputs, the simulation will compute different intermediates than the emulator and you'll mis-attribute a real bug to a "framework difference." (Real example: omitting `tax_unit_childcare_expenses` zeroed out the federal CDCC in direct `Simulation`, which changed `tax_liability_if_not_itemizing` by ~$300 and made me think Microsim vs Simulation diverged when they actually agreed.)

**Mandatory TAXSIM-input → PE-variable cross-walk before running:**

| TAXSIM input | PE-US variable | Entity |
|---|---|---|
| `pwages`, `swages` | `employment_income` | person |
| `intrec` | `taxable_interest_income` | person |
| `pensions` | `taxable_pension_income` | person |
| `gssi` | `social_security` | person |
| `proptax` | `real_estate_taxes` | person |
| `mortgage` | `deductible_mortgage_interest` | person |
| `rentpaid` | `rent` | person |
| `childcare` | `tax_unit_childcare_expenses` | **tax_unit** ← easy to miss |
| `dividends` | `qualified_dividend_income` | person |
| `stcg` | `short_term_capital_gains` | person |
| `ltcg` | `long_term_capital_gains` | person |

Always look at the bundle's `txpydata.csv` and map **every non-zero column** before writing the situation. The canonical mapping is in `policyengine_taxsim/config/variable_mappings.yaml` if a column isn't in the table above.

```python
from policyengine_us import Simulation

# Example — map EVERY non-zero TAXSIM input from txpydata.csv
situation = {
    "people": {
        "head": {"age": {"2025": 65},
                 "employment_income": {"2025": 1571.43},          # pwages
                 "taxable_pension_income": {"2025": 46265.95},    # pensions
                 "taxable_interest_income": {"2025": 36.44},      # intrec
                 "social_security": {"2025": 30000},              # gssi
                 "real_estate_taxes": {"2025": 30000},            # proptax
                 "deductible_mortgage_interest": {"2025": 20000}, # mortgage
                 },
        "k1": {"age": {"2025": 11}},
        "k2": {"age": {"2025": 2}},
    },
    "tax_units": {"tu": {"members": ["head", "k1", "k2"],
                          "tax_unit_childcare_expenses": {"2025": 3000}}},  # childcare
    "households": {"hh": {"members": ["head", "k1", "k2"], "state_fips": {"2025": 8}}},
    "marital_units": {"m": {"members": ["head"]}, "m2": {"members": ["k1"]}, "m3": {"members": ["k2"]}},
    "families": {"f": {"members": ["head", "k1", "k2"]}},
    "spm_units": {"s": {"members": ["head", "k1", "k2"]}},
}

sim = Simulation(situation=situation)
print("federal AGI:", sim.calculate("adjusted_gross_income", 2025))
print("State AGI:", sim.calculate("co_agi", 2025))
```

**Verify input parity before drawing conclusions**: after building the situation, run the emulator (`policyengine_taxsim/cli.py policyengine ...`) on the same row and check that key intermediates (`adjusted_gross_income`, `cdcc`, `ctc`, federal `income_tax`) match. If they don't, you're missing a TAXSIM input mapping — fix that before going further.

### Step 7: Research Legal Documentation

When PE and TaxAct disagree on a specific credit, deduction, or line item, **fetch the primary sources** — don't rely on web-search summaries. Search summaries are routinely wrong or stale (e.g., a search may claim "State X does not offer credit Y" when the statute clearly establishes it). Use search only to *find* the right primary-source URL, then fetch the document.

For state credits, verify all three of:

1. **Statute text** — `WebFetch` the actual statute (e.g., `https://code.<state>legislature.gov/<section>/`). Quote the relevant language verbatim. Confirms whether the credit exists in law.
2. **Current-year form PDF** — fetch the current-year state return PDF and check whether the credit actually appears as a line. A statutory credit that hasn't been operationalized on the form may not be claimable in practice for that year.
3. **Current-year instructions booklet** — fetch the instructions PDF and look for eligibility criteria, income caps, age requirements, or filing prerequisites that PE may not model.

Cross-reference: statute → form line → instructions eligibility. If any of the three says something different, **hedge in your write-up** — don't claim PE is correct just because the statute is on the books, and don't claim PE is wrong just because TaxAct's PDF didn't apply a credit (TaxAct can miss things, too; the bundled PDFs sometimes omit schedules).

For federal items, use IRS publications and Form 1040 instructions directly.

### Step 8: Check policyengine-us Implementation
```bash
# Find state variables
ls /Users/pavelmakarchuk/policyengine-us/policyengine_us/variables/gov/states/{state}/tax/

# Search for specific variable
grep -r "variable_name" /Users/pavelmakarchuk/policyengine-us/policyengine_us/
```

### Step 9: Draft and confirm

If PE needs a fix, **draft** an issue for policyengine-us with:
1. Summary of the problem
2. Link back to the originating taxsim issue
3. Root cause analysis with code references
4. Suggested fix
5. Integration test with correct expected values (from TaxAct PDF, not PE's buggy output)

**Show the draft to the user and wait for approval before posting.** After posting, cross-link the PE-US issue back from the taxsim issue with a short comment.

#### Comment style (taxsim issues)

Replies on taxsim issues should be **soft, question-shaped, and link-heavy**:

- **Phrase findings as questions, not pronouncements.** "Possible that the hand calc didn't apply X?" beats "Your calculation is wrong because you forgot X." If a number doesn't reproduce, ask whether the case was intended differently rather than asserting the reporter is wrong.
- **Always link the primary sources you used.** Statute citations → the actual `revisor`/`legis` URL. IRS limits → the relevant Rev. Proc. PDF with page anchor. PE-US logic → a GitHub permalink to the specific variable file. Existing PE-US tracking → the issue/PR number.
- **Anchor PE behavior to code, not assertion.** Don't write "PE applies X correctly" — write "PE checks X in [`<file>`]<github-link> via `<variable>`."
- Keep it short and structured. One short paragraph per concern with a bold lead-in (e.g., `**M1CWFC**:`).

---

## TAXSIM State Code Reference

**CRITICAL**: TAXSIM uses alphabetical state numbering (1-51), NOT FIPS codes!

| State | TAXSIM Code | FIPS Code |
|-------|-------------|-----------|
| AL | 1 | 1 |
| AK | 2 | 2 |
| AZ | 3 | 4 |
| AR | 4 | 5 |
| CA | 5 | 6 |
| CO | 6 | 8 |
| CT | 7 | 9 |
| DC | 8 | 11 |
| DE | 9 | 10 |
| FL | 10 | 12 |
| ... | ... | ... |
| NJ | **31** | 34 |
| NM | 32 | 35 |
| NY | 33 | 36 |
| NC | **34** | 37 |
| ... | ... | ... |

Common confusion: NJ FIPS=34, but TAXSIM code=31. NC TAXSIM=34.

To verify state code mapping:
```python
from policyengine_taxsim.core.utils import get_state_code, SOI_TO_FIPS_MAP
print(get_state_code(31))  # Should print "NJ"
print(get_state_code(34))  # Should print "NC"
```

---

## TAXSIM Variable Reference (idtl=2)

| Var | Description | PE Variable |
|-----|-------------|-------------|
| fiitax | Federal income tax | income_tax |
| siitax | State income tax | `<state>_income_tax` |
| v10 | Federal AGI | adjusted_gross_income |
| v13 | Standard Deduction | standard_deduction |
| v18 | Taxable Income | taxable_income |
| v22 | Child Tax Credit | ctc_value |
| v25 | EITC | eitc |
| v32 | State AGI | `<state>_agi` |
| v34 | State Std Deduction | `<state>_standard_deduction` |
| v36 | State Taxable Income | `<state>_taxable_income` |

---

## Common Root Causes

### 1. Reporter's claim based on stale PE version
- Reporter ran an older PE-US; the issue is already fixed.
- Caught by Step 0b (version comparison + changelog grep).

### 2. Already-tracked in policyengine-us
- An open PE-US issue or PR is in flight covering the same root cause.
- Caught by Step 0c (`gh search issues`).

### 3. YAML / Reporter's Expected Value Incorrect
- Numbers cited in the issue body don't match the actual TaxAct PDF form
- Always verify by extracting and reading the PDFs
- Example: reporter said "PE allows $502" but PDF showed PTC = $0 and PE returned $0 (the $502 was a max-table value, not what PE returned)

### 4. Data Entry Errors in Issue
- Wrong state code (FIPS vs TAXSIM alphabetical)
- Missing or incorrect age (breaks age-based provisions)
- Wrong filing status (most commonly: assuming `mstat=1` is single when it's HoH with dependents)

### 5. TAXSIM Bug
- TAXSIM source code has known bugs (SALT add-back, DTC phaseout, EITC age limits)
- Compare current PE vs reporter's PE vs TaxAct to triangulate

### 6. Missing State Provisions in PE
- State credit/deduction not implemented
- Year-specific parameter not updated

### 7. Missing Optimization in PE
- PE uses fixed 50/50 splits for exemptions/deductions
- Some states (e.g., MS) allow optimal allocation between spouses
- TaxAct optimizes these allocations automatically

### 8. Input Mapping Issues (policyengine-taxsim)
- Income not being split correctly between spouses
- Variable not mapped from TAXSIM input to PE situation

### 9. Output Mapping Issues (policyengine-taxsim)
- State variable name not being substituted correctly
- Variable exists but not in output mapping

### 10. Calculation Logic Issues (policyengine-us)
- Eligibility criteria wrong
- Formula doesn't match tax form worksheet
- Parameter values outdated

### 11. Negative Income Edge Cases
- Credits/taxes not handling negative AGI or capital losses correctly
- Phantom credits when income is negative

---

## Debugging Checklist

When an issue doesn't reproduce as expected:

- [ ] **Did Step 0 (triage) short-circuit?** Already fixed in newer PE, already tracked, or informational only?
- [ ] **State code correct?** (TAXSIM alphabetical, not FIPS)
- [ ] **v32 (State AGI) non-zero?** (If 0, state setup is wrong)
- [ ] **Filing status inference?** (`mstat=1 + depx≥1` → HoH, not single)
- [ ] **Ages set correctly?** (Many provisions are age-gated)
- [ ] **Income assigned to right person?** (Joint filers: check both)
- [ ] **Test with Simulation directly?** When you do, **map every non-zero TAXSIM input** (especially `tax_unit_childcare_expenses` from `childcare`, `real_estate_taxes` from `proptax`, `deductible_mortgage_interest` from `mortgage`) — missing inputs will make Simulation diverge from the emulator and you'll mis-attribute the gap to a framework difference. See Step 6.
- [ ] **Check existing tests in policyengine-us?** (May show expected behavior)
- [ ] **PDFs extracted and analyzed?** (Reporter's expected values may be wrong!)
- [ ] **Compared current PE vs TaxAct?** Every PE value queried directly (no inference from gaps between variables).
- [ ] **For credit/deduction disagreements: did you fetch the statute + current-year form + instructions booklet?** (Search summaries are not authoritative.)

---

## Key Files

### policyengine-taxsim
- `policyengine_taxsim/config/variable_mappings.yaml` - TAXSIM to PE variable mappings
- `policyengine_taxsim/core/input_mapper.py` - Converts TAXSIM input to PE situations
- `policyengine_taxsim/core/output_mapper.py` - Extracts PE results to TAXSIM format
- `policyengine_taxsim/core/utils.py` - State code mappings (SOI_TO_FIPS_MAP)

### policyengine-us
- `policyengine_us/variables/gov/states/{state}/tax/income/` - State tax variables
- `policyengine_us/parameters/gov/states/{state}/tax/income/` - State tax parameters
- `policyengine_us/tests/policy/baseline/gov/states/{state}/` - Existing tests
- `CHANGELOG.md` - Use to compare reporter's PE version to current and find relevant recent fixes

---

## State Tax Authority URLs

- AZ: azdor.gov
- AR: dfa.arkansas.gov
- CA: ftb.ca.gov
- CO: tax.colorado.gov
- CT: portal.ct.gov/DRS
- DC: otr.cfo.dc.gov
- GA: dor.georgia.gov
- HI: tax.hawaii.gov
- IA: tax.iowa.gov
- KY: revenue.ky.gov
- MN: revenue.state.mn.us
- MO: dor.mo.gov
- MS: dor.ms.gov
- MT: mtrevenue.gov
- NE: revenue.nebraska.gov
- NJ: nj.gov/treasury/taxation
- NM: tax.newmexico.gov
- OK: oklahoma.gov/tax
- VA: tax.virginia.gov
- VT: tax.vermont.gov
- WV: tax.wv.gov

---

## Your Task

$ARGUMENTS

If no specific issue is provided, list the open issues and ask which one to diagnose.
