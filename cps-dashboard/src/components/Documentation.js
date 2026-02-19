import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiCheck, FiX, FiCopy, FiHome, FiBarChart2, FiGithub, FiBook } from 'react-icons/fi';
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
  const [activeSection, setActiveSection] = useState('installation');


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
  const createDivider = (title, color = 'var(--blue-primary)') => (
    <div className="doc-var-divider" style={{ borderLeftColor: color }}>
      {title}
    </div>
  );

  // Shared function to render variable rows
  const renderVariableRow = (mapping, index) => (
    <div key={`var-${index}`} className="doc-var-row">
      <div className="doc-var-names">
        <code className="doc-var-taxsim">{mapping.taxsim}</code>
        <span className="doc-var-arrow">→</span>
        <span className="doc-var-pe">
          {activeTab === 'output' ? renderOutputPolicyEngineCell(mapping) : renderInputPolicyEngineCell(mapping)}
        </span>
      </div>
      <p className="doc-var-description">{mapping.description}</p>
      <span className={`doc-var-status ${mapping.implemented ? 'doc-var-status-yes' : 'doc-var-status-no'}`}>
        {mapping.implemented ? <><FiCheck size={12} /> Implemented</> : <><FiX size={12} /> Not Implemented</>}
      </span>
    </div>
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
          <button className="landing-nav-link landing-nav-link-active">
            <FiBook style={{ marginRight: '6px' }} />
            Documentation
          </button>
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

        {/* Section Tabs */}
        <section className="landing-section" style={{ paddingBottom: 0 }}>
          <div className="landing-section-inner">
            <div className="landing-tab-bar">
              <button
                onClick={() => setActiveSection('installation')}
                className={`landing-tab-button ${activeSection === 'installation' ? 'landing-tab-active' : ''}`}
              >
                Installation & Usage
              </button>
              <button
                onClick={() => setActiveSection('options')}
                className={`landing-tab-button ${activeSection === 'options' ? 'landing-tab-active' : ''}`}
              >
                All Runners & CLI
              </button>
              <button
                onClick={() => setActiveSection('mappings')}
                className={`landing-tab-button ${activeSection === 'mappings' ? 'landing-tab-active' : ''}`}
              >
                Variable Mappings
              </button>
            </div>
          </div>
        </section>

        {/* Installation & Usage */}
        {activeSection === 'installation' && (
          <section className="landing-section">
            <div className="landing-section-inner">
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
          </section>
        )}

        {/* All Runners & CLI */}
        {activeSection === 'options' && (
          <section className="landing-section">
            <div className="landing-section-inner">

              {/* TaxsimRunner */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', marginBottom: '12px' }}>
                TaxsimRunner
              </h3>
              <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
                Runs the official TAXSIM-35 executable locally. Requires the TAXSIM binary
                (auto-detected on macOS, Linux, and Windows). Useful for generating reference
                outputs to compare against PolicyEngine.
              </p>
              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">TaxsimRunner</code>
                  <span className="doc-option-type">input_df, taxsim_path=None</span>
                </div>
                <p className="doc-option-description">
                  Takes a TAXSIM-formatted DataFrame and an optional path to the TAXSIM executable.
                  If <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>taxsim_path</code> is
                  not provided, the runner auto-detects the bundled executable for your OS.
                </p>
                {renderCodeBlock({
                  id: 'taxsim-runner',
                  label: 'Python',
                  code: `from policyengine_taxsim.runners import TaxsimRunner

runner = TaxsimRunner(df)
taxsim_results = runner.run()`
                })}
              </div>

              {/* PolicyEngineRunner advanced options */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', margin: '32px 0 12px' }}>
                PolicyEngineRunner — Advanced Options
              </h3>
              <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
                Beyond the basic usage shown in Installation & Usage, <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>PolicyEngineRunner</code> accepts
                additional options for policy simulations and debugging.
                These options are currently available in the Python API only.
              </p>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">disable_salt</code>
                  <span className="doc-option-type">bool, default False</span>
                </div>
                <p className="doc-option-description">
                  Sets the State and Local Tax (SALT) deduction to zero for all records.
                  Useful for modeling the impact of SALT cap policies — for example,
                  the $10,000 SALT deduction cap introduced by the 2017 Tax Cuts and Jobs Act.
                </p>
                {renderCodeBlock({
                  id: 'option-salt',
                  label: 'Example',
                  code: `runner = PolicyEngineRunner(df, disable_salt=True)
results = runner.run()`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">logs</code>
                  <span className="doc-option-type">bool, default False</span>
                </div>
                <p className="doc-option-description">
                  Generates detailed YAML log files for each household calculation.
                  Useful for debugging discrepancies or auditing how PolicyEngine
                  maps TAXSIM inputs to its internal variables.
                </p>
                {renderCodeBlock({
                  id: 'option-logs',
                  label: 'Example',
                  code: `runner = PolicyEngineRunner(df, logs=True)
results = runner.run()`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">show_progress</code>
                  <span className="doc-option-type">bool, default True (passed to .run())</span>
                </div>
                <p className="doc-option-description">
                  Controls whether progress bars are displayed during calculation.
                  Set to <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>False</code> for
                  batch jobs or automated pipelines.
                </p>
                {renderCodeBlock({
                  id: 'option-progress',
                  label: 'Example',
                  code: `runner = PolicyEngineRunner(df)
results = runner.run(show_progress=False)`
                })}
              </div>

              {/* CLI */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', margin: '32px 0 12px' }}>
                Command-Line Interface
              </h3>
              <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
                All runners are also available via the <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>policyengine-taxsim</code> CLI.
                Each command accepts a TAXSIM-formatted CSV file as input.
              </p>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim policyengine</code>
                </div>
                <p className="doc-option-description">
                  Run PolicyEngine tax calculations on a TAXSIM input file.
                  Supports <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--disable-salt</code>,{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--logs</code>, and{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--sample N</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-pe',
                  label: 'Terminal',
                  code: `policyengine-taxsim policyengine input.csv -o output.csv
policyengine-taxsim policyengine input.csv --disable-salt --logs`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim taxsim</code>
                </div>
                <p className="doc-option-description">
                  Run the official TAXSIM-35 executable on a TAXSIM input file.
                  Optionally specify a custom path to the TAXSIM binary with{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--taxsim-path</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-taxsim',
                  label: 'Terminal',
                  code: `policyengine-taxsim taxsim input.csv -o taxsim_output.csv`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim compare</code>
                </div>
                <p className="doc-option-description">
                  Run both PolicyEngine and TAXSIM-35 on the same input, then compare the
                  results. Outputs a comparison report with match rates and differences.
                </p>
                {renderCodeBlock({
                  id: 'cli-compare',
                  label: 'Terminal',
                  code: `policyengine-taxsim compare input.csv --output-dir comparison_output`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim sample-data</code>
                </div>
                <p className="doc-option-description">
                  Sample N records from a large dataset. Useful for testing on a subset
                  before running on the full file.
                </p>
                {renderCodeBlock({
                  id: 'cli-sample',
                  label: 'Terminal',
                  code: `policyengine-taxsim sample-data input.csv --sample 100 -o sample.csv`
                })}
              </div>
            </div>
          </section>
        )}

        {/* Variable Mappings */}
        {activeSection === 'mappings' && (
          <section className="landing-section">
            <div className="landing-section-inner">
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

              <div className="doc-intro-blurb" style={{ marginBottom: '24px' }}>
                <strong>Note on extended coverage:</strong> Because this emulator is powered by
                PolicyEngine's microsimulation model, it can calculate variables beyond what
                TAXSIM-35 provides. The mappings below show the standard TAXSIM
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

              {/* Variable Mappings */}
              <div className="doc-var-list">
                {activeTab === 'input' ? renderInputVariables() : renderOutputVariables()}
              </div>
            </div>
          </section>
        )}

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
      if (basicInputs.includes(mapping.taxsim) && !hasAddedBasic) {
        results.push(<React.Fragment key="divider-basic">{createDivider('Basic Inputs')}</React.Fragment>);
        hasAddedBasic = true;
      } else if (incomeInputs.includes(mapping.taxsim) && !hasAddedIncome) {
        results.push(<React.Fragment key="divider-income">{createDivider('Income Inputs', 'var(--teal-accent)')}</React.Fragment>);
        hasAddedIncome = true;
      } else if (businessIncomeInputs.includes(mapping.taxsim) && !hasAddedBusiness) {
        results.push(<React.Fragment key="divider-business">{createDivider('Business Income', 'var(--dark-gray)')}</React.Fragment>);
        hasAddedBusiness = true;
      } else if (expenseInputs.includes(mapping.taxsim) && !hasAddedExpense) {
        results.push(<React.Fragment key="divider-expense">{createDivider('Expense & Deduction Inputs')}</React.Fragment>);
        hasAddedExpense = true;
      }

      results.push(renderVariableRow(mapping, index));
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
      if (basicOutputs.includes(mapping.taxsim) && !hasAddedBasic) {
        results.push(<React.Fragment key="divider-basic">{createDivider('Basic Outputs')}</React.Fragment>);
        hasAddedBasic = true;
      } else if (taxOutputs.includes(mapping.taxsim) && !hasAddedTax) {
        results.push(<React.Fragment key="divider-tax">{createDivider('Primary Tax Calculations')}</React.Fragment>);
        hasAddedTax = true;
      } else if (agiOutputs.includes(mapping.taxsim) && !hasAddedAGI) {
        results.push(<React.Fragment key="divider-agi">{createDivider('Adjusted Gross Income', 'var(--teal-accent)')}</React.Fragment>);
        hasAddedAGI = true;
      } else if (deductionOutputs.includes(mapping.taxsim) && !hasAddedDeduction) {
        results.push(<React.Fragment key="divider-deduction">{createDivider('Deductions & Exemptions', 'var(--dark-gray)')}</React.Fragment>);
        hasAddedDeduction = true;
      } else if (taxableIncomeOutputs.includes(mapping.taxsim) && !hasAddedTaxableIncome) {
        results.push(<React.Fragment key="divider-taxable">{createDivider('Taxable Income & Tax Calculations')}</React.Fragment>);
        hasAddedTaxableIncome = true;
      } else if (creditOutputs.includes(mapping.taxsim) && !hasAddedCredit) {
        results.push(<React.Fragment key="divider-credit">{createDivider('Tax Credits', 'var(--teal-accent)')}</React.Fragment>);
        hasAddedCredit = true;
      } else if (amtOutputs.includes(mapping.taxsim) && !hasAddedAMT) {
        results.push(<React.Fragment key="divider-amt">{createDivider('Alternative Minimum Tax', 'var(--dark-gray)')}</React.Fragment>);
        hasAddedAMT = true;
      } else if (stateOutputs.includes(mapping.taxsim) && !hasAddedState) {
        results.push(<React.Fragment key="divider-state">{createDivider('State-Specific Calculations')}</React.Fragment>);
        hasAddedState = true;
      } else if (additionalOutputs.includes(mapping.taxsim) && !hasAddedAdditional) {
        results.push(<React.Fragment key="divider-additional">{createDivider('Additional Outputs', 'var(--teal-accent)')}</React.Fragment>);
        hasAddedAdditional = true;
      }

      results.push(renderVariableRow(mapping, index));
    });

    return results;
  }
};

export default Documentation;