import React, { useState, useCallback } from 'react';
import { FiDownload } from 'react-icons/fi';
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
    setSelectedState(null);
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

  // Landing and documentation render before loading checks (no dashboard data needed)
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
      {/* Dashboard header */}
      <div className="dash-header">
        <div className="dash-header-inner">
          <div className="dash-header-text">
            <h1 className="dash-header-title">
              {selectedYear} comparison
              {selectedState && <span className="dash-header-state"> — {selectedState}</span>}
            </h1>
            <p className="dash-header-desc">
              PolicyEngine vs TAXSIM-35 on CPS microdata. Records match when federal and state tax differ by less than $15.
            </p>
          </div>
          <div className="dash-header-controls">
            <YearTabs
              selectedYear={selectedYear}
              onYearChange={handleYearChange}
              availableYears={availableYears}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <StateFilter
                selectedState={selectedState}
                onStateChange={handleStateChange}
              />
              <button onClick={handleExport} className="dashboard-export-button">
                <FiDownload style={{ marginRight: '6px' }} />
                Export
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <main className="dashboard-content">
        <section style={{ marginBottom: '2rem' }}>
          <MetricsRow
            data={currentYearData}
            selectedState={selectedState}
          />
        </section>

        <section>
          <h2 className="section-title">State-by-state analysis</h2>
          <StateTable
            data={currentYearData}
            selectedState={selectedState}
            selectedYear={selectedYear}
            onStateSelect={handleStateChange}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
