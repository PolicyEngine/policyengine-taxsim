import React, { useState, useCallback } from 'react';
import { FiDownload, FiBook, FiHome, FiBarChart2, FiGithub } from 'react-icons/fi';
import YearTabs from './components/YearTabs';
import StateFilter from './components/StateFilter';
import MetricsRow from './components/MetricsRow';
import StateTable from './components/StateTable';
import Documentation from './components/Documentation';
import LandingPage from './components/LandingPage';
import LoadingSpinner from './components/common/LoadingSpinner';
import ErrorMessage from './components/common/ErrorMessage';
import { useYearData } from './hooks/useYearData';
import { exportAllData } from './utils/exportData';

function App() {
  const [selectedState, setSelectedState] = useState(null);
  const [currentView, setCurrentView] = useState('landing'); // 'landing', 'dashboard', or 'documentation'
  const {
    selectedYear,
    setSelectedYear,
    currentYearData,
    allYearData,
    availableYears,
    loading,
    error
  } = useYearData(2023);

  const handleYearChange = useCallback((year) => {
    setSelectedYear(year);
    setSelectedState(null); // Reset state filter when year changes
  }, [setSelectedYear]);

  const handleStateChange = useCallback((state) => {
    setSelectedState(state);
  }, []);

  const handleExport = useCallback(async () => {
    try {
      await exportAllData();
    } catch (error) {
      console.error('Export failed:', error);
      alert('Failed to export data. Please try again.');
    }
  }, []);

  const handleViewChange = useCallback((view) => {
    setCurrentView(view);
  }, []);

  // Landing and Documentation render before loading checks (no dashboard data needed)
  if (currentView === 'landing') {
    return (
      <LandingPage
        onNavigateToDashboard={() => handleViewChange('dashboard')}
        onNavigateToDocumentation={() => handleViewChange('documentation')}
      />
    );
  }

  if (currentView === 'documentation') {
    return (
      <Documentation
        onBackToDashboard={() => handleViewChange('dashboard')}
        onNavigateHome={() => handleViewChange('landing')}
      />
    );
  }

  // Loading state (only blocks the dashboard, which needs data)
  if (loading) {
    return (
      <LoadingSpinner
        message="Loading data for all years..."
        subMessage="This may take a moment on first load"
      />
    );
  }

  // Error state with no data
  if (error && Object.keys(allYearData).length === 0) {
    return <ErrorMessage error={error} />;
  }

  // No data for selected year
  if (!currentYearData && !loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex-center">
        <div className="text-center">
          <div className="text-xl text-red-600 mb-2">
            Data for {selectedYear} is not available
          </div>
          <div className="text-sm text-gray-500">
            Available years: {availableYears.join(', ')}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="landing-page">
      {/* Navigation — matches landing page */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-nav-brand">
            <FiBarChart2 style={{ marginRight: '8px' }} />
            Comparison Dashboard
          </div>
          <div className="landing-nav-links">
            <button onClick={() => handleViewChange('landing')} className="landing-nav-link">
              <FiHome style={{ marginRight: '6px' }} />
              Home
            </button>
            <button onClick={() => handleViewChange('documentation')} className="landing-nav-link">
              <FiBook style={{ marginRight: '6px' }} />
              Documentation
            </button>
            <button onClick={handleExport} className="landing-nav-link">
              <FiDownload style={{ marginRight: '6px' }} />
              Export Data
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

      {/* Main Content */}
      <main className="dashboard-content">
        {/* Controls */}
        <div className="flex-between mb-6">
          <YearTabs
            selectedYear={selectedYear}
            onYearChange={handleYearChange}
            availableYears={availableYears}
          />
          <StateFilter
            selectedState={selectedState}
            onStateChange={handleStateChange}
          />
        </div>

        {/* Dashboard Sections */}
        <div className="space-y-8">
          {/* Performance Overview */}
          <section>
            <h2 className="section-title">Performance Overview</h2>
            <MetricsRow
              data={currentYearData}
              selectedState={selectedState}
            />
          </section>

          {/* State Analysis */}
          <section>
            <h2 className="section-title">State-by-State Analysis</h2>
            <StateTable
              data={currentYearData}
              selectedState={selectedState}
              selectedYear={selectedYear}
              onStateSelect={handleStateChange}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;