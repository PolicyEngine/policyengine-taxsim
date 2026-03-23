'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  IconExternalLink,
  IconCheck,
  IconX,
  IconCopy,
  IconHome,
  IconChartBar,
  IconBrandGithub,
  IconBook,
  IconSearch,
} from '@tabler/icons-react';
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

const NON_LINKABLE = ['na_pe', 'taxsimid', 'get_year', 'marginal_rate_computed'];
const ADJUSTED_VARIABLES = ['federal_marginal_tax_rate', 'state_marginal_tax_rate', 'fica_marginal_tax_rate'];

const LANG_LABELS = {
  cli: 'CLI',
  python: 'Python',
  r: 'R',
  stata: 'Stata',
  sas: 'SAS',
  julia: 'Julia',
};

const DocumentationContent = () => {
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
  const [installOs, setInstallOs] = useState('mac');

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
uv pip install policyengine-us==1.555.0`
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
    <div key={block.id} className="bg-secondary-900 rounded-lg overflow-hidden mb-3">
      <div className="bg-secondary-800 px-4 py-2 flex justify-between items-center">
        <span className="text-xs font-medium text-gray-400">{block.label}</span>
        <button
          onClick={() => handleCopy(block.code, block.id)}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition"
          title="Copy to clipboard"
        >
          {copiedBlock === block.id ? (
            <>
              <IconCheck size={14} />
              <span>Copied</span>
            </>
          ) : (
            <>
              <IconCopy size={14} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed text-gray-100">
        <code>{highlightCode(block.code, block.language || 'cli')}</code>
      </pre>
    </div>
  );

  // Shared function to create section dividers
  const createDivider = (title, color = 'var(--color-blue-500)') => (
    <div
      className="text-xs font-bold uppercase tracking-wider text-gray-500 py-2 px-4 mt-4 mb-1 border-l-4"
      style={{ borderLeftColor: color }}
    >
      {title}
    </div>
  );

  // Shared function to render variable rows
  const renderVariableRow = (mapping, index) => (
    <div key={`var-${index}`} className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-100 hover:bg-gray-50/50 transition">
      <div className="flex items-center gap-2 min-w-0">
        <code className="text-xs font-semibold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">{mapping.taxsim}</code>
        <span className="text-gray-400 text-xs">&rarr;</span>
        <span className="text-xs text-gray-700">
          {activeTab === 'output' ? renderOutputPolicyEngineCell(mapping) : renderInputPolicyEngineCell(mapping)}
        </span>
      </div>
      <p className="flex-1 text-xs text-gray-500 min-w-[200px]">{mapping.description}</p>
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
        mapping.implemented
          ? 'bg-success/10 text-success'
          : 'bg-gray-100 text-gray-500'
      }`}>
        {mapping.implemented ? <><IconCheck size={12} /> Implemented</> : <><IconX size={12} /> Not Implemented</>}
      </span>
    </div>
  );

  const VariableLink = ({ href, label, fontSize }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center text-primary-600 hover:text-primary-800 hover:underline font-medium"
      style={fontSize ? { fontSize } : undefined}
    >
      {label}
      <IconExternalLink size={fontSize ? 9 : 10} className="ml-1" />
    </a>
  );

  function buildGithubUrl(varName) {
    return `https://github.com/PolicyEngine/policyengine-us/blob/master/policyengine_us/variables/${getVariablePath(varName)}`;
  }

  const renderOutputPolicyEngineCell = (mapping) => {
    const multipleVars = getMultipleVariables(mapping.taxsim);

    if (multipleVars && mapping.implemented) {
      return (
        <div className="flex flex-col gap-1">
          {multipleVars.map((varName, index) => (
            <VariableLink key={index} href={buildGithubUrl(varName)} label={varName} fontSize="11px" />
          ))}
        </div>
      );
    }

    if (mapping.implemented && mapping.policyengine && !NON_LINKABLE.includes(mapping.policyengine)) {
      const isAdjusted = ADJUSTED_VARIABLES.includes(mapping.policyengine);
      return (
        <span>
          <VariableLink href={buildGithubUrl(mapping.policyengine)} label={mapping.policyengine} />
          {isAdjusted && <span className="text-blue-600 font-bold" title="Adjusted to match TAXSIM methodology"> *</span>}
        </span>
      );
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

    // Marginal rates: based on PE variables, adjusted to match TAXSIM methodology
    'frate': { implemented: true, variable: 'federal_marginal_tax_rate' },
    'srate': { implemented: true, variable: 'state_marginal_tax_rate' },
    'ficar': { implemented: true, variable: 'fica_marginal_tax_rate' },

    // Not implemented: variable = 'na_pe' means not available in PolicyEngine
    'fica': { implemented: false, variable: 'na_pe' },
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
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-14">
        <div className="flex items-center gap-2 text-gray-900 font-semibold text-lg">
          <IconBook size={20} className="text-primary-600" />
          Documentation
        </div>
        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
          >
            <IconHome size={16} />
            Home
          </Link>
          <Link
            href="/run"
            className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
          >
            Web Runner
          </Link>
          <span className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium text-primary-600 bg-primary-50">
            <IconBook size={16} />
            Documentation
          </span>
          <a
            href="https://github.com/PolicyEngine/policyengine-taxsim"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition"
          >
            <IconBrandGithub size={16} />
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {renderNav()}

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 pb-12">
        {/* Intro blurb */}
        <section className="pt-8">
          <div className="max-w-3xl mx-auto text-center py-8 text-gray-600 leading-relaxed text-[15px]">
            The PolicyEngine TAXSIM Emulator supports <strong className="text-gray-900">all input and output variables</strong> provided
            by TAXSIM35. It&apos;s a <strong className="text-gray-900">drop-in replacement</strong> &mdash; install
            with <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">uv tool install policyengine-taxsim</code> and
            swap <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">taxsim35</code> for <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">policyengine-taxsim</code>.
            Like TAXSIM35, this emulator <strong className="text-gray-900">runs entirely on your machine</strong>.
            Use the same CSV format you already know: provide household demographics,
            income, and deductions as inputs, and receive federal and state tax calculations as outputs.
          </div>
        </section>

        {/* Section Tabs */}
        <section className="pb-0">
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg max-w-2xl mx-auto mb-8">
            {[
              { id: 'installation', label: 'Installation & Usage' },
              { id: 'options', label: 'All Runners & CLI' },
              { id: 'mappings', label: 'Variable Mappings' },
            ].map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={`flex-1 px-4 py-2.5 rounded-md text-sm font-medium transition ${
                  activeSection === id
                    ? 'bg-white shadow-sm text-primary-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* Installation & Usage */}
        {activeSection === 'installation' && (
          <section className="space-y-6">
            {/* Installation */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                Installation
              </h3>
              <div className={installOs === 'win' ? 'max-w-3xl' : 'max-w-[640px]'}>
                <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit mb-4">
                  {[
                    { id: 'mac', label: 'macOS/Linux' },
                    { id: 'win', label: 'Windows' },
                  ].map(({ id, label }) => (
                    <button
                      key={id}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                        installOs === id
                          ? 'bg-white shadow-sm text-primary-600'
                          : 'text-gray-500 hover:text-gray-700'
                      }`}
                      onClick={() => setInstallOs(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {renderCodeBlock({
                  id: `install-${installOs}`,
                  label: 'Terminal',
                  code: installOs === 'mac'
                    ? `# Install uv package manager (if you don't have it)\ncurl -LsSf https://astral.sh/uv/install.sh | sh\n\n# Install policyengine-taxsim\nuv tool install policyengine-taxsim`
                    : `# Install uv package manager (if you don't have it)\npowershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"\n\n# Install policyengine-taxsim\nuv tool install policyengine-taxsim`,
                })}
                <p className="text-sm text-gray-400 mt-3">
                  If the command is not found, open Terminal and run <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">uv tool dir --bin</code>, then replace <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">policyengine-taxsim</code> with the full path shown (e.g. <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">/Users/you/.local/bin/policyengine-taxsim</code>).
                </p>
              </div>
            </div>

            {/* Upgrading & Version Pinning */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                Upgrading
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                To upgrade to the latest version:
              </p>
              {renderCodeBlock({
                id: 'upgrade',
                label: 'Terminal',
                code: 'uv tool upgrade policyengine-taxsim',
              })}
              <h3 className="text-lg font-bold text-gray-900 mb-3 mt-6">
                Version pinning
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                For reproducible results, pin to a specific version:
              </p>
              {renderCodeBlock({
                id: 'version-pin',
                label: 'Terminal',
                code: '# Install a specific version of policyengine-taxsim\nuv tool install policyengine-taxsim==2.13.0\n\n# Pin the underlying tax model for reproducible results\nuv tool install policyengine-taxsim --with policyengine-us==1.555.0',
              })}
            </div>

            {/* Usage with language tabs */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                Usage
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                Same input format, same output variables. Just swap the command.
              </p>
              <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit mb-4">
                {Object.entries(LANG_LABELS).map(([id, label]) => (
                  <button
                    key={id}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                      activeUsageLang === id
                        ? 'bg-white shadow-sm text-primary-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setActiveUsageLang(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div>
                {renderCodeBlock({
                  id: `usage-${activeUsageLang}`,
                  label: usageExamples[activeUsageLang].label,
                  language: usageExamples[activeUsageLang].language,
                  code: usageExamples[activeUsageLang].code,
                })}
              </div>
              {['stata', 'sas', 'julia'].includes(activeUsageLang) && (
                <p className="text-sm text-gray-400 mt-3">
                  If the command is not found, open Terminal and run <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">uv tool dir --bin</code>, then replace <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">policyengine-taxsim</code> with the full path shown (e.g. <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">/Users/you/.local/bin/policyengine-taxsim</code>).
                </p>
              )}

              {/* Language-specific extras */}
              {activeUsageLang === 'python' && (
                <div className="mt-4">
                  {advancedExamples.python.map(renderCodeBlock)}
                </div>
              )}
              {activeUsageLang === 'r' && (
                <div className="mt-4">
                  {advancedExamples.r.map(renderCodeBlock)}
                </div>
              )}
            </div>
          </section>
        )}

        {/* All Runners & CLI */}
        {activeSection === 'options' && (
          <section className="space-y-6">

            {/* TaxsimRunner */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                TaxsimRunner
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                Runs the official TAXSIM35 executable locally. Requires the TAXSIM binary
                (auto-detected on macOS, Linux, and Windows). Useful for generating reference
                outputs to compare against PolicyEngine.
              </p>
              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">TaxsimRunner</code>
                  <span className="text-xs text-gray-400">input_df, taxsim_path=None</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Takes a TAXSIM-formatted DataFrame and an optional path to the TAXSIM executable.
                  If <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">taxsim_path</code> is
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
            </div>

            {/* PolicyEngineRunner advanced options */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                PolicyEngineRunner &mdash; Advanced options
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                Beyond the basic usage shown in Installation & Usage, <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">PolicyEngineRunner</code> accepts
                additional options for policy simulations and debugging.
                These options are currently available in the Python API only.
              </p>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">disable_salt</code>
                  <span className="text-xs text-gray-400">bool, default False</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Sets the State and Local Tax (SALT) deduction to zero for all records.
                  Useful for modeling the impact of SALT cap policies &mdash; for example,
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

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">assume_w2_wages</code>
                  <span className="text-xs text-gray-400">bool, default False</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Sets <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">w2_wages_from_qualified_business</code> to
                  a large value so the W-2 wage cap in the QBID (Section 199A) calculation never binds.
                  This aligns PolicyEngine&apos;s output with TAXSIM&apos;s simplified S-Corp handling, which applies
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

              <div className="bg-blue-50 rounded-lg p-5 mb-4 border border-blue-200">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">Marginal tax rates (frate, srate, ficar)</code>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Marginal rates are based on PolicyEngine&apos;s <code className="bg-white px-1.5 py-0.5 rounded text-[13px]">federal_marginal_tax_rate</code>,{' '}
                  <code className="bg-white px-1.5 py-0.5 rounded text-[13px]">state_marginal_tax_rate</code>, and{' '}
                  <code className="bg-white px-1.5 py-0.5 rounded text-[13px]">fica_marginal_tax_rate</code> variables,
                  with adjustments to match TAXSIM-35 methodology:
                </p>
                <ul className="text-sm text-gray-600 space-y-1 ml-4 list-disc mb-3">
                  <li>Perturbs <strong>employment income (wages) only</strong> &mdash; self-employment income is not perturbed</li>
                  <li>Splits the perturbation between primary and spouse earners <strong>proportionally to their wage share</strong> (weighted average earnings, matching TAXSIM <code className="bg-white px-1.5 py-0.5 rounded text-[13px]">mtr=11</code>)</li>
                  <li>Measures the change in each tax component independently: federal income tax (<code className="bg-white px-1.5 py-0.5 rounded text-[13px]">frate</code>), state income tax (<code className="bg-white px-1.5 py-0.5 rounded text-[13px]">srate</code>), and employee payroll tax (<code className="bg-white px-1.5 py-0.5 rounded text-[13px]">ficar</code>)</li>
                  <li>Returns rates as <strong>percentages</strong> (e.g., 22.0 for 22%)</li>
                </ul>
                <p className="text-sm text-gray-500">
                  <strong>Note:</strong> PolicyEngine&apos;s upstream MTR variables perturb all earned income (including self-employment) and use a different delta.
                  The emulator adjusts the computation to match TAXSIM&apos;s wage-only perturbation and uses a $100 delta
                  (vs TAXSIM&apos;s $0.01 with Fortran float64) for numerical stability with PolicyEngine&apos;s float32 internals.
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">logs</code>
                  <span className="text-xs text-gray-400">bool, default False</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">
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

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">show_progress</code>
                  <span className="text-xs text-gray-400">bool, default True (passed to .run())</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Controls whether progress bars are displayed during calculation.
                  Set to <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">False</code> for
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
            </div>

            {/* CLI */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <h3 className="text-lg font-bold text-gray-900 mb-3">
                Command-line interface
              </h3>
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
                The <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">policyengine-taxsim</code> CLI
                is a drop-in replacement for <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">taxsim35</code>.
                By default it reads from stdin and writes to stdout, just like TAXSIM35.
                Advanced subcommands are also available.
              </p>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">policyengine-taxsim &lt; input.csv &gt; output.csv</code>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Drop-in replacement for <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">taxsim35</code>.
                  Reads TAXSIM-formatted CSV from stdin, writes results to stdout. Swap the command name and everything else stays the same.
                </p>
                {renderCodeBlock({
                  id: 'cli-stdin',
                  label: 'Terminal',
                  code: `policyengine-taxsim < input.csv > output.csv`
                })}
              </div>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">policyengine-taxsim policyengine</code>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Run PolicyEngine tax calculations with explicit input/output file paths.
                  Supports <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--disable-salt</code>,{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--assume-w2-wages</code>,{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--logs</code>, and{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--sample N</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-pe',
                  label: 'Terminal',
                  code: `policyengine-taxsim policyengine input.csv -o output.csv
policyengine-taxsim policyengine input.csv --disable-salt --assume-w2-wages --logs`
                })}
              </div>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">policyengine-taxsim taxsim</code>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Run the official TAXSIM35 executable on a TAXSIM input file.
                  Optionally specify a custom path to the TAXSIM binary with{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--taxsim-path</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-taxsim',
                  label: 'Terminal',
                  code: `policyengine-taxsim taxsim input.csv -o taxsim_output.csv`
                })}
              </div>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">policyengine-taxsim compare</code>
                </div>
                <p className="text-sm text-gray-500 mb-3">
                  Run both PolicyEngine and TAXSIM35 on the same input, then compare the
                  results. Outputs a comparison report with match rates and differences.
                  Supports <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--disable-salt</code>,{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--assume-w2-wages</code>,{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--logs</code>, and{' '}
                  <code className="bg-blue-50 px-1.5 py-0.5 rounded text-[13px]">--sample N</code>.
                </p>
                {renderCodeBlock({
                  id: 'cli-compare',
                  label: 'Terminal',
                  code: `policyengine-taxsim compare input.csv --output-dir comparison_output --assume-w2-wages`
                })}
              </div>

              <div className="bg-gray-50 rounded-lg p-5 mb-4">
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-sm font-semibold text-gray-900">policyengine-taxsim sample-data</code>
                </div>
                <p className="text-sm text-gray-500 mb-3">
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
          <section>
            {loading && (
              <LoadingSpinner
                message="Loading configuration data..."
                subMessage="Please wait while we load the variable mappings"
              />
            )}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
                <h3 className="text-red-800 font-semibold mb-2">Failed to load variable mappings</h3>
                <p className="text-gray-600">{error}</p>
              </div>
            )}
            {!loading && !error && <>
            <div className="mb-6">
              <p className="text-gray-500 mb-4 text-[15px] leading-relaxed">
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
                className="inline-flex items-center gap-1.5 text-primary-600 hover:text-primary-800 font-medium text-sm"
              >
                TAXSIM Official Documentation <IconExternalLink size={14} />
              </a>
            </div>

            <div className="max-w-3xl mx-auto text-center py-4 text-gray-600 leading-relaxed text-sm mb-6 bg-blue-50/50 rounded-lg px-6">
              <strong className="text-gray-900">Note on extended coverage:</strong> Because this emulator is powered by
              PolicyEngine&apos;s microsimulation model, it can calculate variables beyond what
              TAXSIM35 provides. The mappings below show the standard TAXSIM
              inputs and outputs, but PolicyEngine supports hundreds of additional tax and
              benefit variables. See the{' '}
              <a
                href="https://github.com/PolicyEngine/policyengine-us"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 font-semibold hover:underline"
              >
                PolicyEngine US variable definitions
              </a>{' '}
              for the full list.
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg max-w-md mx-auto mb-4">
              <button
                onClick={() => setActiveTab('input')}
                className={`flex-1 px-4 py-2.5 rounded-md text-sm font-medium transition ${
                  activeTab === 'input'
                    ? 'bg-white shadow-sm text-primary-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Input Variables
              </button>
              <button
                onClick={() => setActiveTab('output')}
                className={`flex-1 px-4 py-2.5 rounded-md text-sm font-medium transition ${
                  activeTab === 'output'
                    ? 'bg-white shadow-sm text-primary-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Output Variables
              </button>
            </div>

            {/* Search Bar */}
            <div className="mb-6 relative">
              <IconSearch size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search variables..."
                className="w-full px-4 py-3 pl-10 rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 text-sm"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            {/* Variable Mappings */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              {activeTab === 'input' ? renderInputVariables() : renderOutputVariables()}
            </div>
            {activeTab === 'output' && (
              <p className="text-xs text-gray-500 mt-2 ml-1">
                <span className="text-blue-600 font-bold">*</span> Adjusted to match TAXSIM methodology: perturbs employment income (wages) only, splits perturbation proportionally between spouses, and uses a $100 delta for numerical stability with PolicyEngine&apos;s float32 internals.
              </p>
            )}
            </>}
          </section>
        )}

      </main>

      {/* Footer -- matches landing page */}
      <footer className="bg-gray-900 text-white mt-16">
        <div className="max-w-5xl mx-auto px-6 py-12">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            <a
              href="https://github.com/PolicyEngine/policyengine-taxsim"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 p-4 rounded-lg bg-gray-800 hover:bg-gray-700 transition group"
            >
              <IconBrandGithub size={20} className="text-gray-400 group-hover:text-white transition" />
              <span className="text-sm font-medium">GitHub Repository</span>
              <IconExternalLink size={14} className="ml-auto text-gray-500 group-hover:text-gray-300 transition" />
            </a>
            <a
              href="https://taxsim.nber.org/taxsim35/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 p-4 rounded-lg bg-gray-800 hover:bg-gray-700 transition group"
            >
              <IconExternalLink size={20} className="text-gray-400 group-hover:text-white transition" />
              <span className="text-sm font-medium">TAXSIM35 Official Docs</span>
              <IconExternalLink size={14} className="ml-auto text-gray-500 group-hover:text-gray-300 transition" />
            </a>
          </div>
          <div className="text-center text-sm text-gray-400">
            Built by <a href="https://policyengine.org" target="_blank" rel="noopener noreferrer" className="text-gray-300 hover:text-white transition">PolicyEngine</a>
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
      { key: 'income', codes: incomeInputs, title: 'Income Inputs', color: 'var(--color-primary-500)' },
      { key: 'business', codes: businessIncomeInputs, title: 'Business Income', color: 'var(--color-gray-700)' },
      { key: 'expense', codes: expenseInputs, title: 'Expense & Deduction Inputs' },
    ]);
  }

  function renderOutputVariables() {
    const { basicOutputs, taxOutputs, agiOutputs, deductionOutputs, taxableIncomeOutputs, creditOutputs, amtOutputs, stateOutputs, additionalOutputs } = OUTPUT_VARIABLE_CATEGORIES;
    return renderVariablesWithDividers([
      { key: 'basic', codes: basicOutputs, title: 'Basic Outputs' },
      { key: 'tax', codes: taxOutputs, title: 'Primary Tax Calculations' },
      { key: 'agi', codes: agiOutputs, title: 'Adjusted Gross Income', color: 'var(--color-primary-500)' },
      { key: 'deduction', codes: deductionOutputs, title: 'Deductions & Exemptions', color: 'var(--color-gray-700)' },
      { key: 'taxable', codes: taxableIncomeOutputs, title: 'Taxable Income & Tax Calculations' },
      { key: 'credit', codes: creditOutputs, title: 'Tax Credits', color: 'var(--color-primary-500)' },
      { key: 'amt', codes: amtOutputs, title: 'Alternative Minimum Tax', color: 'var(--color-gray-700)' },
      { key: 'state', codes: stateOutputs, title: 'State-Specific Calculations' },
      { key: 'additional', codes: additionalOutputs, title: 'Additional Outputs', color: 'var(--color-primary-500)' },
    ]);
  }
};

export default DocumentationContent;
