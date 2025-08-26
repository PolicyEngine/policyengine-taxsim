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
export const OUTPUT_VARIABLES = [
  { code: 'fiitax', name: 'Federal Income Tax' },
  { code: 'siitax', name: 'State Income Tax' },
  { code: 'tfica', name: 'Total FICA Tax' },
  { code: 'v10', name: 'Federal AGI' },
  { code: 'v11', name: 'UI in AGI' },
  { code: 'v12', name: 'Social Security in AGI' },
  { code: 'v14', name: 'Personal Exemptions' },
  { code: 'v17', name: 'Itemized Deductions in taxable income' },
  { code: 'v18', name: 'Federal Taxable Income' },
  { code: 'v19', name: 'Tax on Taxable Income (excludes capital gains tax)' },
  { code: 'v22', name: 'Child Tax Credit' },
  { code: 'v24', name: 'Child Care Credit' },
  { code: 'v25', name: 'Earned Income Credit' },
  { code: 'v26', name: 'Income for the Alternative Minimum Tax' },
  { code: 'v27', name: 'Alternative Minimum Tax' },
  { code: 'v28', name: 'Federal Income Tax before Credits' },
  { code: 'v32', name: 'State AGI' },
  { code: 'v36', name: 'State Taxable Income' },
  { code: 'v38', name: 'State Child Care Credit' },
  { code: 'v39', name: 'State Earned Income Credit' },
  { code: 'v40', name: 'State Total Credits' },
  { code: 'v44', name: 'Medicare Tax on Earnings' },
  { code: 'qbid', name: 'Qualified Business Income Deduction' },
  { code: 'niit', name: 'Net Investment Income Tax' },
  { code: 'sctc', name: 'State Child Tax Credit' },
  { code: 'v46', name: 'Cares Rebate' },
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
  CO: {
    years: 'all',
    title: 'Colorado Tax Calculation Note',
    content: 'For Colorado, TAXSIM applies a rebate that is not included in PolicyEngine calculations. This may result in apparent mismatches where TAXSIM shows lower state tax liability than PolicyEngine due to the rebate being automatically applied in TAXSIM but not in PolicyEngine.'
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