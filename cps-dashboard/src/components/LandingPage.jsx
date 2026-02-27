import React, { useState } from 'react';
import { FiGithub, FiExternalLink, FiArrowRight, FiBarChart2, FiShield, FiCode, FiMap, FiCopy, FiCheck, FiClock } from 'react-icons/fi';
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
    <div className="landing-code-block">
      <div className="landing-code-header">
        <span className="landing-code-label">{label}</span>
        <button onClick={handleCopy} className="landing-copy-button" title="Copy to clipboard">
          {copied ? <><FiCheck size={14} /> Copied</> : <><FiCopy size={14} /> Copy</>}
        </button>
      </div>
      <pre className="landing-code-content"><code>{highlightCode(code, language)}</code></pre>
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
    before: { label: 'Shell', code: 'taxsim35 < input.csv > output.csv', language: 'cli' },
    after: { label: 'Shell', code: 'policyengine-taxsim < input.csv > output.csv', language: 'cli' },
  },
  python: {
    before: { label: 'Python', code: 'import subprocess\nresult = subprocess.run(\n  "taxsim35 < input.csv > output.csv",\n  shell=True\n)', language: 'python' },
    after: { label: 'Python', code: 'from policyengine_taxsim.runners import PolicyEngineRunner\nimport pandas as pd\n\ndf = pd.read_csv("input.csv")\nresult = PolicyEngineRunner(df).run()', language: 'python' },
  },
  r: {
    before: { label: 'R', code: 'library(usincometaxes)\nresult <- taxsim_calculate_taxes(input)', language: 'r' },
    after: { label: 'R', code: 'library(policyenginetaxsim)\nresult <- policyengine_calculate_taxes(input)', language: 'r' },
  },
  stata: {
    before: { label: 'Stata', code: 'taxsimlocal35, replace', language: 'stata' },
    after: { label: 'Stata', code: 'export delimited using "input.csv", replace\nshell policyengine-taxsim < input.csv > output.csv\nimport delimited using "output.csv", clear', language: 'stata' },
  },
  sas: {
    before: { label: 'SAS', code: '%let rc = %sysfunc(system(\n  taxsim35 < input.csv > output.csv\n));', language: 'cli' },
    after: { label: 'SAS', code: '%let rc = %sysfunc(system(\n  policyengine-taxsim < input.csv > output.csv\n));', language: 'cli' },
  },
  julia: {
    before: { label: 'Julia', code: 'run(pipeline(`taxsim35`,\n  stdin="input.csv",\n  stdout="output.csv"\n))', language: 'cli' },
    after: { label: 'Julia', code: 'run(pipeline(`policyengine-taxsim`,\n  stdin="input.csv",\n  stdout="output.csv"\n))', language: 'cli' },
  },
};

