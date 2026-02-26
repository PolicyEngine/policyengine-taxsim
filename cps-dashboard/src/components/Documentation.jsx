import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiCheck, FiX, FiCopy, FiHome, FiBarChart2, FiGithub, FiBook } from 'react-icons/fi';
import { highlightCode } from '../utils/codeHighlight';
import { loadConfigurationData } from '../utils/configLoader';
import LoadingSpinner from './common/LoadingSpinner';
import {
  OUTPUT_VARIABLES,
  INPUT_VARIABLE_CATEGORIES,
  OUTPUT_VARIABLE_CATEGORIES,
  getVariablePath,
  getMultipleVariables
} from '../constants';

const LANG_LABELS = {
  cli: 'CLI',
  python: 'Python',
  r: 'R',
  stata: 'Stata',
  sas: 'SAS',
  julia: 'Julia',
};

const Documentation = ({ onBackToDashboard, onNavigateHome }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('input'); // 'input' or 'output'
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

  const [activeUsageLang, setActiveUsageLang] = useState('cli');

  const usageExamples = {
    cli: {
      code: `policyengine-taxsim < input.csv > output.csv`,
      language: 'cli',
      label: 'Shell',
    },
    python: {
      code: `from policyengine_taxsim.runners import PolicyEngineRunner
import pandas as pd

df = pd.read_csv("input.csv")
result = PolicyEngineRunner(df).run()
result.to_csv("output.csv", index=False)`,
      language: 'python',
      label: 'Python',
    },
    r: {
      code: `library(policyenginetaxsim)

my_data <- data.frame(
  year = 2023, state = 6, mstat = 1, pwages = 50000
)
result <- policyengine_calculate_taxes(my_data)`,
      language: 'r',
      label: 'R',
    },
    stata: {
      code: `export delimited using "input.csv", replace
shell policyengine-taxsim < input.csv > output.csv
import delimited using "output.csv", clear`,
      language: 'stata',
      label: 'Stata',
    },
    sas: {
      code: `%let rc = %sysfunc(system(
  policyengine-taxsim < input.csv > output.csv
));`,
      language: 'cli',
      label: 'SAS',
    },
    julia: {
      code: `run(pipeline(\`policyengine-taxsim\`,
  stdin="input.csv",
  stdout="output.csv"
))`,
      language: 'cli',
      label: 'Julia',
    },
  };

  const advancedExamples = {
    python: [
      {
        id: 'python-pin',
        label: 'Pin policyengine-us version (optional)',
        language: 'cli',
        code: `# For reproducible results, pin the underlying tax model version
pip install policyengine-us==1.555.0`
      },
      {
        id: 'python-cli-advanced',
        label: 'CLI advanced commands',
        language: 'cli',
        code: `# Run PolicyEngine on a TAXSIM input file (with output flag)
policyengine-taxsim policyengine input.csv -o output.csv

# Compare PolicyEngine vs TAXSIM35
policyengine-taxsim compare input.csv --output-dir comparison_output

# Run official TAXSIM35 locally
policyengine-taxsim taxsim input.csv -o taxsim_output.csv

# Sample records from a large dataset
policyengine-taxsim sample-data input.csv --sample 100 -o sample.csv`
      },
    ],
    r: [
      {
        id: 'r-install',
        label: 'R package installation',
        language: 'r',
        code: `# Install R package from GitHub
devtools::install_github(
  "PolicyEngine/policyengine-taxsim",
  subdir = "r-package/policyenginetaxsim"
)
# Python dependencies install automatically on first use`
      },
      {
        id: 'r-version-pin',
        label: 'Pin version & check versions',
        language: 'r',
        code: `# Pin policyengine-us to a specific version for reproducible results
setup_policyengine(force = TRUE, policyengine_us_version = "1.555.0")

# Check installed package versions
policyengine_versions()
#> policyengine-taxsim: 2.8.0
#> policyengine-us:     1.555.0
#> policyengine-core:   3.30.2`
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
        <code>{highlightCode(block.code, block.language || 'cli')}</code>
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

  const VariableLink = ({ href, label, fontSize }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="doc-var-link"
      style={fontSize ? { fontSize } : undefined}
    >
      {label}
      <FiExternalLink style={{ marginLeft: '4px', fontSize: fontSize ? '9px' : '10px' }} />
    </a>
  );

  function buildGithubUrl(varName) {
    return `https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables/${getVariablePath(varName)}`;
  }

  const renderOutputPolicyEngineCell = (mapping) => {
    const multipleVars = getMultipleVariables(mapping.taxsim);

    if (multipleVars && mapping.implemented) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {multipleVars.map((varName, index) => (
            <VariableLink key={index} href={buildGithubUrl(varName)} label={varName} fontSize="11px" />
          ))}
        </div>
      );
    }

    const NON_LINKABLE = ['na_pe', 'taxsimid', 'get_year'];
    if (mapping.implemented && mapping.policyengine && !NON_LINKABLE.includes(mapping.policyengine)) {
      return <VariableLink href={buildGithubUrl(mapping.policyengine)} label={mapping.policyengine} />;
    }

    return mapping.policyengine || 'N/A';
  };

  const renderInputPolicyEngineCell = (mapping) => {
    if (mapping.implemented && mapping.policyengine !== 'na_pe' && mapping.githubLink) {
      return <VariableLink href={mapping.githubLink} label={mapping.policyengine} />;
    }
    if (mapping.implemented && mapping.policyengine !== 'na_pe') {
      return mapping.policyengine;
    }
    return 'N/A';
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

    // Not implemented: variable = 'na_pe' means not available in PolicyEngine
    'fica': { implemented: false, variable: 'na_pe' },
    'frate': { implemented: false, variable: 'na_pe' },
    'srate': { implemented: false, variable: 'na_pe' },
    'ficar': { implemented: false, variable: 'na_pe' },
    'v15': { implemented: false, variable: 'na_pe' },
    'v16': { implemented: false, variable: 'na_pe' },
    'v20': { implemented: false, variable: 'na_pe' },
    'v21': { implemented: false, variable: 'na_pe' },
    'v23': { implemented: false, variable: 'na_pe' },
    'v30': { implemented: false, variable: 'na_pe' },
    'v31': { implemented: false, variable: 'na_pe' },
    'v33': { implemented: false, variable: 'state_exemptions' }, // Has a variable name but still not implemented
    'v41': { implemented: false, variable: 'na_pe' },
    'v42': { implemented: false, variable: 'na_pe' },
    'v43': { implemented: false, variable: 'na_pe' },
    'v45': { implemented: false, variable: 'na_pe' },
    'srebate': { implemented: false, variable: 'na_pe' },
    'senergy': { implemented: false, variable: 'na_pe' },
    'sptcr': { implemented: false, variable: 'na_pe' },
    'samt': { implemented: false, variable: 'na_pe' },
    'addmed': { implemented: false, variable: 'na_pe' },
    'cdate': { implemented: false, variable: 'na_pe' },
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
  const search = searchTerm.toLowerCase();
  const filteredMappings = currentMappings.filter(mapping =>
    mapping.taxsim.toLowerCase().includes(search) ||
    (mapping.policyengine || '').toLowerCase().includes(search) ||
    mapping.description.toLowerCase().includes(search)
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

  // Note: loading state is handled inline in Variable Mappings tab only,
  // so Installation & Usage and All Runners sections load immediately.

  // Note: error state is handled inline in Variable Mappings tab only,
  // so Installation & Usage and All Runners sections remain accessible.

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
              by TAXSIM35. It's a <strong>drop-in replacement</strong> — install
              with <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>pip install policyengine-taxsim</code> and
              swap <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>taxsim35</code> for <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>policyengine-taxsim</code>.
              Like TAXSIM35, this emulator <strong>runs entirely on your machine</strong>.
              Use the same CSV format you already know: provide household demographics,
              income, and deductions as inputs, and receive federal and state tax calculations as outputs.
            </div>
          </div>
        </section>

        {/* Section Tabs */}
        <section className="landing-section" style={{ paddingBottom: 0 }}>
          <div className="landing-section-inner">
            <div className="landing-tab-bar">
              {[
                { id: 'installation', label: 'Installation & Usage' },
                { id: 'options', label: 'All Runners & CLI' },
                { id: 'mappings', label: 'Variable Mappings' },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => setActiveSection(id)}
                  className={`landing-tab-button ${activeSection === id ? 'landing-tab-active' : ''}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Installation & Usage */}
        {activeSection === 'installation' && (
          <section className="landing-section">
            <div className="landing-section-inner">
              {/* Installation */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', marginBottom: '12px' }}>
                Installation
              </h3>
              <div style={{ maxWidth: '640px', marginBottom: '2rem' }}>
                {renderCodeBlock({
                  id: 'install-pip',
                  label: 'Terminal',
                  code: `pip install policyengine-taxsim`,
                })}
              </div>

              {/* Usage with language tabs */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', marginBottom: '12px' }}>
                Usage
              </h3>
              <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
                Same input format, same output variables. Just swap the command.
              </p>
              <div className="landing-lang-toggle">
                {Object.entries(LANG_LABELS).map(([id, label]) => (
                  <button
                    key={id}
                    className={`landing-lang-btn${activeUsageLang === id ? ' landing-lang-btn-active' : ''}`}
                    onClick={() => setActiveUsageLang(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: '16px' }}>
                {renderCodeBlock({
                  id: `usage-${activeUsageLang}`,
                  label: usageExamples[activeUsageLang].label,
                  language: usageExamples[activeUsageLang].language,
                  code: usageExamples[activeUsageLang].code,
                })}
              </div>

              {/* Language-specific extras */}
              {activeUsageLang === 'python' && (
                <div style={{ marginTop: '16px' }}>
                  {advancedExamples.python.map(renderCodeBlock)}
                </div>
              )}
              {activeUsageLang === 'r' && (
                <div style={{ marginTop: '16px' }}>
                  {advancedExamples.r.map(renderCodeBlock)}
                </div>
              )}
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
                Runs the official TAXSIM35 executable locally. Requires the TAXSIM binary
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
                  language: 'python',
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
                  language: 'python',
                  code: `runner = PolicyEngineRunner(df, disable_salt=True)
results = runner.run()`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">assume_w2_wages</code>
                  <span className="doc-option-type">bool, default False</span>
                </div>
                <p className="doc-option-description">
                  Sets <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>w2_wages_from_qualified_business</code> to
                  a large value so the W-2 wage cap in the QBID (Section 199A) calculation never binds.
                  This aligns PolicyEngine's output with TAXSIM's simplified S-Corp handling, which applies
                  a flat 20% deduction on qualified business income without enforcing the W-2/UBIA cap.
                </p>
                {renderCodeBlock({
                  id: 'option-w2-wages',
                  label: 'Example',
                  language: 'python',
                  code: `runner = PolicyEngineRunner(df, assume_w2_wages=True)
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
                  language: 'python',
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
                  language: 'python',
                  code: `runner = PolicyEngineRunner(df)
results = runner.run(show_progress=False)`
                })}
              </div>

              {/* CLI */}
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--darkest-blue)', margin: '32px 0 12px' }}>
                Command-Line Interface
              </h3>
              <p style={{ color: 'var(--dark-gray)', marginBottom: '16px', fontSize: '15px', lineHeight: '1.7' }}>
                The <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>policyengine-taxsim</code> CLI
                is a drop-in replacement for <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>taxsim35</code>.
                By default it reads from stdin and writes to stdout, just like TAXSIM35.
                Advanced subcommands are also available.
              </p>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim &lt; input.csv &gt; output.csv</code>
                </div>
                <p className="doc-option-description">
                  Drop-in replacement for <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>taxsim35</code>.
                  Reads TAXSIM-formatted CSV from stdin, writes results to stdout. Swap the command name and everything else stays the same.
                </p>
                {renderCodeBlock({
                  id: 'cli-stdin',
                  label: 'Terminal',
                  code: `policyengine-taxsim < input.csv > output.csv`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim policyengine</code>
                </div>
                <p className="doc-option-description">
                  Run PolicyEngine tax calculations with explicit input/output file paths.
                  Supports <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--disable-salt</code>,{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--assume-w2-wages</code>,{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--logs</code>, and{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--sample N</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-pe',
                  label: 'Terminal',
                  code: `policyengine-taxsim policyengine input.csv -o output.csv
policyengine-taxsim policyengine input.csv --disable-salt --assume-w2-wages --logs`
                })}
              </div>

              <div className="doc-option-card">
                <div className="doc-option-header">
                  <code className="doc-option-name">policyengine-taxsim taxsim</code>
                </div>
                <p className="doc-option-description">
                  Run the official TAXSIM35 executable on a TAXSIM input file.
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
                  Run both PolicyEngine and TAXSIM35 on the same input, then compare the
                  results. Outputs a comparison report with match rates and differences.
                  Supports <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--disable-salt</code>,{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--assume-w2-wages</code>,{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--logs</code>, and{' '}
                  <code style={{ background: 'var(--blue-98)', padding: '2px 6px', borderRadius: '4px', fontSize: '13px' }}>--sample N</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-compare',
                  label: 'Terminal',
                  code: `policyengine-taxsim compare input.csv --output-dir comparison_output --assume-w2-wages`
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
              {loading && (
                <LoadingSpinner
                  message="Loading configuration data..."
                  subMessage="Please wait while we load the variable mappings"
                />
              )}
              {error && (
                <div className="error-card" style={{ marginBottom: '24px' }}>
                  <h3 style={{ color: 'var(--dark-red)', marginBottom: '8px' }}>Failed to load variable mappings</h3>
                  <p style={{ color: 'var(--dark-gray)' }}>{error}</p>
                </div>
              )}
              {!loading && !error && <>
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
                TAXSIM35 provides. The mappings below show the standard TAXSIM
                inputs and outputs, but PolicyEngine supports hundreds of additional tax and
                benefit variables. See the{' '}
                <a
                  href="https://github.com/PolicyEngine/policyengine-us"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--blue-primary)', fontWeight: 600 }}
                >
                  PolicyEngine US variable definitions
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
              </>}
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
            <a
              href="https://taxsim.nber.org/taxsim35/"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-footer-card"
            >
              <FiExternalLink size={20} />
              <span>TAXSIM35 Official Docs</span>
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

  function renderVariablesWithDividers(sections) {
    const results = [];
    const addedSections = new Set();

    filteredMappings.forEach((mapping, index) => {
      for (const { key, codes, title, color } of sections) {
        if (!addedSections.has(key) && codes.includes(mapping.taxsim)) {
          results.push(
            <React.Fragment key={`divider-${key}`}>
              {createDivider(title, color)}
            </React.Fragment>
          );
          addedSections.add(key);
          break;
        }
      }
      results.push(renderVariableRow(mapping, index));
    });

    return results;
  }

  function renderInputVariables() {
    const { basicInputs, incomeInputs, businessIncomeInputs, expenseInputs } = INPUT_VARIABLE_CATEGORIES;
    return renderVariablesWithDividers([
      { key: 'basic', codes: basicInputs, title: 'Basic Inputs' },
      { key: 'income', codes: incomeInputs, title: 'Income Inputs', color: 'var(--teal-accent)' },
      { key: 'business', codes: businessIncomeInputs, title: 'Business Income', color: 'var(--dark-gray)' },
      { key: 'expense', codes: expenseInputs, title: 'Expense & Deduction Inputs' },
    ]);
  }

  function renderOutputVariables() {
    const { basicOutputs, taxOutputs, agiOutputs, deductionOutputs, taxableIncomeOutputs, creditOutputs, amtOutputs, stateOutputs, additionalOutputs } = OUTPUT_VARIABLE_CATEGORIES;
    return renderVariablesWithDividers([
      { key: 'basic', codes: basicOutputs, title: 'Basic Outputs' },
      { key: 'tax', codes: taxOutputs, title: 'Primary Tax Calculations' },
      { key: 'agi', codes: agiOutputs, title: 'Adjusted Gross Income', color: 'var(--teal-accent)' },
      { key: 'deduction', codes: deductionOutputs, title: 'Deductions & Exemptions', color: 'var(--dark-gray)' },
      { key: 'taxable', codes: taxableIncomeOutputs, title: 'Taxable Income & Tax Calculations' },
      { key: 'credit', codes: creditOutputs, title: 'Tax Credits', color: 'var(--teal-accent)' },
      { key: 'amt', codes: amtOutputs, title: 'Alternative Minimum Tax', color: 'var(--dark-gray)' },
      { key: 'state', codes: stateOutputs, title: 'State-Specific Calculations' },
      { key: 'additional', codes: additionalOutputs, title: 'Additional Outputs', color: 'var(--teal-accent)' },
    ]);
  }
};

export default Documentation;