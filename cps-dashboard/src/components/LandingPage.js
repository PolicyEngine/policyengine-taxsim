import React from 'react';
import { FiGithub, FiExternalLink, FiArrowRight, FiBook, FiBarChart2, FiHome, FiShield, FiCode, FiMap, FiLock } from 'react-icons/fi';

const LandingPage = ({ onNavigateToDashboard, onNavigateToDocumentation }) => {

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
            <button
              onClick={onNavigateToDashboard}
              className="landing-nav-link"
            >
              <FiBarChart2 style={{ marginRight: '6px' }} />
              Dashboard
            </button>
            <button
              onClick={onNavigateToDocumentation}
              className="landing-nav-link"
            >
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

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <h1 className="landing-hero-title">
            PolicyEngine TAXSIM Emulator
          </h1>
          <p className="landing-hero-tagline">
            An open-source, local replacement for NBER's TAXSIM-35. Run the same tax
            calculations on your own machine — no data leaves your environment. Powered
            by PolicyEngine's microsimulation model. Same inputs, same outputs.
          </p>
          <div className="landing-hero-ctas">
            <button
              onClick={onNavigateToDocumentation}
              className="landing-cta-primary"
            >
              Get Started
              <FiArrowRight style={{ marginLeft: '8px' }} />
            </button>
            <button
              onClick={onNavigateToDashboard}
              className="landing-cta-secondary"
            >
              View Dashboard
              <FiBarChart2 style={{ marginLeft: '8px' }} />
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Why PolicyEngine TAXSIM?</h2>
          <div className="landing-features-grid">
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--blue-primary)' }}>
                <FiLock color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Runs Locally</h3>
              <p className="landing-feature-description">
                Traditional TAXSIM requires sending data to NBER's servers. This emulator
                runs entirely on your machine — critical for researchers working with
                confidential microdata (CPS, ACS, SCF, administrative records) behind
                institutional firewalls.
              </p>
            </div>
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--teal-accent)' }}>
                <FiCode color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Open Source</h3>
              <p className="landing-feature-description">
                Fully transparent tax calculations you can inspect and audit.
                Built on PolicyEngine's open-source microsimulation model
                on <a href="https://github.com/PolicyEngine/policyengine-taxsim" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--blue-primary)', fontWeight: 600 }}>GitHub</a>.
              </p>
            </div>
            <div className="landing-feature-card">
              <div className="landing-feature-icon" style={{ background: 'var(--darkest-blue)' }}>
                <FiMap color="white" size={24} />
              </div>
              <h3 className="landing-feature-title">Drop-in Compatible</h3>
              <p className="landing-feature-description">
                Accepts the same TAXSIM-35 input variables and returns the same output
                format. If you already have a TAXSIM workflow, switch to
                local computation with minimal code changes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Validation & Partnerships Section */}
      <section className="landing-section landing-section-alt">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Validated by Leading Institutions</h2>
          <p className="landing-validation-intro">
            PolicyEngine has been rigorously validating its tax calculations against TAXSIM
            for over three years. This work is formalized through memoranda of understanding
            with two major research institutions.
          </p>
          <div className="landing-validation-grid">
            <div className="landing-validation-card">
              <div className="landing-validation-card-header">
                <FiShield size={20} color="var(--blue-primary)" />
                <h3>NBER Partnership</h3>
              </div>
              <p>
                PolicyEngine signed a{' '}
                <a
                  href="https://drive.google.com/file/d/1V5TJk7C01CLYP_FXUZTmHEdLk-WCV4WN/view?usp=sharing"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  memorandum of understanding
                </a>
                {' '}with the National Bureau of Economic Research (NBER) to build this
                open-source emulator of TAXSIM. We work directly with Daniel Feenberg,
                creator of TAXSIM, and NBER President James Poterba to ensure accuracy
                and continuity for the research community.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-nber-mou-taxsim"
                target="_blank"
                rel="noopener noreferrer"
                className="landing-validation-link"
              >
                Read the announcement <FiExternalLink size={14} />
              </a>
            </div>
            <div className="landing-validation-card">
              <div className="landing-validation-card-header">
                <FiShield size={20} color="var(--teal-accent)" />
                <h3>Federal Reserve Bank of Atlanta</h3>
              </div>
              <p>
                PolicyEngine signed a{' '}
                <a
                  href="https://drive.google.com/file/d/1ye8BQo6gXVWl50F1ht6UzB9HsdrfpeOQ/view"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  memorandum of understanding
                </a>
                {' '}with the Federal Reserve Bank of Atlanta to integrate their Policy
                Rules Database into our validation infrastructure, creating a three-way
                validation system across PolicyEngine, TAXSIM, and the Atlanta Fed's models.
              </p>
              <a
                href="https://policyengine.org/us/research/policyengine-atlanta-fed-mou-prd"
                target="_blank"
                rel="noopener noreferrer"
                className="landing-validation-link"
              >
                Read the announcement <FiExternalLink size={14} />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="landing-section">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">How It Works</h2>
          <p className="landing-validation-intro">
            If you've used TAXSIM before, the workflow is the same — except everything
            runs locally. No data is sent to external servers.
          </p>
          <div className="landing-how-steps">
            <div className="landing-how-step">
              <div className="landing-how-step-number">1</div>
              <h3>Prepare Input</h3>
              <p>Use the standard TAXSIM-35 CSV format with your survey microdata (CPS, ACS, SCF, etc.).</p>
            </div>
            <div className="landing-how-step-arrow">
              <FiArrowRight size={24} color="var(--medium-light-gray)" />
            </div>
            <div className="landing-how-step">
              <div className="landing-how-step-number">2</div>
              <h3>Run Locally</h3>
              <p>Call PolicyEngineRunner from Python or R. All computation happens on your machine.</p>
            </div>
            <div className="landing-how-step-arrow">
              <FiArrowRight size={24} color="var(--medium-light-gray)" />
            </div>
            <div className="landing-how-step">
              <div className="landing-how-step-number">3</div>
              <h3>Get Results</h3>
              <p>Receive federal and state tax calculations in the standard TAXSIM output format.</p>
            </div>
          </div>
          <div className="landing-io-cta">
            <button
              onClick={onNavigateToDocumentation}
              className="landing-cta-primary"
            >
              View Installation & Full Documentation
              <FiBook style={{ marginLeft: '8px' }} />
            </button>
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
