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
3. **Test with PE directly** - Run the test case and check output
4. **Check v32 (State AGI)** - If 0 for state tax issues, the state setup is wrong
5. **EXTRACT AND READ THE TAXACT PDF** - This is the ground truth (see below)
6. Trace computation tree to find first diverging variable
7. Research legal documentation (state form instructions, tax code)
8. Check policyengine-us implementation against legal requirements
9. Document finding in `issue_analysis/issues/{number}_{state}_{description}.md`
10. Update tracker in `issue_analysis/README.md`

### CRITICAL: Always Extract TaxAct PDF Forms

**The YAML expected values may be WRONG.** Always download and extract the actual TaxAct PDF:

```bash
# Download PDF from TAXSIM
curl -s -o /tmp/form.pdf "https://taxsim.nber.org/out2psl/{issue_number}/{filename}.pdf"

# Extract text with PyMuPDF
python3 -c "
import fitz
doc = fitz.open('/tmp/form.pdf')
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
