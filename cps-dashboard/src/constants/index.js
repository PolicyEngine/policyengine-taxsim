// State code mappings
export const STATE_TO_FIPS = {
  'AL': 1, 'AK': 2, 'AZ': 3, 'AR': 4, 'CA': 5, 'CO': 6, 'CT': 7, 'DE': 8, 'DC': 9,
  'FL': 10, 'GA': 11, 'HI': 12, 'ID': 13, 'IL': 14, 'IN': 15, 'IA': 16, 'KS': 17,
  'KY': 18, 'LA': 19, 'ME': 20, 'MD': 21, 'MA': 22, 'MI': 23, 'MN': 24, 'MS': 25,
  'MO': 26, 'MT': 27, 'NE': 28, 'NV': 29, 'NH': 30, 'NJ': 31, 'NM': 32, 'NY': 33,
  'NC': 34, 'ND': 35, 'OH': 36, 'OK': 37, 'OR': 38, 'PA': 39, 'RI': 40, 'SC': 41,
  'SD': 42, 'TN': 43, 'TX': 44, 'UT': 45, 'VT': 46, 'VA': 47, 'WA': 48, 'WV': 49,
  'WI': 50, 'WY': 51
};

export const FIPS_TO_STATE = Object.entries(STATE_TO_FIPS).reduce((acc, [state, fips]) => {
  acc[fips] = state;
  return acc;
}, {});

// Available years for the dashboard
export const AVAILABLE_YEARS = [2021, 2022, 2023, 2024];

// GitHub API configuration
export const GITHUB_CONFIG = {
  API_BASE: 'https://api.github.com',
  REPO_OWNER: 'PolicyEngine',
  REPO_NAME: 'policyengine-taxsim',
  CACHE_DURATION: 5 * 60 * 1000 // 5 minutes
};

// Mismatch tolerance
export const MISMATCH_TOLERANCE = 15; // $15 tolerance for mismatches

// Input variables for household comparison
export const INPUT_VARIABLES = [
  { code: 'mstat', name: 'Marital Status' },
  { code: 'page', name: 'Primary Taxpayer Age' },
  { code: 'sage', name: 'Spouse Age' },
  { code: 'depx', name: 'Number of Dependents' },
  { code: 'age1', name: 'Dependent 1 Age' },
  { code: 'age2', name: 'Dependent 2 Age' },
  { code: 'age3', name: 'Dependent 3 Age' },
  { code: 'age4', name: 'Dependent 4 Age' },
  { code: 'age5', name: 'Dependent 5 Age' },
  { code: 'age6', name: 'Dependent 6 Age' },
  { code: 'age7', name: 'Dependent 7 Age' },
  { code: 'age8', name: 'Dependent 8 Age' },
  { code: 'age9', name: 'Dependent 9 Age' },
  { code: 'age10', name: 'Dependent 10 Age' },
  { code: 'age11', name: 'Dependent 11 Age' },
  { code: 'pwages', name: 'Primary Wages' },
  { code: 'swages', name: 'Spouse Wages' },
  { code: 'psemp', name: 'Primary Self-Employment' },
  { code: 'ssemp', name: 'Spouse Self-Employment' },
  { code: 'dividends', name: 'Dividend Income' },
  { code: 'intrec', name: 'Interest Income' },
  { code: 'stcg', name: 'Short-Term Capital Gains' },
  { code: 'ltcg', name: 'Long-Term Capital Gains' },
  { code: 'otherprop', name: 'Other Property Income' },
  { code: 'nonprop', name: 'Other Non-Property Income' },
  { code: 'pensions', name: 'Taxable Pensions' },
  { code: 'gssi', name: 'Gross Social Security' },
  { code: 'pui', name: 'Primary Unemployment Income' },
  { code: 'sui', name: 'Spouse Unemployment Income' },
  { code: 'transfers', name: 'Non-Taxable Transfers' },
  { code: 'rentpaid', name: 'Rent Paid' },
  { code: 'proptax', name: 'Property Taxes' },
  { code: 'otheritem', name: 'Other Itemized Deductions' },
  { code: 'childcare', name: 'Child Care Expenses' },
  { code: 'mortgage', name: 'Mortgage Interest' }
];

