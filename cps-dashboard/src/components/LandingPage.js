import React, { useState } from 'react';
import { FiGithub, FiExternalLink, FiArrowRight, FiBook, FiBarChart2, FiHome, FiShield, FiCode, FiMap } from 'react-icons/fi';

const LandingPage = ({ onNavigateToDashboard, onNavigateToDocumentation }) => {
  const [lang, setLang] = useState('python');

  return (
    <div className="landing-page">
      {/* Navigation */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-nav-brand">
            <FiHome style={{ marginRight: '8px' }} />
            PolicyEngine TAXSIM
          </div>
          <div className="landing-nav-links">
            <button className="landing-nav-link landing-nav-link-active">
              <FiHome style={{ marginRight: '6px' }} />
              Home
            </button>
            <button
              onClick={onNavigateToDocumentation}
              className="landing-nav-link"
            >
              <FiBook style={{ marginRight: '6px' }} />
              Documentation
            </button>
            <button
              onClick={onNavigateToDashboard}
              className="landing-nav-link"
            >
              <FiBarChart2 style={{ marginRight: '6px' }} />
              Dashboard
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

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <h1 className="landing-hero-title">
            The next chapter of TAXSIM
          </h1>
          <p className="landing-hero-tagline">
            PolicyEngine continues the TAXSIM legacy with an open-source tax
            calculator. Same inputs, same outputs — now powered by
            PolicyEngine's microsimulation engine.
          </p>
          <div className="landing-hero-ctas">
            <button
              onClick={onNavigateToDocumentation}
              className="landing-cta-primary"
            >
              Read the documentation
              <FiArrowRight style={{ marginLeft: '8px' }} />
            </button>
            <button
              onClick={onNavigateToDashboard}
              className="landing-cta-secondary"
            >
              View comparison dashboard
              <FiBarChart2 style={{ marginLeft: '8px' }} />
            </button>
          </div>
        </div>
      </section>

      {/* Get Started */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Get started</h2>
          <div className="landing-lang-toggle">
            <button
              className={`landing-lang-btn${lang === 'python' ? ' landing-lang-btn-active' : ''}`}
              onClick={() => setLang('python')}
            >
              Python
            </button>
            <button
              className={`landing-lang-btn${lang === 'r' ? ' landing-lang-btn-active' : ''}`}
              onClick={() => setLang('r')}
            >
              R
            </button>
          </div>
          <div className="landing-get-started-code">
            <div className="landing-code-block">
              <div className="landing-code-header">
                <span className="landing-code-label">{lang === 'python' ? 'Python' : 'R'}</span>
              </div>
              <pre className="landing-code-content"><code>{lang === 'python'
? `pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git

import pandas as pd
from policyengine_taxsim.runners import PolicyEngineRunner

df = pd.read_csv("input.csv")
runner = PolicyEngineRunner(df)
output = runner.run()`
: `devtools::install_github(
  "PolicyEngine/policyengine-taxsim",
  subdir = "r-package/policyenginetaxsim"
)

library(policyenginetaxsim)
setup_policyengine()
input <- read.csv("input.csv")
output <- policyengine_calculate_taxes(input)`}</code></pre>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
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
                Same TAXSIM-35 input variables, same output format. Minimal code
                changes to switch.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof — NBER + Atlanta Fed */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Validated by leading institutions</h2>
          <div className="landing-social-proof">
            <div className="landing-social-proof-card">
              <div className="landing-social-proof-header">
                <FiShield size={20} color="var(--blue-primary)" />
                <h3>NBER Partnership</h3>
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
              <span>GitHub Repository</span>
              <FiExternalLink size={14} className="landing-footer-external" />
            </a>
            <button
              onClick={onNavigateToDashboard}
              className="landing-footer-card"
            >
              <FiBarChart2 size={20} />
              <span>Comparison Dashboard</span>
              <FiArrowRight size={14} className="landing-footer-external" />
            </button>
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
};

export default LandingPage;
