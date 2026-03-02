const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// Path to the original YAML file
const yamlPath = path.join(__dirname, '../../policyengine_taxsim/config/variable_mappings.yaml');
const outputPath = path.join(__dirname, '../public/config-data.json');

/**
 * Generate GitHub link for PolicyEngine variable
 */
function generatePolicyEngineGitHubLink(variableName) {
  const baseUrl = 'https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables';
  
  // Variables that should NOT have links (utility functions, system variables)
  const noLinkVariables = [
    'taxsimid', 
    'get_year', 
    'get_state_code', 
    'marital_status', // This is likely a system variable
    'dependents' // This might be a computed variable
  ];
  
  if (noLinkVariables.includes(variableName)) {
    return null;
  }
  
  // Map variables to their actual paths in PolicyEngine-US (verified working paths)
  const variablePathMap = {
    // Income variables
    'employment_income': 'input/employment_income.py',
    'self_employment_income': 'household/income/self_employment/self_employment_income.py',
    'qualified_dividend_income': 'household/income/person/dividends/qualified_dividend_income.py',
    'taxable_interest_income': 'household/income/person/interest/taxable_interest_income.py',
    'short_term_capital_gains': 'household/income/person/capital_gains/short_term_capital_gains.py',
    'long_term_capital_gains': 'household/income/person/capital_gains/long_term_capital_gains.py',
    'taxable_private_pension_income': 'household/income/person/retirement/taxable_private_pension_income.py',
    'social_security_retirement': 'gov/ssa/ss/social_security_retirement.py',
    'unemployment_compensation': 'gov/states/unemployment_compensation.py',
    'partnership_s_corp_income': 'household/income/person/self_employment/partnership_s_corp_income.py',
    'qualified_business_income': 'gov/irs/income/taxable_income/deductions/qualified_business_income_deduction/qualified_business_income.py',
    
    // Expense/Deduction variables
    'rent': 'household/expense/housing/rent.py',
    'real_estate_taxes': 'household/expense/tax/real_estate_taxes.py',
    'tax_unit_childcare_expenses': 'household/expense/childcare/tax_unit_childcare_expenses.py',
    'deductible_mortgage_interest': 'household/expense/person/deductible_mortgage_interest.py',
    
    // Demographics
    'age': 'household/demographic/age.py'
  };
  
  const path = variablePathMap[variableName];
  if (path) {
    return `${baseUrl}/${path}`;
  }
  
  // For variables we're not sure about, don't provide a link
  // This prevents broken links
  return null;
}

/**
 * Extract TAXSIM to PolicyEngine variable mappings from the configuration
 */
