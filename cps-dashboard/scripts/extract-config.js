const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// Path to the original YAML file
const yamlPath = path.join(__dirname, '../../policyengine_taxsim/config/variable_mappings.yaml');
const outputPath = path.join(__dirname, '../public/config-data.json');

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

        // Handle special cases
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
        } else if (taxsimVar === 'sage') {
          policyengineVar = 'age';
          implemented = true;
        } else if (taxsimVar === 'sui') {
          policyengineVar = 'unemployment_compensation';
          implemented = true;
        }

        // Mark certain variables as not available in PolicyEngine
        const notAvailableVars = ['otherprop', 'nonprop', 'transfers', 'otheritem', 'pprofinc'];
        if (notAvailableVars.includes(taxsimVar) && policyengineVar === 'Not mapped') {
          policyengineVar = 'na_pe';
          implemented = false;
        }

        mappings.push({
          taxsim: taxsimVar,
          policyengine: policyengineVar,
          description: description,
          implemented: implemented
        });
      });
    }
  });

  return mappings;
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
      'Variables marked as "na_pe" (not available in PolicyEngine) are not implemented',
      'Some state-specific calculations may have different implementations',
      'Marginal rate calculations are not currently supported',
      'FICA calculations use PolicyEngine methodology, not TAXSIM\'s approach'
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
