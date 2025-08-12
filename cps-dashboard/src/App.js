import React, { useState, useEffect } from 'react';
import { FiDownload } from 'react-icons/fi';
import YearTabs from './components/YearTabs';
import StateFilter from './components/StateFilter';
import MetricsRow from './components/MetricsRow';
import StateTable from './components/StateTable';
import VariableAnalysis from './components/VariableAnalysis';
import { loadYearData } from './utils/dataLoader';
import './App.css';

function App() {
  const [selectedYear, setSelectedYear] = useState(2023);
  const [selectedState, setSelectedState] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load data when year changes
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const yearData = await loadYearData(selectedYear);
        setData(yearData);
      } catch (err) {
        console.error('Error loading data:', err);
        setError(`Failed to load data for ${selectedYear}`);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedYear]);

  const handleYearChange = (year) => {
    setSelectedYear(year);
    setSelectedState(null); // Reset state filter when year changes
  };

  const handleStateChange = (state) => {
    setSelectedState(state);
  };

  const handleExport = () => {
    // TODO: Implement export functionality
    console.log('Export data for year:', selectedYear, 'state:', selectedState);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl text-gray-600">Loading {selectedYear} data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="main-header shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <h1 className="text-3xl main-title">
              PolicyEngine-Taxsim Emulator
            </h1>
            <button
              onClick={handleExport}
              className="btn"
            >
              <FiDownload className="mr-2" />
              Export Data
            </button>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col gap-4 mb-6" style={{flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between'}}>
          <YearTabs 
            selectedYear={selectedYear}
            onYearChange={handleYearChange}
          />
          <StateFilter
            selectedState={selectedState}
            onStateChange={handleStateChange}
          />
        </div>

        {/* Main Content */}
        <div className="space-y-8">
          {/* Performance Overview Section */}
          <section>
            <h2 className="section-title">Performance Overview</h2>
            <MetricsRow 
              data={data}
              selectedState={selectedState}
            />
          </section>

          {/* State Analysis Section */}
          <section>
            <h2 className="section-title">State-by-State Analysis</h2>
            <StateTable
              data={data}
              selectedState={selectedState}
              onStateSelect={handleStateChange}
            />
          </section>

          {/* Variable Analysis Section */}
          <section>
            <VariableAnalysis
              data={data}
              selectedState={selectedState}
            />
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;