const LandingPage = ({ onNavigateToDashboard, onNavigateToDocumentation }) => {
  const [lang, setLang] = useState('cli');

  const example = COMPARISON_EXAMPLES[lang];

  return (
    <div className="landing-page">
      {/* Hero section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <h1 className="landing-hero-title">
            The next chapter of TAXSIM
          </h1>
          <p className="landing-hero-tagline">
            An open-source, drop-in replacement for TAXSIM35. Same interface,
            same inputs, same outputs — powered by PolicyEngine's
            microsimulation engine.
          </p>
        </div>
      </section>

      {/* Installation */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Installation</h2>
          <div className="landing-get-started-code" style={{ maxWidth: '640px', margin: '0 auto' }}>
            <CodeBlock
              label="Terminal"
              code="pip install policyengine-taxsim"
              language="cli"
            />
          </div>
        </div>
      </section>

      {/* Get started */}
      <section className="landing-section landing-section-alt">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Get started</h2>
          <p className="landing-section-subtitle">
            Same input format, same output variables. Just swap the command.
          </p>
          <div className="landing-lang-toggle">
            {LANG_TABS.map(({ id, label }) => (
              <button
                key={id}
                className={`landing-lang-btn${lang === id ? ' landing-lang-btn-active' : ''}`}
                onClick={() => setLang(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="landing-compare-grid">
            <div>
              <h3 className="landing-compare-label" style={{ color: 'var(--dark-gray)' }}>TAXSIM35 (before)</h3>
              <CodeBlock label={example.before.label} code={example.before.code} language={example.before.language} />
            </div>
            <div>
              <h3 className="landing-compare-label" style={{ color: 'var(--blue-primary)' }}>PolicyEngine TAXSIM (after)</h3>
              <CodeBlock label={example.after.label} code={example.after.code} language={example.after.language} />
            </div>
          </div>
        </div>
      </section>

      {/* Powered by PolicyEngine */}
      <section className="landing-section landing-section-alt">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Powered by PolicyEngine</h2>
          <p className="landing-section-subtitle">
            PolicyEngine and TAXSIM have been cross-validated against each other since 2021,
            comparing results across thousands of CPS households. That work led to a formal
            partnership with NBER.
          </p>
          <div className="landing-features-grid">
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--teal-accent)' }}>
                <FiCode color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Fully open source</h3>
              <p className="landing-feature-description">
                All code — the TAXSIM emulator and the PolicyEngine engine it
                runs on — is open source on GitHub. Inspect every calculation.
              </p>
            </div>
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--darkest-blue)' }}>
                <FiMap color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Drop-in compatible</h3>
              <p className="landing-feature-description">
                Same stdin/stdout interface, same input variables, same output
                format. Just swap <code>taxsim35</code> for{' '}
                <code>policyengine-taxsim</code>.
              </p>
            </div>
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--blue-primary)' }}>
                <FiClock color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">1960s to today</h3>
              <p className="landing-feature-description">
                Automatic year-stitching routes 2021+ to PolicyEngine and
                earlier years to TAXSIM35, so a single command handles any
                tax year from the 1960s onward.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Validated by leading institutions */}
      <section className="landing-section landing-section-alt">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Validated by leading institutions</h2>
          <div className="landing-social-proof">
            <div className="landing-social-proof-card">
              <div className="landing-social-proof-header">
                <FiShield size={20} color="var(--blue-primary)" />
                <h3>NBER partnership</h3>
              </div>
              <p>
                Built under a{' '}
                <a
                  href="https://drive.google.com/file/d/1V5TJk7C01CLYP_FXUZTmHEdLk-WCV4WN/view?usp=sharing"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  memorandum of understanding
                </a>
                {' '}with the National Bureau of Economic Research and TAXSIM creator Daniel Feenberg.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-nber-mou-taxsim"
                target="_blank"
                rel="noopener noreferrer"
                className="landing-validation-link"
              >
                Read more <FiArrowRight size={14} />
              </a>
            </div>
            <div className="landing-social-proof-card">
              <div className="landing-social-proof-header">
                <FiShield size={20} color="var(--teal-accent)" />
                <h3>Federal Reserve Bank of Atlanta</h3>
              </div>
              <p>
                Three-way validation with the Atlanta Fed's{' '}
                <a
                  href="https://drive.google.com/file/d/1ye8BQo6gXVWl50F1ht6UzB9HsdrfpeOQ/view"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Policy Rules Database
                </a>
                {' '}— cross-checking PolicyEngine, TAXSIM, and the Fed's models.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-atlanta-fed-mou-prd"
                target="_blank"
                rel="noopener noreferrer"
                className="landing-validation-link"
              >
                Read more <FiArrowRight size={14} />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Beyond TAXSIM */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Beyond TAXSIM</h2>
          <p className="landing-section-subtitle">
            TAXSIM covers federal and state income taxes. PolicyEngine goes further — benefit
            programs, payroll taxes, detailed credits, and full microsimulation on representative
            survey data.
          </p>
          <div className="landing-features-grid">
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--blue-primary)' }}>
                <FiBarChart2 color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Microsimulation</h3>
              <p className="landing-feature-description">
                Estimate the budgetary and distributional impact of policy reforms
                across the full US population using PolicyEngine's{' '}
                <a href="https://policyengine.org/us/model" target="_blank" rel="noopener noreferrer">
                  Enhanced CPS
                </a>
                , which integrates and calibrates multiple survey datasets.
              </p>
            </div>
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--teal-accent)' }}>
                <FiShield color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Benefits and taxes</h3>
              <p className="landing-feature-description">
                SNAP, SSI, Medicaid, CHIP, ACA marketplace subsidies, TANF,
                housing vouchers, WIC, EITC, CTC, and hundreds more federal
                and state programs — all in one model.
              </p>
            </div>
          </div>
          <div style={{ textAlign: 'center', marginTop: '2rem' }}>
            <a
              href="https://policyengine.org"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-cta-primary"
              style={{ display: 'inline-flex', textDecoration: 'none' }}
            >
              Explore PolicyEngine
              <FiArrowRight style={{ marginLeft: '8px' }} />
            </a>
          </div>
        </div>
      </section>

      {/* Documentation CTA */}
      <section className="landing-section landing-section-alt">
        <div className="landing-section-inner" style={{ textAlign: 'center' }}>
          <button
            onClick={onNavigateToDocumentation}
            className="landing-cta-primary"
          >
            Read the full documentation
            <FiArrowRight style={{ marginLeft: '8px' }} />
          </button>
        </div>
      </section>

      {/* Footer */}
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
              <span>GitHub repository</span>
              <FiExternalLink size={14} className="landing-footer-external" />
            </a>
            <a
              href="https://taxsim.nber.org/taxsim35/"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-footer-card"
            >
              <FiExternalLink size={20} />
              <span>TAXSIM35 official docs</span>
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
};

export default LandingPage;
