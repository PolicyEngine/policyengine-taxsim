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
  const [allYearData, setAllYearData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const availableYears = [2021, 2022, 2023, 2024];
  
  // Get current year data from cached data
  const data = allYearData[selectedYear] || null;

  // Load all year data on component mount
  useEffect(() => {
    const fetchAllData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        console.log('Loading data for all years...');
        
        // Load all years in parallel
        const loadPromises = availableYears.map(async (year) => {
          try {
            const yearData = await loadYearData(year);
            return { year, data: yearData };
          } catch (err) {
            console.warn(`Failed to load data for year ${year}:`, err);
            return { year, data: null, error: err.message };
          }
        });
        
        const results = await Promise.all(loadPromises);
        
        // Build the data object
        const dataByYear = {};
        let hasAnyData = false;
        
        results.forEach(({ year, data, error }) => {
          if (data) {
            dataByYear[year] = data;
            hasAnyData = true;
          } else if (error) {
            console.error(`Year ${year} failed to load:`, error);
          }
        });
        
        if (!hasAnyData) {
          throw new Error('Failed to load data for any year');
        }
        
        setAllYearData(dataByYear);
        console.log('All year data loaded successfully');
        
      } catch (err) {
        console.error('Error loading data:', err);
        setError('Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []); // Only run once on mount

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
        <div className="text-center">
          <div className="text-xl text-gray-600 mb-2">Loading data for all years...</div>
          <div className="text-sm text-gray-500">This may take a moment on first load</div>
        </div>
      </div>
    );
  }

  if (error && Object.keys(allYearData).length === 0) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl text-red-600">{error}</div>
      </div>
    );
  }

  // Show a message if current year data is not available
  if (!data && !loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl text-red-600 mb-2">Data for {selectedYear} is not available</div>
          <div className="text-sm text-gray-500">
            Available years: {Object.keys(allYearData).join(', ')}
          </div>
        </div>
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
            availableYears={Object.keys(allYearData).map(Number)}
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