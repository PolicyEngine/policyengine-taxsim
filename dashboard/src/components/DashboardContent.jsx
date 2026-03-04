'use client';

import { useState } from 'react';
import { IconDownload } from '@tabler/icons-react';
import YearTabs from '@/components/YearTabs';
import StateFilter from '@/components/StateFilter';
import MetricsRow from '@/components/MetricsRow';
import StateTable from '@/components/StateTable';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import { useYearData } from '@/hooks/useYearData';
import { exportAllData } from '@/utils/exportData';

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

            <button
              onClick={exportAllData}
              className="inline-flex items-center px-4 py-2.5 rounded-lg bg-primary-500 text-white font-semibold text-sm hover:bg-primary-600 transition shadow-sm"
            >
              <IconDownload size={16} className="mr-2" />
              Export all data
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <MetricsRow data={currentYearData} selectedState={selectedState} />

        <h2 className="text-2xl font-bold text-secondary-900 mb-6 pb-3">
          State-by-state analysis
        </h2>

        <StateTable
          data={currentYearData}
          selectedState={selectedState}
          selectedYear={selectedYear}
          onStateSelect={setSelectedState}
        />
      </div>
    </div>
  );
}
