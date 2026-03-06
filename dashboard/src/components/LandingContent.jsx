'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  IconBrandGithub,
  IconExternalLink,
  IconArrowRight,
  IconChartBar,
  IconShield,
  IconCode,
  IconMap,
  IconCopy,
  IconCheck,
  IconClock,
} from '@tabler/icons-react';
import { highlightCode } from '../utils/codeHighlight';

const CodeBlock = ({ label, code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  return (
    <div className="bg-secondary-900 rounded-lg overflow-hidden">
      <div className="bg-secondary-800 px-4 py-2 flex justify-between items-center">
        <span className="text-gray-400 text-sm font-mono">{label}</span>
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 text-gray-400 hover:text-white text-sm transition"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <IconCheck size={14} /> Copied
            </>
          ) : (
            <>
              <IconCopy size={14} /> Copy
            </>
          )}
        </button>
      </div>
      <pre className="p-4 text-sm leading-relaxed overflow-x-auto text-gray-100 font-mono">
        <code>{highlightCode(code, language)}</code>
      </pre>
    </div>
  );
};

const LANG_TABS = [
  { id: 'cli', label: 'CLI' },
  { id: 'python', label: 'Python' },
  { id: 'r', label: 'R' },
  { id: 'stata', label: 'Stata' },
  { id: 'sas', label: 'SAS' },
  { id: 'julia', label: 'Julia' },
];

const COMPARISON_EXAMPLES = {
  cli: {
    before: {
      label: 'Shell',
      code: 'taxsim35 < input.csv > output.csv',
      language: 'cli',
    },
    after: {
      label: 'Shell',
      code: 'policyengine-taxsim < input.csv > output.csv',
      language: 'cli',
    },
  },
  python: {
    before: {
      label: 'Python',
      code: 'import subprocess\nresult = subprocess.run(\n  "taxsim35 < input.csv > output.csv",\n  shell=True\n)',
      language: 'python',
    },
    after: {
      label: 'Python',
      code: 'from policyengine_taxsim.runners import PolicyEngineRunner\nimport pandas as pd\n\ndf = pd.read_csv("input.csv")\nresult = PolicyEngineRunner(df).run()',
      language: 'python',
    },
  },
  r: {
    before: {
      label: 'R',
      code: 'library(usincometaxes)\nresult <- taxsim_calculate_taxes(input)',
      language: 'r',
    },
    after: {
      label: 'R',
      code: 'library(policyenginetaxsim)\nresult <- policyengine_calculate_taxes(input)',
      language: 'r',
    },
  },
  stata: {
    before: {
      label: 'Stata',
      code: 'taxsimlocal35, replace',
      language: 'stata',
    },
    after: {
      label: 'Stata',
      code: 'export delimited using "input.csv", replace\nshell policyengine-taxsim < input.csv > output.csv\nimport delimited using "output.csv", clear',
      language: 'stata',
    },
  },
  sas: {
    before: {
      label: 'SAS',
      code: '%let rc = %sysfunc(system(\n  taxsim35 < input.csv > output.csv\n));',
      language: 'cli',
    },
    after: {
      label: 'SAS',
      code: '%let rc = %sysfunc(system(\n  policyengine-taxsim < input.csv > output.csv\n));',
      language: 'cli',
    },
  },
  julia: {
    before: {
      label: 'Julia',
      code: 'run(pipeline(`taxsim35`,\n  stdin="input.csv",\n  stdout="output.csv"\n))',
      language: 'cli',
    },
    after: {
      label: 'Julia',
      code: 'run(pipeline(`policyengine-taxsim`,\n  stdin="input.csv",\n  stdout="output.csv"\n))',
      language: 'cli',
    },
  },
};

const OS_TABS = [
  { id: 'mac', label: 'macOS/Linux' },
  { id: 'win', label: 'Windows' },
];

const INSTALL_COMMANDS = {
  mac: "# Install uv package manager (if you don't have it)\ncurl -LsSf https://astral.sh/uv/install.sh | sh\n\n# Install policyengine-taxsim\nuv tool install policyengine-taxsim",
  win: "# Install uv package manager (if you don't have it)\npowershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n\n# Install policyengine-taxsim\nuv tool install policyengine-taxsim",
};

