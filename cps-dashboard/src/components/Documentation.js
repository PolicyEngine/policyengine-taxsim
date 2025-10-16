import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiChevronDown, FiChevronRight, FiCheck, FiX } from 'react-icons/fi';
import { loadConfigurationData } from '../utils/configLoader';
import LoadingSpinner from './common/LoadingSpinner';
import { 
  OUTPUT_VARIABLES, 
  INPUT_VARIABLE_CATEGORIES,
  OUTPUT_VARIABLE_CATEGORIES,
  getVariablePath,
  getMultipleVariables
} from '../constants';

const Documentation = ({ onBackToDashboard }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('input'); // 'input' or 'output'
  const [expandedSections, setExpandedSections] = useState({
    mappings: true,
    assumptions: false,
    implementation: false
  });


  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [configData, setConfigData] = useState({
    variableMappings: [],
    incomeSplittingRules: {},
    systemAssumptions: {},
    implementationDetails: {}
  });

  // Load configuration data on component mount
  useEffect(() => {
    const loadConfigData = async () => {
      try {
        setLoading(true);
        const configData = await loadConfigurationData();
        
        setConfigData(configData);
        setError(null);
      } catch (err) {
        console.error('Failed to load configuration:', err);
        setError('Failed to load configuration data. Please try refreshing the page.');
      } finally {
        setLoading(false);
      }
    };

    loadConfigData();
  }, []);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Shared function to create section dividers
  const createDivider = (title, color = 'var(--blue-primary)', bgColor = 'var(--blue-98)') => (
    <tr>
      <td colSpan="4" style={{ 
        padding: '12px 20px',
        backgroundColor: bgColor,
        borderTop: `2px solid ${color}`,
        borderBottom: `2px solid ${color}`,
        textAlign: 'center',
        fontWeight: '600',
        fontSize: '14px',
        color: color === 'var(--blue-primary)' ? 'var(--darkest-blue)' : 'var(--teal-pressed)',
        textTransform: 'uppercase',
        letterSpacing: '0.5px'
      }}>
        {title}
      </td>
    </tr>
  );

  // Shared function to render variable rows
  const renderVariableRow = (mapping, index, categoryClass = '') => (
    <tr key={`var-${index}`} style={{ 
      ...(categoryClass ? { backgroundColor: categoryClass } : {}),
      cursor: 'default'
    }}>
      <td style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: '600', color: 'var(--blue-primary)' }}>
        {mapping.taxsim}
      </td>
      <td style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: '600', color: 'var(--darkest-blue)' }}>
        {activeTab === 'output' ? renderOutputPolicyEngineCell(mapping) : renderInputPolicyEngineCell(mapping)}
      </td>
      <td style={{ 
        fontSize: '14px', 
        color: 'var(--dark-gray)',
        whiteSpace: 'normal',
        wordWrap: 'break-word',
        maxWidth: '300px',
        lineHeight: '1.4'
      }}>
        {mapping.description}
      </td>
      <td style={{ textAlign: 'center' }}>
        {mapping.implemented ? (
          <span className="status-badge status-badge-match">
            <FiCheck className="w-3 h-3 mr-1" />
            Implemented
          </span>
        ) : (
          <span className="status-badge status-badge-mismatch">
            <FiX className="w-3 h-3 mr-1" />
            Not Implemented
          </span>
        )}
      </td>
    </tr>
  );

  // Function to render PolicyEngine cell for output variables (with multiple variables support)
  const renderOutputPolicyEngineCell = (mapping) => {
    const multipleVars = getMultipleVariables(mapping.taxsim);
    
    if (multipleVars && mapping.implemented) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {multipleVars.map((varName, index) => (
            <a 
              key={index}
              href={`https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables/${getVariablePath(varName)}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ 
                color: 'var(--blue-primary)', 
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                cursor: 'pointer',
                fontSize: '11px'
              }}
              onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
              onMouseOut={(e) => e.target.style.textDecoration = 'none'}
            >
              {varName}
              <FiExternalLink style={{ marginLeft: '4px', fontSize: '9px' }} />
            </a>
          ))}
        </div>
      );
    } else if (mapping.implemented && mapping.policyengine && mapping.policyengine !== 'na_pe' && 
               mapping.policyengine !== 'taxsimid' && mapping.policyengine !== 'get_year') {
      return (
        <a 
          href={`https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables/${getVariablePath(mapping.policyengine)}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ 
            color: 'var(--blue-primary)', 
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            cursor: 'pointer'
          }}
          onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
          onMouseOut={(e) => e.target.style.textDecoration = 'none'}
        >
          {mapping.policyengine}
          <FiExternalLink style={{ marginLeft: '4px', fontSize: '10px' }} />
        </a>
      );
    } else {
      return mapping.policyengine || 'N/A';
    }
  };

  // Function to render PolicyEngine cell for input variables
  const renderInputPolicyEngineCell = (mapping) => {
    if (mapping.implemented && mapping.policyengine !== 'na_pe' && mapping.githubLink) {
      return (
        <a 
          href={mapping.githubLink}
          target="_blank"
          rel="noopener noreferrer"
          style={{ 
            color: 'var(--blue-primary)', 
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            cursor: 'pointer'
          }}
          onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
          onMouseOut={(e) => e.target.style.textDecoration = 'none'}
        >
          {mapping.policyengine}
          <FiExternalLink style={{ marginLeft: '4px', fontSize: '10px' }} />
        </a>
      );
    } else if (mapping.implemented && mapping.policyengine !== 'na_pe') {
      return mapping.policyengine;
    } else {
      return 'N/A';
    }
  };

  // Create output mappings from OUTPUT_VARIABLES with actual implementation status
  // CRITICAL RULE: Variables with 'na_pe' = NOT AVAILABLE IN POLICYENGINE = NOT IMPLEMENTED
  // Only variables with actual PolicyEngine variable names are implemented
  const actualImplementationStatus = {
    // IMPLEMENTED variables (have actual PolicyEngine variable mappings)
    'taxsimid': { implemented: true, variable: 'taxsimid' },
    'year': { implemented: true, variable: 'get_year' },
    'state': { implemented: true, variable: 'state_code' },
    'fiitax': { implemented: true, variable: 'income_tax' },
    'siitax': { implemented: true, variable: 'state_income_tax' },
    'tfica': { implemented: true, variable: 'taxsim_tfica' },
    'v10': { implemented: true, variable: 'adjusted_gross_income' },
    'v11': { implemented: true, variable: 'tax_unit_taxable_unemployment_compensation' },
    'v12': { implemented: true, variable: 'tax_unit_taxable_social_security' },
    'v13': { implemented: true, variable: 'standard_deduction' },
    'v14': { implemented: true, variable: 'exemptions' },
    'v17': { implemented: true, variable: 'itemized_taxable_income_deductions' },
    'v18': { implemented: true, variable: 'taxable_income' },
    'v19': { implemented: true, variable: 'income_tax_main_rates' },
    'v22': { implemented: true, variable: 'ctc_value' },
    'v24': { implemented: true, variable: 'cdcc' },
    'v25': { implemented: true, variable: 'eitc' },
    'v26': { implemented: true, variable: 'amt_income' },
    'v27': { implemented: true, variable: 'alternative_minimum_tax' },
    'v28': { implemented: true, variable: 'multiple_variables' },
    'v32': { implemented: true, variable: 'state_agi' },
    'v34': { implemented: true, variable: 'state_standard_deduction' },
    'v35': { implemented: true, variable: 'state_itemized_deductions' },
    'v36': { implemented: true, variable: 'state_taxable_income' },
    'v37': { implemented: true, variable: 'state_property_tax_credit' },
    'v38': { implemented: true, variable: 'state_cdcc' },
    'v39': { implemented: true, variable: 'state_eitc' },
    'v40': { implemented: true, variable: 'multiple_variables' },
    'v44': { implemented: true, variable: 'multiple_variable' },
    'qbid': { implemented: true, variable: 'qualified_business_income_deduction' },
    'niit': { implemented: true, variable: 'net_investment_income_tax' },
    'sctc': { implemented: true, variable: 'state_ctc' },
    'cares': { implemented: true, variable: 'recovery_rebate_credit' },
    'actc': { implemented: true, variable: 'refundable_ctc' }, // Implemented as refundable CTC
    'staxbc': { implemented: true, variable: 'state_income_tax_before_non_refundable_credits' }, 

    
    // ❌ NOT IMPLEMENTED variables - ALL HAVE 'na_pe' (NOT AVAILABLE IN POLICYENGINE)
    // IF variable = 'na_pe' --> IT IS NOT IMPLEMENTED
    'fica': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'frate': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'srate': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'ficar': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v15': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v16': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v20': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v21': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v23': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v30': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v31': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v33': { implemented: false, variable: 'state_exemptions' }, // Special case: still not implemented
    'v41': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v42': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v43': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'v45': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'srebate': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'senergy': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'sptcr': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'samt': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'addmed': { implemented: false, variable: 'na_pe' }, // na_pe = NOT IMPLEMENTED
    'cdate': { implemented: false, variable: 'na_pe' } // na_pe = NOT IMPLEMENTED
  };

  const outputMappings = OUTPUT_VARIABLES.map(variable => {
    const actualStatus = actualImplementationStatus[variable.code];
    const isImplemented = actualStatus ? actualStatus.implemented : false;
    const actualVariable = actualStatus ? actualStatus.variable : variable.policyengine;
    
    return {
      taxsim: variable.code,
      policyengine: isImplemented && actualVariable !== 'na_pe' ? actualVariable : null,
      description: variable.name,
      implemented: isImplemented,
      githubLink: isImplemented && actualVariable !== 'na_pe' ? `https://github.com/PolicyEngine/policyengine-us/tree/master/policyengine_us/variables` : null
    };
  });

  // Filter mappings based on search term and active tab
  const currentMappings = activeTab === 'input' ? configData.variableMappings : outputMappings;
  const filteredMappings = currentMappings.filter(mapping =>
    mapping.taxsim.toLowerCase().includes(searchTerm.toLowerCase()) ||
    mapping.policyengine.toLowerCase().includes(searchTerm.toLowerCase()) ||
    mapping.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Show loading spinner while data is being loaded
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100">
        <header className="main-header shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex-between py-6">
              <h1 className="text-3xl main-title">
                Emulator Documentation
              </h1>
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <LoadingSpinner 
            message="Loading configuration data..." 
            subMessage="Please wait while we load the variable mappings"
          />
        </main>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-100">
        <header className="main-header shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex-between py-6">
              <h1 className="text-3xl main-title">
                Emulator Documentation
              </h1>
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="error-card">
            <div className="error-icon">⚠️</div>
            <h2 style={{ color: 'var(--dark-red)', marginBottom: '12px' }}>Configuration Load Error</h2>
            <p style={{ color: 'var(--dark-gray)' }}>{error}</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="main-header shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex-between py-6">
            <h1 className="text-3xl main-title">
              Emulator Documentation
            </h1>
            {onBackToDashboard && (
              <button
                onClick={onBackToDashboard}
                className="btn-ghost"
              >
                Back to Dashboard
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="space-y-8">
          
          {/* TAXSIM to PolicyEngine Mappings Section */}
          <section className="card-container">
            <div 
              className="card-header cursor-pointer"
              onClick={() => toggleSection('mappings')}
            >
              <h2 className="section-title flex items-center">
                {expandedSections.mappings ? <FiChevronDown className="mr-2" /> : <FiChevronRight className="mr-2" />}
                TAXSIM to PolicyEngine Variable Mappings
              </h2>
            </div>
            
            {expandedSections.mappings && (
              <div style={{ padding: '24px 32px', background: 'var(--white)' }}>
                <div className="mb-6">
                  <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '14px', lineHeight: '1.6' }}>
                    {activeTab === 'input' 
                      ? 'This table shows how TAXSIM input variables are mapped to PolicyEngine variables in our implementation. '
                      : 'This table shows the TAXSIM output variables that are calculated and returned by both systems. '
                    }
                    For complete TAXSIM variable documentation, refer to the official documentation:
                  </p>
                  <a 
                    href="https://taxsim.nber.org/taxsimtest/" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    style={{ 
                      display: 'inline-flex', 
                      alignItems: 'center', 
                      color: 'var(--blue-primary)', 
                      fontWeight: '600',
                      textDecoration: 'none',
                      fontSize: '14px'
                    }}
                    onMouseOver={(e) => e.target.style.color = 'var(--dark-blue-hover)'}
                    onMouseOut={(e) => e.target.style.color = 'var(--blue-primary)'}
                  >
                    TAXSIM Official Documentation
                    <FiExternalLink className="ml-1 w-4 h-4" />
                  </a>
                </div>

                {/* Tab Navigation */}
                <div className="tab-navigation">
                  <button
                    onClick={() => setActiveTab('input')}
                    className={`tab-button ${activeTab === 'input' ? 'tab-button-active' : ''}`}
                  >
                    Input Variables
                  </button>
                  <button
                    onClick={() => setActiveTab('output')}
                    className={`tab-button ${activeTab === 'output' ? 'tab-button-active' : ''}`}
                  >
                    Output Variables
                  </button>
                </div>

                {/* Search Bar */}
                <div className="mb-4">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search variables..."
                      className="select"
                      style={{ paddingLeft: '16px', width: '100%', maxWidth: '400px' }}
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                </div>

                {/* Variable Mappings Table */}
                <div className="overflow-x-auto">
                  <table className="state-table">
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>TAXSIM Variable</th>
                        <th style={{ textAlign: 'left' }}>PolicyEngine Variable</th>
                        <th style={{ textAlign: 'left' }}>Description</th>
                        <th style={{ textAlign: 'center' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeTab === 'input' ? renderInputVariables() : renderOutputVariables()}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          {/* System Assumptions Section */}
          <section className="card-container">
            <div 
              className="card-header cursor-pointer"
              onClick={() => toggleSection('assumptions')}
            >
              <h2 className="section-title flex items-center">
                {expandedSections.assumptions ? <FiChevronDown className="mr-2" /> : <FiChevronRight className="mr-2" />}
                System Assumptions
              </h2>
            </div>
            
            {expandedSections.assumptions && (
              <div style={{ padding: '24px 32px', background: 'var(--white)' }} className="space-y-6">
                
                {/* Income Splitting Rules */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Income Splitting Rules (Married Filing Jointly)</h3>
                  <p style={{ color: 'var(--dark-gray)', marginBottom: '20px', fontSize: '14px', lineHeight: '1.6' }}>
                    When processing married filing jointly households (mstat = 2), certain income types are automatically 
                    split evenly (50/50) between the primary taxpayer and spouse, while others use separate input fields.
                  </p>
                  
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <h4 style={{ fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '12px', fontSize: '16px' }}>Income Types Split 50/50:</h4>
                      <ul style={{ listStyle: 'none', padding: 0 }}>
                        {configData.incomeSplittingRules.incomeTypesSplit?.map((type, index) => (
                          <li key={index} style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                            <span style={{ width: '8px', height: '8px', backgroundColor: 'var(--blue-primary)', borderRadius: '50%', marginRight: '12px' }}></span>
                            <code style={{ backgroundColor: 'var(--blue-98)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>{type}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                    
                    <div>
                      <h4 style={{ fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '12px', fontSize: '16px' }}>Income Types with Separate Fields:</h4>
                      <ul style={{ listStyle: 'none', padding: 0 }}>
                        {configData.incomeSplittingRules.incomeTypesNotSplit?.map((type, index) => (
                          <li key={index} style={{ display: 'flex', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <span style={{ width: '8px', height: '8px', backgroundColor: 'var(--teal-accent)', borderRadius: '50%', marginRight: '12px', marginTop: '6px', flexShrink: 0 }}></span>
                            <code style={{ backgroundColor: 'var(--teal-light)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>{type}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                {/* Default Values */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Default Values</h3>
                  <div style={{ backgroundColor: 'var(--blue-98)', padding: '20px', borderRadius: '8px', border: '1px solid var(--blue-95)' }}>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Primary/Age of secondary taxpayer:</strong> {configData.systemAssumptions.defaultAges?.primary || 40} years (when not specified)</li>
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Dependent Age:</strong> {configData.systemAssumptions.defaultAges?.dependent || 10} years (when not specified or age is 0)</li>
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Missing Income Values:</strong> ${configData.systemAssumptions.missingIncomeValue || 0}</li>
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Single Taxpayer:</strong> mstat = {configData.systemAssumptions.maritalStatusCodes?.single || 1}</li>
                      <li style={{ marginBottom: '0', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Married Filing Jointly:</strong> mstat = {configData.systemAssumptions.maritalStatusCodes?.marriedFilingJointly || 2}</li>
                    </ul>
                  </div>
                </div>

                {/* Household Structure Logic */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Household Structure Logic</h3>
                  <div className="space-y-3">
                    <div style={{ borderLeft: '4px solid var(--blue-primary)', paddingLeft: '16px', marginBottom: '16px' }}>
                      <strong style={{ color: 'var(--darkest-blue)', fontSize: '14px' }}>Single Taxpayer (mstat = 1):</strong>
                      <p style={{ color: 'var(--dark-gray)', fontSize: '14px', margin: '4px 0 0 0', lineHeight: '1.6' }}>Creates household with "you" only, plus any dependents specified by depx</p>
                    </div>
                    <div style={{ borderLeft: '4px solid var(--teal-accent)', paddingLeft: '16px', marginBottom: '16px' }}>
                      <strong style={{ color: 'var(--darkest-blue)', fontSize: '14px' }}>Married Filing Jointly (mstat = 2):</strong>
                      <p style={{ color: 'var(--dark-gray)', fontSize: '14px', margin: '4px 0 0 0', lineHeight: '1.6' }}>Creates household with "you" and "your partner", plus any dependents specified by depx</p>
                    </div>
                    <div style={{ borderLeft: '4px solid var(--dark-gray)', paddingLeft: '16px', marginBottom: '0' }}>
                      <strong style={{ color: 'var(--darkest-blue)', fontSize: '14px' }}>Dependents:</strong>
                      <p style={{ color: 'var(--dark-gray)', fontSize: '14px', margin: '4px 0 0 0', lineHeight: '1.6' }}>Named as "your first dependent", "your second dependent", etc., based on depx value</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* Implementation Details Section */}
          <section className="card-container">
            <div 
              className="card-header cursor-pointer"
              onClick={() => toggleSection('implementation')}
            >
              <h2 className="section-title flex items-center">
                {expandedSections.implementation ? <FiChevronDown className="mr-2" /> : <FiChevronRight className="mr-2" />}
                Implementation Details
              </h2>
            </div>
            
            {expandedSections.implementation && (
              <div style={{ padding: '24px 32px', background: 'var(--white)' }} className="space-y-6">
                
                {/* Output Types */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Output Types (idtl)</h3>
                  <div className="space-y-3">
                    {configData.implementationDetails.outputTypes?.map((outputType, index) => (
                      <div key={index} className={`metric-card ${index === 0 ? 'federal' : index === 1 ? 'state' : 'total'}`}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                          <span className={`status-badge ${index === 0 ? 'status-badge-match' : ''}`} 
                                style={{ 
                                  marginRight: '16px',
                                  ...(index === 1 ? { backgroundColor: 'var(--teal-light)', color: 'var(--teal-pressed)', border: '1px solid var(--teal-accent)' } : {}),
                                  ...(index === 2 ? { backgroundColor: 'var(--light-gray)', color: 'var(--dark-gray)', border: '1px solid var(--medium-dark-gray)' } : {})
                                }}>
                            {outputType.name} ({outputType.code})
                          </span>
                          <span style={{ color: 'var(--dark-gray)', fontSize: '14px' }}>{outputType.description}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Known Limitations */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Known Limitations</h3>
                  <div style={{ backgroundColor: 'rgba(181, 13, 13, 0.04)', border: '1px solid rgba(181, 13, 13, 0.2)', borderRadius: '8px', padding: '20px' }}>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      {configData.implementationDetails.knownLimitations?.map((limitation, index) => (
                        <li key={index} style={{ display: 'flex', alignItems: 'flex-start', marginBottom: index === configData.implementationDetails.knownLimitations.length - 1 ? '0' : '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}>
                          <span style={{ width: '8px', height: '8px', backgroundColor: 'var(--dark-red)', borderRadius: '50%', marginRight: '12px', marginTop: '8px', flexShrink: 0 }}></span>
                          {limitation}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Multiple Variable Handling */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Multiple Variable Handling</h3>
                  <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '14px', lineHeight: '1.6' }}>
                    Some TAXSIM output variables combine multiple PolicyEngine variables for accurate calculations:
                  </p>
                  <div style={{ backgroundColor: 'var(--blue-98)', padding: '20px', borderRadius: '8px', border: '1px solid var(--blue-95)' }}>
                    <div className="space-y-4">
                      {Object.entries(getMultipleVariables ? {
                        'v28': getMultipleVariables('v28'),
                        'v40': getMultipleVariables('v40'),
                        'v44': getMultipleVariables('v44')
                      } : {}).filter(([_, variables]) => variables).map(([taxsimCode, variables], index) => (
                        <div key={index} style={{ borderLeft: '3px solid var(--blue-primary)', paddingLeft: '16px', marginBottom: '16px' }}>
                          <div style={{ marginBottom: '8px' }}>
                            <code style={{ backgroundColor: 'var(--white)', padding: '8px 12px', borderRadius: '6px', fontSize: '13px', fontFamily: 'monospace', color: 'var(--blue-primary)', fontWeight: '700' }}>
                              {taxsimCode}
                            </code>
                            <span style={{ color: 'var(--darkest-blue)', marginLeft: '12px', fontSize: '14px', fontWeight: '600' }}>
                              {taxsimCode === 'v28' ? 'Federal Income Tax Before Credits' : 
                               taxsimCode === 'v40' ? 'State Total Credits' : 
                               taxsimCode === 'v44' ? 'Medicare Tax on Earned Income' : taxsimCode}
                            </span>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginLeft: '12px' }}>
                            {variables.map((variable, varIndex) => (
                              <div key={varIndex} style={{ display: 'flex', alignItems: 'center' }}>
                                <span style={{ color: 'var(--dark-gray)', marginRight: '8px', fontSize: '14px' }}>→</span>
                                <a 
                                  href={`https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables/${getVariablePath(variable)}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{ 
                                    color: 'var(--blue-primary)', 
                                    textDecoration: 'none',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    fontSize: '12px',
                                    fontFamily: 'monospace',
                                    fontWeight: '600'
                                  }}
                                  onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
                                  onMouseOut={(e) => e.target.style.textDecoration = 'none'}
                                >
                                  {variable}
                                  <FiExternalLink style={{ marginLeft: '4px', fontSize: '10px' }} />
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}

                    </div>
                  </div>
                </div>

                {/* Dependent Age Structures */}
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '16px' }}>Dependent Age Structures</h3>
                  <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '14px', lineHeight: '1.6' }}>
                    Our implementation supports both TAXSIM and TAXSIM32 dependent age input formats, with automatic conversion between formats as needed.
                  </p>
                  
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <h4 style={{ fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '12px', fontSize: '16px' }}>Individual Ages (TAXSIM):</h4>
                      <div style={{ backgroundColor: 'var(--blue-98)', padding: '16px', borderRadius: '8px', border: '1px solid var(--blue-95)' }}>
                        <p style={{ color: 'var(--dark-gray)', fontSize: '14px', marginBottom: '12px', lineHeight: '1.6' }}>
                          Traditional format using individual age fields:
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                          <li style={{ marginBottom: '8px' }}>
                            <code style={{ backgroundColor: 'var(--white)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>age1, age2, age3...</code>
                            <span style={{ color: 'var(--dark-gray)', marginLeft: '8px', fontSize: '13px' }}>up to age11</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                    
                    <div style={{ marginTop: '8px' }}>
                      <h4 style={{ fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '12px', fontSize: '16px' }}>Cumulative Counts (TAXSIM32):</h4>
                      <div style={{ backgroundColor: 'var(--teal-light)', padding: '16px', borderRadius: '8px', border: '1px solid var(--teal-accent)' }}>
                        <p style={{ color: 'var(--dark-gray)', fontSize: '14px', marginBottom: '12px', lineHeight: '1.6' }}>
                          Cumulative dependent counts by age bracket:
                        </p>
                        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                          <li style={{ marginBottom: '8px' }}>
                            <code style={{ backgroundColor: 'var(--white)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>dep13</code>
                            <span style={{ color: 'var(--dark-gray)', marginLeft: '8px', fontSize: '13px' }}>dependents under 13</span>
                          </li>
                          <li style={{ marginBottom: '8px' }}>
                            <code style={{ backgroundColor: 'var(--white)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>dep17</code>
                            <span style={{ color: 'var(--dark-gray)', marginLeft: '8px', fontSize: '13px' }}>dependents under 17</span>
                          </li>
                          <li style={{ marginBottom: '0' }}>
                            <code style={{ backgroundColor: 'var(--white)', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--darkest-blue)' }}>dep18</code>
                            <span style={{ color: 'var(--dark-gray)', marginLeft: '8px', fontSize: '13px' }}>dependents under 18</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: '20px' }}>
                    <h4 style={{ fontWeight: '600', color: 'var(--darkest-blue)', marginBottom: '12px', fontSize: '16px' }}>Conversion Logic:</h4>
                    <div style={{ backgroundColor: 'rgba(44, 100, 150, 0.04)', padding: '20px', borderRadius: '8px', border: '1px solid rgba(44, 100, 150, 0.2)' }}>
                      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                        <li style={{ marginBottom: '8px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}>
                          <span style={{ fontWeight: '600' }}>Under 13:</span> Assigned age 10
                        </li>
                        <li style={{ marginBottom: '8px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}>
                          <span style={{ fontWeight: '600' }}>Ages 13-16:</span> Assigned age 15
                        </li>
                        <li style={{ marginBottom: '8px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}>
                          <span style={{ fontWeight: '600' }}>Age 17:</span> Assigned age 17
                        </li>
                        <li style={{ marginBottom: '0', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}>
                          <span style={{ fontWeight: '600' }}>18 and older:</span> Assigned age 21
                        </li>
                      </ul>
                    </div>
                    <p style={{ color: 'var(--dark-gray)', marginTop: '16px', fontSize: '14px', lineHeight: '1.6' }}>
                      For complete documentation on TAXSIM32 dependent age formats, see: 
                      <a 
                        href="https://taxsim.nber.org/taxsim32/" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        style={{ 
                          color: 'var(--blue-primary)', 
                          fontWeight: '600',
                          textDecoration: 'none',
                          marginLeft: '4px'
                        }}
                        onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
                        onMouseOut={(e) => e.target.style.textDecoration = 'none'}
                      >
                        TAXSIM32 Documentation
                        <FiExternalLink style={{ marginLeft: '4px', fontSize: '12px', display: 'inline' }} />
                      </a>
                    </p>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );

  // Helper function to render input variables
  function renderInputVariables() {
    const { basicInputs, incomeInputs, businessIncomeInputs, expenseInputs } = INPUT_VARIABLE_CATEGORIES;

    const results = [];
    let hasAddedBasic = false;
    let hasAddedIncome = false;
    let hasAddedBusiness = false;
    let hasAddedExpense = false;

    filteredMappings.forEach((mapping, index) => {
      // Add section dividers
      if (basicInputs.includes(mapping.taxsim) && !hasAddedBasic) {
        results.push(React.cloneElement(createDivider('Basic Inputs'), { key: `divider-basic` }));
        hasAddedBasic = true;
      } else if (incomeInputs.includes(mapping.taxsim) && !hasAddedIncome) {
        results.push(React.cloneElement(createDivider('Income Inputs', 'var(--teal-accent)', 'var(--teal-light)'), { key: `divider-income` }));
        hasAddedIncome = true;
      } else if (businessIncomeInputs.includes(mapping.taxsim) && !hasAddedBusiness) {
        results.push(React.cloneElement(createDivider('Business Income', 'var(--dark-gray)', 'var(--light-gray)'), { key: `divider-business` }));
        hasAddedBusiness = true;
      } else if (expenseInputs.includes(mapping.taxsim) && !hasAddedExpense) {
        results.push(React.cloneElement(createDivider('Expense & Deduction Inputs', 'var(--blue-primary)', 'var(--blue-98)'), { key: `divider-expense` }));
        hasAddedExpense = true;
      }

      // Add the variable row with appropriate styling
      let categoryClass = '';
      if (basicInputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      } else if (incomeInputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(57, 198, 192, 0.02)';
      } else if (businessIncomeInputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(97, 97, 97, 0.02)';
      } else if (expenseInputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      }

      results.push(renderVariableRow(mapping, index, categoryClass));
    });

    return results;
  }

  // Helper function to render output variables
  function renderOutputVariables() {
    const { basicOutputs, taxOutputs, agiOutputs, deductionOutputs, taxableIncomeOutputs, creditOutputs, amtOutputs, stateOutputs, additionalOutputs } = OUTPUT_VARIABLE_CATEGORIES;

    const results = [];
    let hasAddedBasic = false;
    let hasAddedTax = false;
    let hasAddedAGI = false;
    let hasAddedDeduction = false;
    let hasAddedTaxableIncome = false;
    let hasAddedCredit = false;
    let hasAddedAMT = false;
    let hasAddedState = false;
    let hasAddedAdditional = false;

    filteredMappings.forEach((mapping, index) => {
      // Add section dividers for outputs
      if (basicOutputs.includes(mapping.taxsim) && !hasAddedBasic) {
        results.push(React.cloneElement(createDivider('Basic Outputs'), { key: `divider-basic` }));
        hasAddedBasic = true;
      } else if (taxOutputs.includes(mapping.taxsim) && !hasAddedTax) {
        results.push(React.cloneElement(createDivider('Primary Tax Calculations'), { key: `divider-tax` }));
        hasAddedTax = true;
      } else if (agiOutputs.includes(mapping.taxsim) && !hasAddedAGI) {
        results.push(React.cloneElement(createDivider('Adjusted Gross Income', 'var(--teal-accent)', 'var(--teal-light)'), { key: `divider-agi` }));
        hasAddedAGI = true;
      } else if (deductionOutputs.includes(mapping.taxsim) && !hasAddedDeduction) {
        results.push(React.cloneElement(createDivider('Deductions & Exemptions', 'var(--dark-gray)', 'var(--light-gray)'), { key: `divider-deduction` }));
        hasAddedDeduction = true;
      } else if (taxableIncomeOutputs.includes(mapping.taxsim) && !hasAddedTaxableIncome) {
        results.push(React.cloneElement(createDivider('Taxable Income & Tax Calculations', 'var(--blue-primary)', 'var(--blue-98)'), { key: `divider-taxable` }));
        hasAddedTaxableIncome = true;
      } else if (creditOutputs.includes(mapping.taxsim) && !hasAddedCredit) {
        results.push(React.cloneElement(createDivider('Tax Credits', 'var(--teal-accent)', 'var(--teal-light)'), { key: `divider-credit` }));
        hasAddedCredit = true;
      } else if (amtOutputs.includes(mapping.taxsim) && !hasAddedAMT) {
        // AMT section now only contains v26, v27 (v28 moved to taxable income)
        results.push(React.cloneElement(createDivider('Alternative Minimum Tax', 'var(--dark-gray)', 'var(--light-gray)'), { key: `divider-amt` }));
        hasAddedAMT = true;
      } else if (stateOutputs.includes(mapping.taxsim) && !hasAddedState) {
        results.push(React.cloneElement(createDivider('State-Specific Calculations', 'var(--blue-primary)', 'var(--blue-98)'), { key: `divider-state` }));
        hasAddedState = true;
      } else if (additionalOutputs.includes(mapping.taxsim) && !hasAddedAdditional) {
        results.push(React.cloneElement(createDivider('Additional Outputs', 'var(--teal-accent)', 'var(--teal-light)'), { key: `divider-additional` }));
        hasAddedAdditional = true;
      }

      // Add the variable row with appropriate styling
      let categoryClass = '';
      if (basicOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      } else if (taxOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      } else if (agiOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(57, 198, 192, 0.02)';
      } else if (deductionOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(97, 97, 97, 0.02)';
      } else if (taxableIncomeOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      } else if (creditOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(57, 198, 192, 0.02)';
      } else if (amtOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(97, 97, 97, 0.02)';
      } else if (stateOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(44, 100, 150, 0.02)';
      } else if (additionalOutputs.includes(mapping.taxsim)) {
        categoryClass = 'rgba(57, 198, 192, 0.02)';
      }

      results.push(renderVariableRow(mapping, index, categoryClass));
    });

    return results;
  }
};

export default Documentation;