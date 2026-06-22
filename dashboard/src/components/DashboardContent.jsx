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

  const isRel = toleranceMode === TOLERANCE_MODES.RELATIVE;
  const summary = currentYearData?.summary;
  const heroFederal = summary
    ? (isRel ? summary.federalMatchPctRel ?? summary.federalMatchPct : summary.federalMatchPct)
    : null;
  const heroTotal = summary?.totalRecords ?? 0;
  const heroStateCount = availableStates.length;
  const tolerancePhrase = isRel ? 'within 1% of income' : 'within $15';

  return (
    <div>
      {/* Hero console — the validation result as the thesis */}
      <div className="hero-console text-white">
        <div className="calib-rule h-1.5 w-full opacity-70" />
        <div className="max-w-7xl mx-auto px-6 pt-8 pb-9">
          <div className="font-mono text-[11px] tracking-[0.22em] uppercase text-primary-200">
            Model validation · PolicyEngine&nbsp;×&nbsp;TAXSIM
          </div>

          <h1 className="mt-3 text-3xl md:text-4xl font-bold tracking-tight">
            TAXSIM validation
            {selectedState && (
              <span className="text-primary-200 font-normal"> · {selectedState}</span>
            )}
          </h1>

          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-white/75">
            {heroFederal != null ? (
              <>
                PolicyEngine reproduces TAXSIM federal income tax for{' '}
                <span className="tnum font-mono font-semibold text-white">
                  {heroFederal.toFixed(1)}%
                </span>{' '}
                of {selectedState ? `${selectedState} ` : ''}households in {selectedYear},
                matching {tolerancePhrase}.
              </>
            ) : (
              'Comparing PolicyEngine and TAXSIM tax calculations across states and years.'
            )}
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-x-7 gap-y-2 font-mono text-[13px] text-white/70">
            <span><span className="tnum text-white font-semibold">{heroTotal.toLocaleString()}</span> households</span>
            <span className="h-3 w-px bg-white/20" />
            <span><span className="tnum text-white font-semibold">{heroStateCount}</span> states</span>
            <span className="h-3 w-px bg-white/20" />
            <span><span className="tnum text-white font-semibold">{availableYears?.length ?? 5}</span> tax years</span>
          </div>
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
            className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1 font-mono text-[13px]"
            role="group"
            aria-label="Match tolerance"
          >
            <button
              onClick={() => setToleranceMode(TOLERANCE_MODES.ABSOLUTE)}
              className={`px-3 py-1.5 rounded-md font-medium transition ${
                toleranceMode === TOLERANCE_MODES.ABSOLUTE
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              ±$15
            </button>
            <button
              onClick={() => setToleranceMode(TOLERANCE_MODES.RELATIVE)}
              className={`px-3 py-1.5 rounded-md font-medium transition ${
                toleranceMode === TOLERANCE_MODES.RELATIVE
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              ±1% income
            </button>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={exportAllData}
              className="inline-flex items-center px-3.5 py-2 rounded-lg border border-gray-200 text-gray-700 font-semibold text-sm hover:bg-gray-50 transition"
            >
              <IconDownload size={16} className="mr-2" />
              Export sample
            </button>

            <a
              href={fullDataUrl(selectedYear)}
              className="inline-flex items-center px-3.5 py-2 rounded-lg bg-primary-600 text-white font-semibold text-sm hover:bg-primary-700 transition"
              title={`Download the complete ${selectedYear} comparison (all 111,347 records) — ~110MB`}
            >
              <IconDatabaseExport size={16} className="mr-2" />
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
