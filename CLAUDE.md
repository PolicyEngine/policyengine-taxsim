# Claude Code Instructions for policyengine-taxsim

## Project Overview

This is a TAXSIM-35 emulator using PolicyEngine's US tax calculator. It processes TAXSIM input format and produces compatible output, allowing comparison between PolicyEngine and NBER's TAXSIM.

## Related Repositories

- **policyengine-taxsim** (this repo): `/Users/pavelmakarchuk/policyengine-taxsim`
  - GitHub: https://github.com/PolicyEngine/policyengine-taxsim
  - Issues are filed here

- **policyengine-us**: `/Users/pavelmakarchuk/policyengine-us`
  - GitHub: https://github.com/PolicyEngine/policyengine-us
  - Contains the actual tax rules - fixes go here
  - Variables: `policyengine_us/variables/gov/states/{state}/tax/`
  - Parameters: `policyengine_us/parameters/gov/states/{state}/tax/`

## Issue Diagnosis Workflow

Issues at https://github.com/PolicyEngine/policyengine-taxsim/issues contain test cases where PolicyEngine differs from TaxAct (ground truth). Use `/diagnose-issue {number}` to start diagnosis.

### Workflow Steps:
1. **Read issue description first** - The filer often identifies the root cause or provides key hints
2. **Verify input parameters** - Check state code, ages, filing status are correct
3. **Fetch ALL TAXSIM data in one request** - Use the batch download pattern below
4. **EXTRACT AND READ THE TAXACT PDF** - This is the ground truth (see below)
5. **Test with PE directly** - Run the test case and check output
6. **Check v32 (State AGI)** - If 0 for state tax issues, the state setup is wrong
7. Trace computation tree to find first diverging variable
8. Research legal documentation (state form instructions, tax code)
9. Check policyengine-us implementation against legal requirements
10. Document finding in `issue_analysis/issues/{number}_{state}_{description}.md`
11. Update tracker in `issue_analysis/README.md`
12. **If PE needs fix**: File issue in policyengine-us with integration test (see below)

### CRITICAL: Fetch TAXSIM Data ONCE

**Do NOT make multiple requests to taxsim.nber.org** - the server is unreliable. Fetch everything in ONE batch:

```bash
# Create local directory and batch download ALL files
ISSUE=664
mkdir -p /tmp/taxsim_$ISSUE
cd /tmp/taxsim_$ISSUE

# Single directory listing
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/" -o index.html

# Batch download all files (run in parallel)
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/$ISSUE.yaml" -o $ISSUE.yaml &
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/$ISSUE.txt" -o $ISSUE.txt &
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/output.txt" -o output.txt &
curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/txpydata.csv" -o txpydata.csv &
wait

# Download any PDFs listed in index.html
grep -oP 'href="\K[^"]+\.pdf' index.html | while read pdf; do
  curl -sL "http://taxsim.nber.org/out2psl/$ISSUE/$pdf" -o "$pdf" &
done
wait
```

Then work ENTIRELY from local files - no more network calls to TAXSIM.

### CRITICAL: Always Extract TaxAct PDF Forms

**The YAML expected values may be WRONG.** Always download and extract the actual TaxAct PDF:

```bash
# Extract text with PyMuPDF (from local file)
python3 -c "
import fitz
doc = fitz.open('/tmp/taxsim_$ISSUE/form.pdf')
for page in doc:
    print(page.get_text())
"
```

Example: Issue #657 YAML showed $147.97 MS tax, but the actual Form 80-105 showed **$0** (TaxAct optimally allocated exemptions to get both incomes under $10K).

### CRITICAL: TAXSIM State Codes

TAXSIM uses **alphabetical** state numbering (1-51), NOT FIPS codes!

Common confusion:
- NJ = TAXSIM **31** (FIPS 34)
- NC = TAXSIM **34** (FIPS 37)

Verify with: `from policyengine_taxsim.core.utils import get_state_code; print(get_state_code(31))`

### Quick Test Command:
```bash
echo "taxsimid,year,state,mstat,page,sage,depx,pwages,intrec,idtl
1,2024,31,2,70,70,0,0,129000,2" > /tmp/test.csv
python policyengine_taxsim/cli.py policyengine /tmp/test.csv -o /tmp/out.csv
cat /tmp/out.csv
```

### Key Files (policyengine-taxsim):
- `policyengine_taxsim/config/variable_mappings.yaml` - Variable mappings
- `policyengine_taxsim/core/input_mapper.py` - Input conversion
- `policyengine_taxsim/core/output_mapper.py` - Output extraction
- `policyengine_taxsim/core/utils.py` - State code mappings (SOI_TO_FIPS_MAP)
- `issue_analysis/` - Diagnosis tracking and findings

### Key Paths (policyengine-us):
- `policyengine_us/variables/gov/states/{state}/tax/income/` - State tax variables
- `policyengine_us/variables/gov/irs/income/credits/` - Federal credits
- `policyengine_us/parameters/gov/states/{state}/tax/income/` - State parameters
- `policyengine_us/tests/policy/baseline/gov/states/{state}/` - Existing tests

### TAXSIM Variable Quick Reference (idtl=2):
- fiitax/siitax: Final federal/state tax
- v10: Federal AGI
- v13: Standard deduction
- v18: Federal taxable income
- v32: State AGI (**if 0, check state code!**)
- v36: State taxable income

## Filing Issues in policyengine-us

When a bug is found in PolicyEngine, file an issue in policyengine-us with:

1. **Summary** of the problem
2. **Root cause** analysis with code references
3. **Files to fix** - list all affected files
4. **Suggested fix** - show the code change needed
5. **Integration test** - YAML test case with **correct expected values** (not PE's current buggy output)

Example integration test format:
```yaml
- name: Descriptive test name
  absolute_error_margin: 0.01
  period: 2024
  input:
    people:
      person1:
        is_tax_unit_head: true
        age: 40
        # ... income variables
    tax_units:
      tax_unit:
        members: [person1]
    spm_units:
      spm_unit:
        members: [person1]
    households:
      household:
        members: [person1]
        state_fips: XX  # or state_code: XX
  output:
    variable_name: expected_value  # Correct value from TaxAct PDF
```

Use `gh issue create --repo PolicyEngine/policyengine-us` to file issues.

After creating the issue, add a follow-up comment to trigger the automated PR bot:
```bash
gh issue comment {issue_number} --repo PolicyEngine/policyengine-us --body "@PolicyEngine review the issue and implement option 3."
```

## Common Root Causes

1. **YAML expected value wrong** - Always verify against PDF (e.g., #657: YAML=$147.97, PDF=$0)
2. **Data entry errors** - Wrong state code (FIPS vs TAXSIM), missing ages
3. **Missing optimization** - PE uses 50/50 splits; some states allow optimal allocation
4. **Missing state provisions** - PE doesn't implement a state credit/deduction
5. **Year-specific rules** - Tax law changed, PE not updated
6. **Filing status edge cases** - HoH qualification, elderly provisions
7. **Age-based provisions** - Retirement income exclusions, elderly credits
8. **Parameter values outdated** - Thresholds/amounts not updated for current year
9. **Input/output mapping** - Variable not correctly mapped between TAXSIM and PE
10. **Negative income edge cases** - Credits/taxes not handling negative AGI or capital losses correctly
