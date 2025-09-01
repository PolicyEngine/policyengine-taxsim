import React, { useState, useCallback } from 'react';
import { FiDownload, FiBook } from 'react-icons/fi';
import YearTabs from './components/YearTabs';
import StateFilter from './components/StateFilter';
import MetricsRow from './components/MetricsRow';
import StateTable from './components/StateTable';
import Documentation from './components/Documentation';
import LoadingSpinner from './components/common/LoadingSpinner';
import ErrorMessage from './components/common/ErrorMessage';
import Button from './components/common/Button';
import { useYearData } from './hooks/useYearData';

function App() {
  const [selectedState, setSelectedState] = useState(null);
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' or 'documentation'
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

  const handleExport = useCallback(() => {
    // TODO: Implement export functionality
    alert(`Export functionality coming soon!\nYear: ${selectedYear}, State: ${selectedState || 'All'}`);
  }, [selectedYear, selectedState]);

  const handleViewChange = useCallback((view) => {
    setCurrentView(view);
  }, []);

  // Loading state
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

  // Show Documentation view
  if (currentView === 'documentation') {
    return <Documentation onBackToDashboard={() => handleViewChange('dashboard')} />;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="main-header shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex-between py-6">
            <h1 className="text-3xl main-title">
              PolicyEngine-Taxsim Emulator
            </h1>
            <Button
              onClick={handleExport}
              icon={<FiDownload />}
            >
              Export Data
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Navigation Tabs */}
        <div className="flex justify-end mb-3">
          <nav className="flex space-x-1">
            <button
              onClick={() => handleViewChange('dashboard')}
              className={`year-tab ${currentView === 'dashboard' ? 'active' : 'inactive'}`}
            >
              Dashboard
            </button>
            <button
              onClick={() => handleViewChange('documentation')}
              className={`year-tab ${currentView === 'documentation' ? 'active' : 'inactive'} flex items-center`}
            >
              <FiBook className="mr-1 w-4 h-4" />
              Documentation
            </button>
          </nav>
        </div>

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