function extractTaxsimToPolicyEngineMappings(config) {
  const mappings = [];
  const taxsimInputDef = config.taxsim_input_definition || [];
  const taxsimToPe = config.taxsim_to_policyengine || {};
  const additionalIncomeUnits = taxsimToPe.household_situation?.additional_income_units || [];
  const additionalTaxUnits = taxsimToPe.household_situation?.additional_tax_units || [];

  // Process taxsim_input_definition for basic mappings
  taxsimInputDef.forEach(item => {
    if (typeof item === 'object') {
      Object.entries(item).forEach(([taxsimVar, definition]) => {
        const name = definition.name || taxsimVar;
        const description = name.replace(/^\d+\.\s*/, ''); // Remove numbering
        
        // Find corresponding PolicyEngine variable from additional_income_units
        let policyengineVar = 'Not mapped';
        let implemented = false;
        
        // Check additional_income_units
        additionalIncomeUnits.forEach(incomeUnit => {
          Object.entries(incomeUnit).forEach(([peVar, taxsimVars]) => {
            if (Array.isArray(taxsimVars) && taxsimVars.includes(taxsimVar)) {
              policyengineVar = peVar;
              implemented = true;
            }
          });
        });
        
        // Check additional_tax_units
        additionalTaxUnits.forEach(taxUnit => {
          Object.entries(taxUnit).forEach(([peVar, taxsimVars]) => {
            if (Array.isArray(taxsimVars) && taxsimVars.includes(taxsimVar)) {
              policyengineVar = peVar;
              implemented = true;
            }
          });
        });

        // Handle special cases and paired variables
        if (taxsimVar === 'taxsimid') {
          policyengineVar = 'taxsimid';
          implemented = true;
        } else if (taxsimVar === 'year') {
          policyengineVar = 'get_year';
          implemented = true;
        } else if (taxsimVar === 'state') {
          policyengineVar = 'get_state_code';
          implemented = true;
        } else if (taxsimVar === 'mstat') {
          policyengineVar = 'marital_status';
          implemented = true;
        } else if (taxsimVar === 'page' || taxsimVar === 'sage') {
          policyengineVar = 'age';
          implemented = true;
        } else if (taxsimVar === 'depx' || taxsimVar === 'dependent_exemption') {
          policyengineVar = 'dependents';
          implemented = true;
        } else if (taxsimVar === 'pwages' || taxsimVar === 'swages') {
          policyengineVar = 'employment_income';
          implemented = true;
        } else if (taxsimVar === 'psemp' || taxsimVar === 'ssemp') {
          policyengineVar = 'self_employment_income';
          implemented = true;
        } else if (taxsimVar === 'pui' || taxsimVar === 'sui') {
          policyengineVar = 'unemployment_compensation';
          implemented = true;
        }

        // Mark certain variables as not available in PolicyEngine
        const notAvailableVars = ['otherprop', 'nonprop', 'transfers', 'otheritem', 'pprofinc'];
        if (notAvailableVars.includes(taxsimVar) && policyengineVar === 'Not mapped') {
          policyengineVar = 'na_pe';
          implemented = false;
        }

        // Generate GitHub link for PolicyEngine variable
        let githubLink = null;
        if (implemented && policyengineVar !== 'na_pe' && policyengineVar !== 'Not mapped') {
          githubLink = generatePolicyEngineGitHubLink(policyengineVar);
        }

        mappings.push({
          taxsim: taxsimVar,
          policyengine: policyengineVar,
          description: description,
          implemented: implemented,
          githubLink: githubLink
        });
      });
    }
  });

  // Sort mappings by logical category order and insert spouse variables in the right places
  const sortedMappings = [];
  
  // Basic inputs first
  const basicOrder = ['taxsimid', 'year', 'state', 'mstat', 'page', 'dependent_exemption', 'depx'];
  basicOrder.forEach(varName => {
    const mapping = mappings.find(m => m.taxsim === varName);
    if (mapping) sortedMappings.push(mapping);
  });
  
  // Add sage (Age of secondary taxpayer) after page
  const sageIndex = sortedMappings.findIndex(m => m.taxsim === 'page');
  if (sageIndex >= 0) {
    const githubLink = generatePolicyEngineGitHubLink('age');
    sortedMappings.splice(sageIndex + 1, 0, {
      taxsim: 'sage',
      policyengine: 'age',
      description: 'Age of secondary taxpayer',
      implemented: true,
      githubLink: githubLink
    });
  }
  
  // Income inputs
  const incomeOrder = ['pwages', 'psemp', 'dividends', 'intrec', 'stcg', 'ltcg', 'pensions', 'gssi', 'pui'];
  incomeOrder.forEach(varName => {
    const mapping = mappings.find(m => m.taxsim === varName);
    if (mapping) sortedMappings.push(mapping);
  });
  
  // Add spouse income variables after their primary counterparts
  const pwagesIndex = sortedMappings.findIndex(m => m.taxsim === 'pwages');
  if (pwagesIndex >= 0) {
    const githubLink = generatePolicyEngineGitHubLink('employment_income');
    sortedMappings.splice(pwagesIndex + 1, 0, {
      taxsim: 'swages',
      policyengine: 'employment_income',
      description: 'Wage and salary income of secondary taxpayer',
      implemented: true,
      githubLink: githubLink
    });
  }
  
  const psempIndex = sortedMappings.findIndex(m => m.taxsim === 'psemp');
  if (psempIndex >= 0) {
    const githubLink = generatePolicyEngineGitHubLink('self_employment_income');
    sortedMappings.splice(psempIndex + 1, 0, {
      taxsim: 'ssemp',
      policyengine: 'self_employment_income',
      description: 'Self-employment income of secondary taxpayer',
      implemented: true,
      githubLink: githubLink
    });
  }
  
  const puiIndex = sortedMappings.findIndex(m => m.taxsim === 'pui');
  if (puiIndex >= 0) {
    const githubLink = generatePolicyEngineGitHubLink('unemployment_compensation');
    sortedMappings.splice(puiIndex + 1, 0, {
      taxsim: 'sui',
      policyengine: 'unemployment_compensation',
      description: 'Secondary taxpayer unemployment compensation',
      implemented: true,
      githubLink: githubLink
    });
  }
  
  // Business income
  const businessOrder = ['scorp', 'pbusinc', 'pprofinc'];
  businessOrder.forEach(varName => {
    const mapping = mappings.find(m => m.taxsim === varName);
    if (mapping) sortedMappings.push(mapping);
  });
  
  // Expense inputs
  const expenseOrder = ['rentpaid', 'proptax', 'childcare', 'mortgage', 'otherprop', 'nonprop', 'transfers', 'otheritem'];
  expenseOrder.forEach(varName => {
    const mapping = mappings.find(m => m.taxsim === varName);
    if (mapping) sortedMappings.push(mapping);
  });

  return sortedMappings;
}

