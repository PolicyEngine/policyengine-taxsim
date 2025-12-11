# TAXSIM Issue Diagnosis Workflow

You are helping diagnose discrepancies between PolicyEngine and TAXSIM tax calculations.

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
3. **YAML test file** - PolicyEngine situation and expected outputs (attached)
4. **TaxAct PDF** - The ground truth tax forms (attached)
5. **TAXSIM URL** - Reference at `taxsim.nber.org/out2psl/{issue_number}`

**IMPORTANT**: The issue description often contains the filer's analysis of what's wrong (e.g., "PE is not applying the retirement income exclusion", "extra credits TA doesn't find"). Start by reading the description carefully before diving into code.

## Diagnostic Steps

### Step 1: Read the Issue
- Fetch the issue from GitHub
- Read the description carefully for diagnostic hints
- Note any specific numbers mentioned (PE vs TaxAct values)

### Step 2: Verify the Input Parameters
**CRITICAL**: Before deep-diving into code, verify the TAXSIM input parameters are correct!

Common data entry errors to check:
- **State code**: TAXSIM uses alphabetical numbering (1-51), NOT FIPS codes!
- **Filing status (mstat)**: 1=single, 2=joint, 6=dependent
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

### Step 4: Compare Output Variables
Check key output variables (when idtl=2):
- `v32` = State AGI (should be non-zero for state tax issues)
- `v36` = State Taxable Income
- `siitax` = State Income Tax
- `fiitax` = Federal Income Tax

**If v32=0 for a state tax issue**: The state isn't being set correctly. Check the state code!

### Step 5: Deep Dive if Needed
If the basic test shows incorrect values:

```python
# Test with Simulation directly
from policyengine_us import Simulation

situation = {
    "people": {
        "person1": {"age": {"2024": 70}, "taxable_interest_income": {"2024": 64500}},
        "person2": {"age": {"2024": 70}, "taxable_interest_income": {"2024": 64500}},
    },
    "tax_units": {"tax_unit": {"members": ["person1", "person2"]}},
    "households": {"household": {"members": ["person1", "person2"], "state_fips": {"2024": 34}}},
    # ... other units
}

sim = Simulation(situation=situation)
print("State AGI:", sim.calculate("{state}_agi", 2024))
print("Exclusion:", sim.calculate("{state}_retirement_exclusion", 2024))
```

### Step 6: Research Legal Documentation
If PE logic appears wrong, verify against official sources:
- State tax form instructions (primary source)
- State tax code/statutes
- Tax Foundation / Tax Policy Center summaries

### Step 7: Check policyengine-us Implementation
```bash
# Find state variables
ls /Users/pavelmakarchuk/policyengine-us/policyengine_us/variables/gov/states/{state}/tax/

# Search for specific variable
grep -r "variable_name" /Users/pavelmakarchuk/policyengine-us/policyengine_us/
```

### Step 8: Document Finding
Record in `issue_analysis/issues/{number}_{description}.md` and update `issue_analysis/README.md`

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
| siitax | State income tax | state_income_tax |
| v10 | Federal AGI | adjusted_gross_income |
| v13 | Standard Deduction | standard_deduction |
| v18 | Taxable Income | taxable_income |
| v22 | Child Tax Credit | ctc_value |
| v25 | EITC | eitc |
| v32 | State AGI | {state}_agi |
| v34 | State Std Deduction | {state}_standard_deduction |
| v36 | State Taxable Income | {state}_taxable_income |

---

## Common Root Causes

### 1. Data Entry Errors in Issue
- Wrong state code (FIPS vs TAXSIM alphabetical)
- Missing or incorrect age (breaks age-based provisions)
- Wrong filing status

### 2. Missing State Provisions in PE
- State credit/deduction not implemented
- Year-specific parameter not updated

### 3. Input Mapping Issues (policyengine-taxsim)
- Income not being split correctly between spouses
- Variable not mapped from TAXSIM input to PE situation

### 4. Output Mapping Issues (policyengine-taxsim)
- State variable name not being substituted correctly
- Variable exists but not in output mapping

### 5. Calculation Logic Issues (policyengine-us)
- Eligibility criteria wrong
- Formula doesn't match tax form worksheet
- Parameter values outdated

---

## Debugging Checklist

When an issue doesn't reproduce as expected:

- [ ] **State code correct?** (TAXSIM alphabetical, not FIPS)
- [ ] **v32 (State AGI) non-zero?** (If 0, state setup is wrong)
- [ ] **Ages set correctly?** (Many provisions are age-gated)
- [ ] **Income assigned to right person?** (Joint filers: check both)
- [ ] **Test with Simulation directly?** (Bypasses taxsim mapping)
- [ ] **Check existing tests in policyengine-us?** (May show expected behavior)

---

## Key Files

### policyengine-taxsim
- `policyengine_taxsim/config/variable_mappings.yaml` - TAXSIM to PE variable mappings
- `policyengine_taxsim/core/input_mapper.py` - Converts TAXSIM input to PE situations
- `policyengine_taxsim/core/output_mapper.py` - Extracts PE results to TAXSIM format
- `policyengine_taxsim/core/utils.py` - State code mappings (SOI_TO_FIPS_MAP)
- `issue_analysis/` - Diagnosis tracking and findings

### policyengine-us
- `policyengine_us/variables/gov/states/{state}/tax/income/` - State tax variables
- `policyengine_us/parameters/gov/states/{state}/tax/income/` - State tax parameters
- `policyengine_us/tests/policy/baseline/gov/states/{state}/` - Existing tests

---

## State Tax Authority URLs

- AZ: azdor.gov
- AR: dfa.arkansas.gov
- CO: tax.colorado.gov
- CT: portal.ct.gov/DRS
- DC: otr.cfo.dc.gov
- MS: dor.ms.gov
- NJ: nj.gov/treasury/taxation
- VT: tax.vermont.gov

---

## Your Task

$ARGUMENTS

If no specific issue is provided, list the open issues and ask which one to diagnose.