// Output variables for household comparison
// Based on TAXSIM documentation: https://taxsim.nber.org/taxsimtest/
// Linked to PolicyEngine US variables: https://github.com/PolicyEngine/policyengine-us/tree/master/policyengine_us/variables
export const OUTPUT_VARIABLES = [
  // Basic Output Variables
  { code: 'taxsimid', name: 'Case ID', policyengine: 'taxsimid' },
  { code: 'year', name: 'Year', policyengine: 'year' },
  { code: 'state', name: 'State code', policyengine: 'state_code' },
  
  // Primary Tax Outputs
  { code: 'fiitax', name: 'Federal income tax liability including capital gains rates, surtaxes, Maximum Tax, NIIT, AMT, Additional Medicare Tax and refundable and non-refundable credits including CTC, ACTC and EIC etc, but not including self-employment or FICA taxes', policyengine: 'income_tax' },
  { code: 'siitax', name: 'State income tax liability, also after all credits', policyengine: 'state_income_tax' },

  // Federal AGI and Income Components (v10-v12)
  { code: 'v10', name: 'Federal AGI', policyengine: 'adjusted_gross_income' },
  { code: 'v11', name: 'UI in AGI', policyengine: 'unemployment_compensation' },
  { code: 'v12', name: 'Social Security in AGI', policyengine: 'taxable_social_security' },

  // Federal Deductions and Exemptions (v13-v17)
  { code: 'v13', name: 'Zero Bracket Amount (zero for itemizers) / Standard Deduction', policyengine: 'standard_deduction' },
  { code: 'v14', name: 'Personal Exemptions', policyengine: 'exemptions' },
  { code: 'v15', name: 'Exemption Phaseout', policyengine: null },
  { code: 'v16', name: 'Deduction Phaseout', policyengine: null },
  { code: 'v17', name: 'Itemized Deductions in taxable income', policyengine: 'itemized_deductions' },
  { code: 'qbid', name: 'Qualified business income deduction', policyengine: 'qualified_business_income_deduction' },

  // Federal Taxable Income and Tax Calculations (v18-v21)
  { code: 'v18', name: 'Federal Taxable Income', policyengine: 'taxable_income' },
  { code: 'v19', name: 'Tax on Taxable Income (no special capital gains rates)', policyengine: 'income_tax_before_credits' },
  { code: 'v20', name: 'Exemption Surtax', policyengine: null },
  { code: 'v21', name: 'General Tax Credit', policyengine: null },

  // Federal Tax Credits (v22-v25)
  { code: 'v22', name: 'Child Tax Credit (as adjusted includes additional ctc)', policyengine: 'ctc' },
  { code: 'v23', name: 'Reserved', policyengine: null },
  { code: 'v24', name: 'Child Care Credit (including additional credit)', policyengine: 'cdcc' },
  { code: 'v25', name: 'Earned Income Credit (total federal)', policyengine: 'eitc' },
  { code: 'actc', name: 'Additional child tax credit', policyengine: 'additional_ctc' },
  { code: 'cares', name: 'Cares rebate', policyengine: 'recovery_rebate_credit' },

  // Federal AMT and Special Taxes (v26-v28)
  { code: 'v26', name: 'Income for the Alternative Minimum Tax', policyengine: 'amt_income' },
  { code: 'v27', name: 'AMT Liability after credit for regular tax and other allowed credits', policyengine: 'amt' },
  { code: 'v28', name: 'Federal Income Tax Before Credits (includes special treatment of Capital gains, exemption surtax (1988-1996) and 15% rate phaseout (1988-1990) but not AMT)', policyengine: 'income_tax_before_credits' },

  // State Income Calculations (v30-v36)
  { code: 'v30', name: 'State Household Income (imputation for property tax credit)', policyengine: 'household_income' },
  { code: 'v31', name: 'State Rent Expense (imputation for property tax credit)', policyengine: 'rent' },
  { code: 'v32', name: 'State AGI', policyengine: 'state_agi' },
  { code: 'v33', name: 'State Exemption amount', policyengine: 'state_exemptions' },
  { code: 'v34', name: 'State Standard Deduction', policyengine: 'state_standard_deduction' },
  { code: 'v35', name: 'State Itemized Deductions', policyengine: 'state_itemized_deductions' },
  { code: 'v36', name: 'State Taxable Income', policyengine: 'state_taxable_income' },

  // State Tax Credits (v37-v41)
  { code: 'v37', name: 'State Property Tax Credit', policyengine: 'state_property_tax_credit' },
  { code: 'v38', name: 'State Child Care Credit', policyengine: 'state_cdcc' },
  { code: 'v39', name: 'State EIC', policyengine: 'state_eitc' },
  { code: 'v40', name: 'State Total Credits', policyengine: 'state_tax_credits' },
  { code: 'v41', name: 'State Bracket Rate', policyengine: 'state_income_tax_rate' },

  // Additional State Results (moved to be with other state variables)
  { code: 'staxbc', name: 'State tax before credits', policyengine: 'state_income_tax_before_credits' },
  { code: 'srebate', name: 'State income tax rebates (shown only in year paid even if eligibility depends on prior year)', policyengine: 'state_rebates' },
  { code: 'senergy', name: 'State energy/fuel tax credits', policyengine: 'state_energy_credits' },
  { code: 'sctc', name: 'State child tax credit', policyengine: 'state_ctc' },
  { code: 'sptcr', name: 'State property tax credit', policyengine: 'state_property_tax_credit' },
  { code: 'samt', name: 'State alternative minimum tax', policyengine: 'state_amt' },
  { code: 'srate', name: 'State marginal rate', policyengine: null },

  // Additional Federal Results (v42-v46)
  { code: 'v42', name: 'Earned Self-Employment Income for FICA', policyengine: 'self_employment_income' },
  { code: 'v43', name: 'Medicare Tax on Unearned Income', policyengine: 'net_investment_income_tax' },
  { code: 'v44', name: 'Medicare Tax on Earned Income', policyengine: 'medicare_tax' },
  { code: 'v45', name: 'CARES act Recovery Rebates', policyengine: 'recovery_rebate_credit' },
  { code: 'v46', name: 'Cares Rebate (duplicate)', policyengine: 'recovery_rebate_credit' },

  // Additional Federal Results
  { code: 'niit', name: 'Medicare Net Investment Income Tax', policyengine: 'net_investment_income_tax' },
  { code: 'addmed', name: 'Medicare additional earnings Tax', policyengine: 'additional_medicare_tax' },
  { code: 'cdate', name: 'Date this version of Taxsim was compiled', policyengine: null },

  // Additional Taxes (moved to end for proper section ordering)
  { code: 'fica', name: 'FICA (OADSI and HI, sum of employee AND employer including Additional Medicare Tax)', policyengine: null },
  { code: 'tfica', name: 'Taxpayer liability for FICA', policyengine: 'taxsim_tfica' },
  { code: 'frate', name: 'Federal marginal rate', policyengine: null },
  { code: 'ficar', name: 'FICA rate', policyengine: null },
];

