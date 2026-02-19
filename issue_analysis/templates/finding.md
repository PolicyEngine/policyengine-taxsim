# Issue #{ISSUE_NUMBER}: {TITLE}

## Overview
- **State**: {STATE}
- **Year**: {YEAR}
- **Filing Status**: {FILING_STATUS}
- **GitHub**: https://github.com/PolicyEngine/policyengine-taxsim/issues/{ISSUE_NUMBER}
- **TAXSIM Ref**: https://taxsim.nber.org/out2psl/{ISSUE_NUMBER}

## Test Case Parameters
```
taxsimid: {ISSUE_NUMBER}
year: {YEAR}
state: {STATE_CODE}
mstat: {MSTAT}
page: {PAGE}
sage: {SAGE}
depx: {DEPX}
pwages: {PWAGES}
...
```

## Discrepancy

| Variable | PolicyEngine | TaxAct | Difference |
|----------|-------------|--------|------------|
| siitax   |             |        |            |
| fiitax   |             |        |            |

## Computation Tree Analysis

### Where divergence occurs:
- [ ] Federal AGI (v10)
- [ ] Federal Deductions (v13/v17)
- [ ] Federal Taxable Income (v18)
- [ ] Federal Credits (v22/v24/v25)
- [ ] Federal Final Tax (fiitax)
- [ ] State AGI (v32)
- [ ] State Deductions (v34/v35)
- [ ] State Taxable Income (v36)
- [ ] State Credits (v37/v38/v39)
- [ ] State Final Tax (siitax)

### First diverging variable:
**{VARIABLE_NAME}**
- PE calculates: ${PE_VALUE}
- TaxAct shows: ${TAXACT_VALUE}
- Difference: ${DIFF}

## Legal Research

### Source Documents
- [ ] State form instructions: {URL}
- [ ] State tax code: {CITATION}
- [ ] IRS publication: {PUB_NUMBER}

### What the law says:
{LEGAL_DESCRIPTION}

### Eligibility criteria:
- Age requirement:
- Income threshold:
- Filing status:

## PolicyEngine Implementation

### policyengine-us location:
`/Users/pavelmakarchuk/policyengine-us/policyengine_us/variables/gov/states/{state}/tax/income/`

### Relevant files examined:
- [ ] `{file1.py}` - {description}
- [ ] `{file2.py}` - {description}

### Current implementation:
- Variable: `{PE_VARIABLE_NAME}`
- Location: `policyengine_us/variables/gov/states/{state}/...`
- What it does: {DESCRIPTION}

```python
# Key code snippet from policyengine-us
```

### Gap identified:
{GAP_DESCRIPTION}

### Parameters checked:
- Location: `policyengine_us/parameters/gov/states/{state}/tax/income/...`
- Current values: {PARAM_VALUES}
- Expected values: {EXPECTED_VALUES}

## Conclusion

- [ ] PolicyEngine is correct
- [ ] PolicyEngine needs fix (variable logic)
- [ ] PolicyEngine needs fix (parameter values)
- [ ] Ambiguous / needs more research
- [ ] TAXSIM/TaxAct is wrong

### Recommended action:
{RECOMMENDATION}

### Fix location:
- Repository: policyengine-us
- File(s) to modify: {FILES}
- Type of change: [ ] New variable [ ] Fix existing variable [ ] Update parameters

### policyengine-us issue:
{PE_US_ISSUE_URL}
