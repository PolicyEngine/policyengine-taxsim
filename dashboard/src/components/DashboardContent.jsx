'use client';

import { useState } from 'react';
import { IconDownload, IconDatabaseExport } from '@tabler/icons-react';
import YearTabs from '@/components/YearTabs';
import StateFilter from '@/components/StateFilter';
import MetricsRow from '@/components/MetricsRow';
import StateTable from '@/components/StateTable';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import { useYearData } from '@/hooks/useYearData';
import { exportAllData } from '@/utils/exportData';
import { TOLERANCE_MODES, fullDataUrl } from '@/constants';

export default function DashboardContent() {
  const {
    selectedYear,
    setSelectedYear,
    currentYearData,
    allYearData,
    availableYears,
    loading,
    error,
  } = useYearData(2023);

  const [selectedState, setSelectedState] = useState(null);
  const [toleranceMode, setToleranceMode] = useState(TOLERANCE_MODES.RELATIVE);

  if (loading) {
    return (
      <LoadingSpinner
        message="Loading dashboard data..."
        subMessage="Fetching comparison results for all years"
      />
    );
  }

  if (error) {
    return <ErrorMessage error={error} retry={() => window.location.reload()} />;
  }

  if (!currentYearData) {
    return (
      <ErrorMessage
        error={`No data available for year ${selectedYear}`}
        retry={() => setSelectedYear(2023)}
      />
    );
  }

  const availableStates = currentYearData?.summary?.stateBreakdown
    ? currentYearData.summary.stateBreakdown.map((s) => s.state)
    : [];

  return (
    <div>
      {/* Dashboard header */}
      <div className="bg-gradient-to-r from-white to-gray-50 border-b border-gray-200 px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold text-secondary-900">
            TAXSIM validation dashboard
            {selectedState && (
              <span className="text-primary-500 font-normal">
                {' '}
                - {selectedState}
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Comparing PolicyEngine and TAXSIM tax calculations across states and
            years
          </p>

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-3 mt-4">
            <YearTabs
              selectedYear={selectedYear}
              onYearChange={setSelectedYear}
              availableYears={availableYears}
            />

            <StateFilter
              selectedState={selectedState}
              onStateChange={setSelectedState}
              availableStates={availableStates}
            />

            <div className="inline-flex rounded-lg border border-gray-200 bg-white p-1 text-sm" role="group" aria-label="Match tolerance">
              <button
                onClick={() => setToleranceMode(TOLERANCE_MODES.ABSOLUTE)}
                className={`px-3 py-1.5 rounded-md font-medium transition ${
                  toleranceMode === TOLERANCE_MODES.ABSOLUTE
                    ? 'bg-primary-500 text-white'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                ±$15
              </button>
              <button
                onClick={() => setToleranceMode(TOLERANCE_MODES.RELATIVE)}
                className={`px-3 py-1.5 rounded-md font-medium transition ${
                  toleranceMode === TOLERANCE_MODES.RELATIVE
                    ? 'bg-primary-500 text-white'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                ±1% of income
              </button>
            </div>

            <button
              onClick={exportAllData}
              className="inline-flex items-center px-4 py-2.5 rounded-lg bg-primary-500 text-white font-semibold text-sm hover:bg-primary-600 transition shadow-sm"
            >
              <IconDownload size={16} className="mr-2" />
              Export sample
            </button>

            <a
              href={fullDataUrl(selectedYear)}
              className="inline-flex items-center px-4 py-2.5 rounded-lg border border-primary-500 text-primary-600 font-semibold text-sm hover:bg-primary-50 transition"
              title={`Download the complete ${selectedYear} comparison (all 111,347 records) — ~110MB`}
            >
              <IconDatabaseExport size={16} className="mr-2" />
              Download full {selectedYear} data
            </a>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <MetricsRow
          data={currentYearData}
          selectedState={selectedState}
          toleranceMode={toleranceMode}
        />

        <h2 className="text-2xl font-bold text-secondary-900 mb-6 pb-3">
          State-by-state analysis
        </h2>

        <StateTable
          data={currentYearData}
          selectedState={selectedState}
          selectedYear={selectedYear}
          onStateSelect={setSelectedState}
          toleranceMode={toleranceMode}
        />
      </div>
    </div>
  );
}