/**
 * Extract income splitting rules (these are hardcoded in the Python code)
 */
function extractIncomeSplittingRules() {
  const incomeTypesSplit = [
    'taxable_interest_income',
    'qualified_dividend_income',
    'long_term_capital_gains',
    'partnership_s_corp_income',
    'taxable_private_pension_income',
    'short_term_capital_gains',
    'social_security_retirement'
  ];

  const incomeTypesNotSplit = [
    'employment_income (uses separate pwages/swages fields)',
    'self_employment_income (uses separate psemp/ssemp fields)',
    'unemployment_compensation (uses separate pui/sui fields)'
  ];

  return {
    incomeTypesSplit,
    incomeTypesNotSplit
  };
}

/**
 * Extract system assumptions
 */
function extractSystemAssumptions() {
  return {
    defaultAges: {
      primary: 40,
      spouse: 40,
      dependent: 10
    },
    maritalStatusCodes: {
      single: 1,
      marriedFilingJointly: 2
    },
    missingIncomeValue: 0
  };
}

/**
 * Extract implementation details
 */
function extractImplementationDetails() {
  return {
    outputTypes: [
      { code: 0, name: 'Standard', description: 'Basic tax liability output' },
      { code: 2, name: 'Full', description: 'Detailed calculation breakdown' },
      { code: 5, name: 'Full Text', description: 'Complete variable descriptions and values' }
    ],
    knownLimitations: [
      'Variables marked as "N/A" are currently not implemented in the Emulator but are supported by both models',
      'Calculations may vary due to differences in the model coverage and know limitations',
      'Marginal rate calculations are not currently supported',
    ],
    multipleVariableHandling: [
      { 
        taxsim: 'v28 (Income Tax Before Credits)', 
        policyengine: 'income_tax_main_rates + capital_gains_tax' 
      },
      { 
        taxsim: 'v40 (Total Credits)', 
        policyengine: 'state_non_refundable_credits + state_refundable_credits' 
      }
    ]
  };
}

// Skip extraction if the YAML source is unavailable (e.g. Vercel deployment
// where the root directory is cps-dashboard and the parent repo isn't present).
// The committed public/config-data.json will be used instead.
if (!fs.existsSync(yamlPath)) {
  console.log(`⏭️  YAML source not found at ${yamlPath}`);
  console.log('   Using committed config-data.json (this is expected on Vercel)');
  process.exit(0);
}

try {
  console.log('Reading YAML configuration from:', yamlPath);

  // Read and parse the original YAML file
  const yamlContent = fs.readFileSync(yamlPath, 'utf8');
  const config = yaml.load(yamlContent);

  // Extract all the data
  const extractedData = {
    variableMappings: extractTaxsimToPolicyEngineMappings(config),
    incomeSplittingRules: extractIncomeSplittingRules(),
    systemAssumptions: extractSystemAssumptions(),
    implementationDetails: extractImplementationDetails(),
    lastUpdated: new Date().toISOString()
  };

  // Write the extracted data to a JSON file
  fs.writeFileSync(outputPath, JSON.stringify(extractedData, null, 2));

  console.log(`✅ Configuration data extracted successfully!`);
  console.log(`📁 Output file: ${outputPath}`);
  console.log(`📊 Variable mappings: ${extractedData.variableMappings.length}`);
  console.log(`🔄 Income types split: ${extractedData.incomeSplittingRules.incomeTypesSplit.length}`);

} catch (error) {
  console.error('❌ Error extracting configuration:', error);
  process.exit(1);
}
