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
      {/* Hero console */}
      <div className="hero-console text-white">
        <div className="max-w-7xl mx-auto px-6 py-9">
          <div className="font-mono text-[11px] tracking-[0.22em] uppercase text-primary-200">
            PolicyEngine&nbsp;×&nbsp;TAXSIM
          </div>

          <h1 className="mt-3 text-3xl md:text-4xl font-bold tracking-tight">
            TAXSIM validation
            {selectedState && (
              <span className="text-primary-200 font-normal"> · {selectedState}</span>
            )}
          </h1>
        </div>
      </div>

      {/* Control bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex flex-wrap items-center gap-3">
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

          <div
            className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-0.5 font-mono text-xs"
            role="group"
            aria-label="Match tolerance"
          >
            <button
              onClick={() => setToleranceMode(TOLERANCE_MODES.ABSOLUTE)}
              className={`px-2.5 py-1 rounded font-medium transition ${
                toleranceMode === TOLERANCE_MODES.ABSOLUTE
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              ±$15
            </button>
            <button
              onClick={() => setToleranceMode(TOLERANCE_MODES.RELATIVE)}
              className={`px-2.5 py-1 rounded font-medium transition ${
                toleranceMode === TOLERANCE_MODES.RELATIVE
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              ±1% income
            </button>
            <button
              onClick={() => setToleranceMode(TOLERANCE_MODES.RELATIVE_NET)}
              className={`px-2.5 py-1 rounded font-medium transition ${
                toleranceMode === TOLERANCE_MODES.RELATIVE_NET
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
              title="±1% of income, with one-time state rebates netted out of state tax on both sides — removes the TAXSIM payout-year vs PolicyEngine liability-year rebate timing difference (issue #1068)"
            >
              ±1% net of rebates
            </button>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={exportAllData}
              className="inline-flex items-center px-3 py-1.5 rounded-md border border-gray-200 text-gray-700 font-semibold text-[13px] hover:bg-gray-50 transition"
            >
              <IconDownload size={15} className="mr-1.5" />
              Export sample
            </button>

            <a
              href={fullDataUrl(selectedYear)}
              className="inline-flex items-center px-3 py-1.5 rounded-md bg-primary-600 text-white font-semibold text-[13px] hover:bg-primary-700 transition"
              title={`Download the complete ${selectedYear} comparison (all 111,347 records) — ~110MB`}
            >
              <IconDatabaseExport size={15} className="mr-1.5" />
              Full {selectedYear} data
            </a>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <MetricsRow
          data={currentYearData}
          selectedState={selectedState}
          toleranceMode={toleranceMode}
        />

        <div className="mt-10 mb-5">
          <div className="font-mono text-[11px] tracking-[0.18em] uppercase text-gray-400">
            By jurisdiction
          </div>
          <h2 className="mt-1 text-2xl font-bold text-secondary-900 tracking-tight">
            State-by-state agreement
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Sorted by federal agreement. Bars are color-coded by calibration band —
            <span className="text-[#E5484D] font-medium"> coral</span> flags states that diverge.
          </p>
        </div>

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
