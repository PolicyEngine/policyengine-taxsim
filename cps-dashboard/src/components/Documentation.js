import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiChevronDown, FiChevronRight, FiCheck, FiX, FiCopy, FiHome, FiBarChart2, FiGithub, FiBook } from 'react-icons/fi';
import { loadConfigurationData } from '../utils/configLoader';
import LoadingSpinner from './common/LoadingSpinner';
import {
  OUTPUT_VARIABLES,
  INPUT_VARIABLE_CATEGORIES,
  OUTPUT_VARIABLE_CATEGORIES,
  getVariablePath,
  getMultipleVariables
} from '../constants';

const Documentation = ({ onBackToDashboard, onNavigateHome }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('input'); // 'input' or 'output'
  const [activeInstallTab, setActiveInstallTab] = useState('python');
  const [copiedBlock, setCopiedBlock] = useState(null);
  const [expandedSections, setExpandedSections] = useState({
    installation: true,
    options: false,
    mappings: false
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

  const handleCopy = async (text, blockId) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedBlock(blockId);
      setTimeout(() => setCopiedBlock(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const codeExamples = {
    python: [
      {
        id: 'python-install',
        label: 'Install',
        code: `pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git`
      },
      {
        id: 'python-api',
        label: 'Python API',
        code: `import pandas as pd
from policyengine_taxsim.runners import PolicyEngineRunner

# Load TAXSIM-formatted input (same CSV format as TAXSIM-35)
df = pd.read_csv("input.csv")

# Run all TAXSIM output variables
runner = PolicyEngineRunner(df)
results = runner.run(show_progress=True)
results.to_csv("output.csv", index=False)`
      },
    ],
    r: [
      {
        id: 'r-install',
        label: 'Install',
        code: `# Install from GitHub (R package is in the r-package/ subdirectory)
devtools::install_github(
  "PolicyEngine/policyengine-taxsim",
  subdir = "r-package/policyenginetaxsim"
)`
      },
      {
        id: 'r-setup',
        label: 'Setup & Usage',
        code: `library(policyenginetaxsim)

# One-time setup (creates venv & installs Python package)
setup_policyengine()

# Calculate taxes with PolicyEngine
my_data <- data.frame(
  year = 2023, state = 6, mstat = 1, pwages = 50000
)
result <- policyengine_calculate_taxes(my_data)

# Compare PolicyEngine vs TAXSIM-35
comparison <- compare_with_taxsim(my_data)`
      }
    ],
  };

  const renderCodeBlock = (block) => (
    <div key={block.id} className="landing-code-block" style={{ marginBottom: '12px' }}>
      <div className="landing-code-header">
        <span className="landing-code-label">{block.label}</span>
        <button
          onClick={() => handleCopy(block.code, block.id)}
          className="landing-copy-button"
          title="Copy to clipboard"
        >
          {copiedBlock === block.id ? (
            <>
              <FiCheck size={14} />
              <span>Copied</span>
            </>
          ) : (
            <>
              <FiCopy size={14} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="landing-code-content">
        <code>{block.code}</code>
      </pre>
    </div>
  );

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

  const renderNav = () => (
    <nav className="landing-nav">
      <div className="landing-nav-inner">
        <div className="landing-nav-brand">
          <FiBook style={{ marginRight: '8px' }} />
          Documentation
        </div>
        <div className="landing-nav-links">
          {onNavigateHome && (
            <button onClick={onNavigateHome} className="landing-nav-link">
              <FiHome style={{ marginRight: '6px' }} />
              Home
            </button>
          )}
          {onBackToDashboard && (
            <button onClick={onBackToDashboard} className="landing-nav-link">
              <FiBarChart2 style={{ marginRight: '6px' }} />
              Dashboard
            </button>
          )}
          <a
            href="https://github.com/PolicyEngine/policyengine-taxsim"
            target="_blank"
            rel="noopener noreferrer"
            className="landing-nav-link"
          >
            <FiGithub style={{ marginRight: '6px' }} />
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );

  // Show loading spinner while data is being loaded
  if (loading) {
    return (
      <div className="landing-page">
        {renderNav()}
        <main className="landing-section-inner" style={{ paddingTop: '3rem', paddingBottom: '3rem' }}>
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
      <div className="landing-page">
        {renderNav()}
        <main className="landing-section-inner" style={{ paddingTop: '3rem', paddingBottom: '3rem' }}>
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
    <div className="landing-page">
      {renderNav()}

      {/* Main Content */}
      <main className="doc-content">
        {/* Intro blurb */}
        <section className="landing-section" style={{ paddingTop: '2rem', paddingBottom: '0' }}>
          <div className="landing-section-inner">
            <div className="doc-intro-blurb">
              The PolicyEngine TAXSIM Emulator supports <strong>all input and output variables</strong> provided
              by TAXSIM-35. Unlike traditional TAXSIM, which requires sending data to NBER's servers,
              this emulator <strong>runs entirely on your machine</strong> — making it suitable for
              confidential microdata (CPS, ACS, SCF, administrative records) behind institutional
              firewalls. Use the same CSV format you already know: provide household demographics,
              income, and deductions as inputs, and receive federal and state tax calculations as outputs.
            </div>
          </div>
        </section>

        {/* Installation & Usage Section */}
        <section className="landing-section">
          <div className="landing-section-inner">
            <div
              className="doc-section-header"
              onClick={() => toggleSection('installation')}
            >
              {expandedSections.installation ? <FiChevronDown size={20} /> : <FiChevronRight size={20} />}
              <h2 className="landing-section-title" style={{ marginBottom: 0 }}>Installation & Usage</h2>
            </div>

            {expandedSections.installation && (
              <div className="doc-section-body">
                <p style={{ color: 'var(--dark-gray)', marginBottom: '20px', fontSize: '15px', lineHeight: '1.7' }}>
                  Install and run the emulator using Python or R. The emulator accepts the standard
                  TAXSIM-35 CSV input format and returns matching output variables.
                </p>

                {/* Language Tabs */}
                <div className="landing-tab-bar">
                  {['python', 'r'].map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveInstallTab(tab)}
                      className={`landing-tab-button ${activeInstallTab === tab ? 'landing-tab-active' : ''}`}
                    >
                      {tab === 'python' ? 'Python' : 'R'}
                    </button>
                  ))}
                </div>

                {/* Code Blocks */}
                <div style={{ marginTop: '16px' }}>
                  {codeExamples[activeInstallTab].map(renderCodeBlock)}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Advanced Options Section */}
        <section className="landing-section landing-section-alt">
          <div className="landing-section-inner">
            <div
              className="doc-section-header"
              onClick={() => toggleSection('options')}
            >
              {expandedSections.options ? <FiChevronDown size={20} /> : <FiChevronRight size={20} />}
              <h2 className="landing-section-title" style={{ marginBottom: 0 }}>Advanced Options</h2>
            </div>

            {expandedSections.options && (
              <div className="doc-section-body">
                <p style={{ color: 'var(--dark-gray)', marginBottom: '24px', fontSize: '15px', lineHeight: '1.7' }}>
                  The Python <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>PolicyEngineRunner</code> accepts
                  additional options beyond the input data for policy simulations and debugging.
                  These options are currently available in the Python API only.
                </p>

                {/* disable_salt */}
                <div className="doc-option-card">
                  <div className="doc-option-header">
                    <code className="doc-option-name">disable_salt</code>
                    <span className="doc-option-type">bool, default False</span>
                  </div>
                  <p className="doc-option-description">
                    Sets the State and Local Tax (SALT) deduction to zero for all records.
                    This is useful for modeling the impact of SALT cap policies — for example,
                    the $10,000 SALT deduction cap introduced by the 2017 Tax Cuts and Jobs Act
                    and its potential expiration. Researchers studying SALT reform can toggle
                    this to compare outcomes with and without the deduction.
                  </p>
                  {renderCodeBlock({
                    id: 'option-salt',
                    label: 'Example',
                    code: `runner = PolicyEngineRunner(df, disable_salt=True)
results = runner.run()`
                  })}
                </div>

                {/* logs */}
                <div className="doc-option-card">
                  <div className="doc-option-header">
                    <code className="doc-option-name">logs</code>
                    <span className="doc-option-type">bool, default False</span>
                  </div>
                  <p className="doc-option-description">
                    Generates detailed YAML log files for each household calculation.
                    Useful for debugging discrepancies or auditing how PolicyEngine
                    maps TAXSIM inputs to its internal variables and computes each
                    output value step by step.
                  </p>
                  {renderCodeBlock({
                    id: 'option-logs',
                    label: 'Example',
                    code: `runner = PolicyEngineRunner(df, logs=True)
results = runner.run()`
                  })}
                </div>

                {/* show_progress */}
                <div className="doc-option-card">
                  <div className="doc-option-header">
                    <code className="doc-option-name">show_progress</code>
                    <span className="doc-option-type">bool, default True (passed to .run())</span>
                  </div>
                  <p className="doc-option-description">
                    Controls whether progress bars are displayed during calculation.
                    Set to <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>False</code> for
                    batch jobs or when running inside automated pipelines where
                    console output should be suppressed.
                  </p>
                  {renderCodeBlock({
                    id: 'option-progress',
                    label: 'Example',
                    code: `runner = PolicyEngineRunner(df)
results = runner.run(show_progress=False)`
                  })}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* TAXSIM to PolicyEngine Mappings Section */}
        <section className="landing-section">
          <div className="landing-section-inner">
            <div
              className="doc-section-header"
              onClick={() => toggleSection('mappings')}
            >
              {expandedSections.mappings ? <FiChevronDown size={20} /> : <FiChevronRight size={20} />}
              <h2 className="landing-section-title" style={{ marginBottom: 0 }}>TAXSIM to PolicyEngine Variable Mappings</h2>
            </div>

            {expandedSections.mappings && (
              <div className="doc-section-body">
                <div className="mb-6">
                  <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
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
                    className="landing-validation-link"
                  >
                    TAXSIM Official Documentation <FiExternalLink size={14} />
                  </a>
                </div>

                {/* Tab Navigation */}
                <div className="landing-tab-bar" style={{ marginBottom: '16px' }}>
                  <button
                    onClick={() => setActiveTab('input')}
                    className={`landing-tab-button ${activeTab === 'input' ? 'landing-tab-active' : ''}`}
                  >
                    Input Variables
                  </button>
                  <button
                    onClick={() => setActiveTab('output')}
                    className={`landing-tab-button ${activeTab === 'output' ? 'landing-tab-active' : ''}`}
                  >
                    Output Variables
                  </button>
                </div>

                {/* Search Bar */}
                <div className="mb-4">
                  <input
                    type="text"
                    placeholder="Search variables..."
                    className="doc-search-input"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
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
          </div>
        </section>

        {/* Notes Section */}
        <section className="landing-section">
          <div className="landing-section-inner">
            <div className="doc-intro-blurb">
              <strong>Note on extended coverage:</strong> Because this emulator is powered by
              PolicyEngine's microsimulation model, it can calculate variables beyond what
              TAXSIM-35 provides. The variable mappings above show the standard TAXSIM
              inputs and outputs, but PolicyEngine supports hundreds of additional tax and
              benefit variables. See the{' '}
              <a
                href="https://policyengine.org/us/api"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--blue-primary)', fontWeight: 600 }}
              >
                PolicyEngine API documentation
              </a>{' '}
              for the full list.
            </div>
          </div>
        </section>
      </main>

      {/* Footer — matches landing page */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-grid">
            <a
              href="https://github.com/PolicyEngine/policyengine-taxsim"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-footer-card"
            >
              <FiGithub size={20} />
              <span>GitHub Repository</span>
              <FiExternalLink size={14} className="landing-footer-external" />
            </a>
            {onBackToDashboard && (
              <button onClick={onBackToDashboard} className="landing-footer-card">
                <FiBarChart2 size={20} />
                <span>Comparison Dashboard</span>
                <FiExternalLink size={14} className="landing-footer-external" />
              </button>
            )}
            <a
              href="https://taxsim.nber.org/taxsim35/"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-footer-card"
            >
              <FiExternalLink size={20} />
              <span>TAXSIM-35 Official Docs</span>
              <FiExternalLink size={14} className="landing-footer-external" />
            </a>
          </div>
          <div className="landing-footer-copyright">
            Built by <a href="https://policyengine.org" target="_blank" rel="noopener noreferrer">PolicyEngine</a>
          </div>
        </div>
      </footer>
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