// Input fields from TAXSIM
export const INPUT_FIELDS = [
  'taxsimid', 'state', 'mstat', 'page', 'sage', 'depx', 'pwages', 'swages', 
  'psemp', 'ssemp', 'dividends', 'intrec', 'stcg', 'ltcg', 'otherprop', 'nonprop',
  'pensions', 'gssi', 'pui', 'sui', 'transfers', 'rentpaid', 'proptax', 'otheritem',
  'childcare', 'mortgage', 'scorp', 'age1', 'age2', 'age3', 'age4', 'age5', 'age6',
  'age7', 'age8', 'age9', 'age10', 'age11', 'year'
];

// Label colors for GitHub issues
export const LABEL_COLORS = {
  'bug': '#d73a4a',
  'enhancement': '#0075ca',
  'documentation': '#0075ca',
  'good first issue': '#7057ff',
  'help wanted': '#008672',
  'question': '#d876e3',
  'wontfix': '#ffffff',
  'duplicate': '#cfd3d7',
  'invalid': '#e4e669'
};

// State-specific tax calculation notes
export const STATE_TAX_NOTES = {
  VA: {
    years: [2021],
    title: 'Virginia 2021 Tax Calculation Note',
    content: 'For Virginia in 2021, TAXSIM includes a state tax rebate that is not reflected in PolicyEngine calculations. This may result in apparent mismatches where TAXSIM shows lower state tax liability than PolicyEngine due to the rebate being automatically applied in TAXSIM but not in PolicyEngine.'
  },
  NM: {
    years: [2021],
    title: 'New Mexico 2021 Tax Calculation Note',
    content: 'For New Mexico in 2021, PolicyEngine includes three income rebates that are omitted in TAXSIM calculations. This may result in apparent mismatches where PolicyEngine shows lower state tax liability than TAXSIM due to these rebates being included in PolicyEngine but not in TAXSIM.'
  },
  LA: {
    years: 'all',
    title: 'Louisiana Tax Calculation Note',
    content: 'For Louisiana, TAXSIM and PolicyEngine handle income exemption amounts differently. This may result in apparent mismatches between the two calculation systems due to different interpretations or implementations of Louisiana\'s income exemption rules.'
  },
  OK: {
    years: [2024],
    title: 'Oklahoma 2024 Tax Calculation Note',
    content: 'For Oklahoma in 2024, TAXSIM has not updated the state income tax rates. This may result in apparent mismatches where TAXSIM shows different state tax liability than PolicyEngine due to TAXSIM using outdated tax rates while PolicyEngine uses the current 2024 rates.'
  }
};