const LandingContent = () => {
  const [lang, setLang] = useState('cli');
  const [os, setOs] = useState('mac');

  const example = COMPARISON_EXAMPLES[lang];

  return (
    <div className="min-h-screen bg-white">
      {/* Hero section */}
      <section className="bg-gradient-to-br from-white to-gray-100 py-20 px-6 text-center">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl md:text-5xl font-bold text-secondary-900 mb-6">
            The next chapter of TAXSIM
          </h1>
          <p className="text-lg md:text-xl text-gray-500 leading-relaxed">
            An open-source, drop-in replacement for TAXSIM35. Same interface,
            same inputs, same outputs — powered by PolicyEngine&apos;s
            microsimulation engine.
          </p>
        </div>
      </section>

      {/* Installation */}
      <section className="py-16 px-6 max-w-5xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-secondary-900 text-center mb-8">
          Installation
        </h2>
        <div className={`${os === 'win' ? 'max-w-3xl' : 'max-w-[640px]'} mx-auto`}>
          <div className="flex flex-wrap justify-center gap-2 mb-4">
            {OS_TABS.map(({ id, label }) => (
              <button
                key={id}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  os === id
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-500 hover:bg-gray-100'
                }`}
                onClick={() => setOs(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <CodeBlock
            label="Terminal"
            code={INSTALL_COMMANDS[os]}
            language="cli"
          />
        </div>
      </section>

      {/* Get started */}
      <section className="py-16 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-secondary-900 text-center mb-4">
            Get started
          </h2>
          <p className="text-gray-500 text-center text-lg mb-8 max-w-2xl mx-auto">
            Same input format, same output variables. Just swap the command.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            {LANG_TABS.map(({ id, label }) => (
              <button
                key={id}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  lang === id
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-500 hover:bg-gray-100'
                }`}
                onClick={() => setLang(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
                TAXSIM35 (before)
              </h3>
              <CodeBlock
                label={example.before.label}
                code={example.before.code}
                language={example.before.language}
              />
            </div>
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-primary-500 mb-3">
                PolicyEngine TAXSIM (after)
              </h3>
              <CodeBlock
                label={example.after.label}
                code={example.after.code}
                language={example.after.language}
              />
            </div>
          </div>
          {['stata', 'sas', 'julia'].includes(lang) && (
            <p className="text-sm text-gray-400 mt-6 text-center">
              If the command is not found, open Terminal and run <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">uv tool dir --bin</code>, then replace <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">policyengine-taxsim</code> with the full path shown (e.g. <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">/Users/you/.local/bin/policyengine-taxsim</code>).
            </p>
          )}
        </div>
      </section>

      {/* Powered by PolicyEngine */}
      <section className="py-16 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-secondary-900 text-center mb-4">
            Powered by PolicyEngine
          </h2>
          <p className="text-gray-500 text-center text-lg mb-10 max-w-3xl mx-auto">
            PolicyEngine and TAXSIM have been cross-validated against each other
            since 2021, comparing results across thousands of CPS households.
            That work led to a formal partnership with NBER.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition">
              <div className="w-12 h-12 rounded-lg bg-primary-400 flex items-center justify-center mb-4">
                <IconCode color="white" size={24} />
              </div>
              <h3 className="text-lg font-semibold text-secondary-900 mb-2">
                Fully open source
              </h3>
              <p className="text-gray-500 leading-relaxed">
                All code — the TAXSIM emulator and the PolicyEngine engine it
                runs on — is open source on GitHub. Inspect every calculation.
              </p>
            </div>
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition">
              <div className="w-12 h-12 rounded-lg bg-primary-800 flex items-center justify-center mb-4">
                <IconMap color="white" size={24} />
              </div>
              <h3 className="text-lg font-semibold text-secondary-900 mb-2">
                Drop-in compatible
              </h3>
              <p className="text-gray-500 leading-relaxed">
                Same stdin/stdout interface, same input variables, same output
                format. Just swap <code className="text-primary-600 bg-gray-100 px-1.5 py-0.5 rounded text-sm">taxsim35</code> for{' '}
                <code className="text-primary-600 bg-gray-100 px-1.5 py-0.5 rounded text-sm">policyengine-taxsim</code>.
              </p>
            </div>
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition">
              <div className="w-12 h-12 rounded-lg bg-primary-500 flex items-center justify-center mb-4">
                <IconClock color="white" size={24} />
              </div>
              <h3 className="text-lg font-semibold text-secondary-900 mb-2">
                Full historical and future coverage
              </h3>
              <p className="text-gray-500 leading-relaxed">
                Automatic year-stitching routes 2021+ to PolicyEngine and
                earlier years to TAXSIM35, covering the 1960s through future
                scheduled law changes in a single command.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Validated by leading institutions */}
      <section className="py-16 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-secondary-900 text-center mb-10">
            Validated by leading institutions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center gap-3 mb-4">
                <IconShield size={20} className="text-primary-500" />
                <h3 className="text-lg font-semibold text-secondary-900">
                  NBER partnership
                </h3>
              </div>
              <p className="text-gray-500 leading-relaxed mb-4">
                Built under a{' '}
                <a
                  href="https://drive.google.com/file/d/1V5TJk7C01CLYP_FXUZTmHEdLk-WCV4WN/view?usp=sharing"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-500 hover:text-primary-600 underline"
                >
                  memorandum of understanding
                </a>{' '}
                with the National Bureau of Economic Research and TAXSIM creator
                Daniel Feenberg.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-nber-mou-taxsim"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-primary-500 hover:text-primary-600 font-medium transition"
              >
                Read more <IconArrowRight size={14} />
              </a>
            </div>
            <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
              <div className="flex items-center gap-3 mb-4">
                <IconShield size={20} className="text-primary-400" />
                <h3 className="text-lg font-semibold text-secondary-900">
                  Federal Reserve Bank of Atlanta
                </h3>
              </div>
              <p className="text-gray-500 leading-relaxed mb-4">
                Three-way validation with the Atlanta Fed&apos;s{' '}
                <a
                  href="https://drive.google.com/file/d/1ye8BQo6gXVWl50F1ht6UzB9HsdrfpeOQ/view"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-500 hover:text-primary-600 underline"
                >
                  Policy Rules Database
                </a>{' '}
                — cross-checking PolicyEngine, TAXSIM, and the Fed&apos;s
                models.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-atlanta-fed-mou-prd"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-primary-500 hover:text-primary-600 font-medium transition"
              >
                Read more <IconArrowRight size={14} />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Beyond TAXSIM */}
      <section className="py-16 px-6 max-w-5xl mx-auto">
        <h2 className="text-2xl md:text-3xl font-bold text-secondary-900 text-center mb-4">
          Beyond TAXSIM
        </h2>
        <p className="text-gray-500 text-center text-lg mb-10 max-w-3xl mx-auto">
          TAXSIM covers federal and state income taxes. PolicyEngine goes
          further — benefit programs, payroll taxes, detailed credits, and full
          microsimulation on representative survey data.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition">
            <div className="w-12 h-12 rounded-lg bg-primary-500 flex items-center justify-center mb-4">
              <IconChartBar color="white" size={24} />
            </div>
            <h3 className="text-lg font-semibold text-secondary-900 mb-2">
              Microsimulation
            </h3>
            <p className="text-gray-500 leading-relaxed">
              Estimate the budgetary and distributional impact of policy reforms
              across the full US population using PolicyEngine&apos;s{' '}
              <a
                href="https://policyengine.org/us/model"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-500 hover:text-primary-600 underline"
              >
                Enhanced CPS
              </a>
              , which integrates and calibrates multiple survey datasets.
            </p>
          </div>
          <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition">
            <div className="w-12 h-12 rounded-lg bg-primary-400 flex items-center justify-center mb-4">
              <IconShield color="white" size={24} />
            </div>
            <h3 className="text-lg font-semibold text-secondary-900 mb-2">
              Benefits and taxes
            </h3>
            <p className="text-gray-500 leading-relaxed">
              SNAP, SSI, Medicaid, CHIP, ACA marketplace subsidies, TANF,
              housing vouchers, WIC, EITC, CTC, and hundreds more federal and
              state programs — all in one model.
            </p>
          </div>
        </div>
        <div className="text-center mt-8">
          <a
            href="https://policyengine.org"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-6 py-3 rounded-lg bg-primary-500 text-white font-semibold hover:bg-primary-600 transition"
          >
            Explore PolicyEngine
            <IconArrowRight className="ml-2" size={18} />
          </a>
        </div>
      </section>

      {/* Documentation CTA */}
      <section className="py-16 px-6 bg-gray-50">
        <div className="max-w-5xl mx-auto text-center">
          <Link
            href="/documentation"
            className="inline-flex items-center px-6 py-3 rounded-lg bg-primary-500 text-white font-semibold hover:bg-primary-600 transition"
          >
            Read the full documentation
            <IconArrowRight className="ml-2" size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-secondary-900 text-white py-12 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            <a
              href="https://github.com/PolicyEngine/policyengine-taxsim"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 bg-white/10 rounded-lg px-5 py-4 hover:bg-white/20 transition"
            >
              <IconBrandGithub size={20} />
              <span className="flex-1">GitHub repository</span>
              <IconExternalLink size={14} className="text-gray-400" />
            </a>
            <a
              href="https://taxsim.nber.org/taxsim35/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 bg-white/10 rounded-lg px-5 py-4 hover:bg-white/20 transition"
            >
              <IconExternalLink size={20} />
              <span className="flex-1">TAXSIM35 official docs</span>
              <IconExternalLink size={14} className="text-gray-400" />
            </a>
          </div>
          <div className="text-center text-gray-400 text-sm">
            Built by{' '}
            <a
              href="https://policyengine.org"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white hover:text-primary-400 underline transition"
            >
              PolicyEngine
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingContent;
