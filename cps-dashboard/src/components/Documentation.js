import React, { useState, useEffect } from 'react';
import { FiExternalLink, FiChevronDown, FiChevronRight, FiSearch, FiCheck, FiX, FiArrowLeft } from 'react-icons/fi';
import { loadConfigurationData } from '../utils/configLoader';
import LoadingSpinner from './common/LoadingSpinner';

const Documentation = ({ onBackToDashboard }) => {
  const [searchTerm, setSearchTerm] = useState('');
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

  // Filter mappings based on search term
  const filteredMappings = configData.variableMappings.filter(mapping =>
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
                PolicyEngine-TAXSIM Documentation
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
                PolicyEngine-TAXSIM Documentation
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
            <div className="flex items-center space-x-4">
              {onBackToDashboard && (
                <button
                  onClick={onBackToDashboard}
                  className="btn-ghost"
                >
                  <FiArrowLeft className="mr-2 w-4 h-4" />
                  Back to Dashboard
                </button>
              )}
              <h1 className="text-3xl main-title">
                PolicyEngine-TAXSIM Documentation
              </h1>
            </div>
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
                    This table shows how TAXSIM input variables are mapped to PolicyEngine variables in our implementation.
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

                {/* Search Bar */}
                <div className="mb-4">
                  <div className="relative">
                    <FiSearch style={{ position: 'absolute', left: '12px', top: '12px', width: '16px', height: '16px', color: 'var(--dark-gray)' }} />
                    <input
                      type="text"
                      placeholder="Search variables..."
                      className="select"
                      style={{ paddingLeft: '40px', width: '100%', maxWidth: '400px' }}
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
                      {filteredMappings.map((mapping, index) => (
                        <tr key={index}>
                          <td style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: '600', color: 'var(--blue-primary)' }}>
                            {mapping.taxsim}
                          </td>
                          <td style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: '600', color: 'var(--darkest-blue)' }}>
                            {mapping.githubLink ? (
                              <a 
                                href={mapping.githubLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ 
                                  color: 'var(--blue-primary)', 
                                  textDecoration: 'none',
                                  display: 'inline-flex',
                                  alignItems: 'center'
                                }}
                                onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
                                onMouseOut={(e) => e.target.style.textDecoration = 'none'}
                              >
                                {mapping.policyengine}
                                <FiExternalLink style={{ marginLeft: '4px', fontSize: '10px' }} />
                              </a>
                            ) : (
                              mapping.policyengine
                            )}
                          </td>
                          <td style={{ fontSize: '14px', color: 'var(--dark-gray)' }}>
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
                                Not Available
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
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
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Primary/Spouse Age:</strong> {configData.systemAssumptions.defaultAges?.primary || 40} years (when not specified)</li>
                      <li style={{ marginBottom: '12px', fontSize: '14px', color: 'var(--darkest-blue)', lineHeight: '1.6' }}><strong>Dependent Age:</strong> {configData.systemAssumptions.defaultAges?.dependent || 10} years (when not specified)</li>
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
                    Some PolicyEngine outputs combine multiple TAXSIM variables:
                  </p>
                  <div style={{ backgroundColor: 'var(--blue-98)', padding: '20px', borderRadius: '8px', border: '1px solid var(--blue-95)' }}>
                    <div className="space-y-2">
                      {configData.implementationDetails.multipleVariableHandling?.map((item, index) => (
                        <div key={index} style={{ marginBottom: index === configData.implementationDetails.multipleVariableHandling.length - 1 ? '0' : '12px' }}>
                          <code style={{ backgroundColor: 'var(--white)', padding: '6px 12px', borderRadius: '4px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--blue-primary)', fontWeight: '600' }}>{item.taxsim}</code>
                          <span style={{ color: 'var(--dark-gray)', marginLeft: '12px', fontSize: '14px' }}>→ {item.policyengine}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
};

export default Documentation;
