'use client';

import { useEffect, useState } from 'react';
import { IconDownload, IconDatabaseExport, IconInfoCircle } from '@tabler/icons-react';
import YearTabs from '@/components/YearTabs';
import StateFilter from '@/components/StateFilter';
import MetricsRow from '@/components/MetricsRow';
import StateTable from '@/components/StateTable';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorMessage from '@/components/common/ErrorMessage';
import { useYearData } from '@/hooks/useYearData';
import { exportAllData } from '@/utils/exportData';
import {
  COMPARISON_NOTE,
  DATASETS,
  DEFAULT_DATASET,
  TOLERANCE_MODES,
  fullDataUrl,
} from '@/constants';

// ?dataset=ecps links straight to the archived Enhanced CPS view.
const datasetFromUrl = () => {
  if (typeof window === 'undefined') return DEFAULT_DATASET;
  const requested = new URLSearchParams(window.location.search).get('dataset');
  return DATASETS[requested] ? requested : DEFAULT_DATASET;
};

export default function DashboardContent() {
  const {
    selectedYear,
    setSelectedYear,
    dataset,
    setDataset,
    currentYearData,
    availableYears,
    loading,
    error,
  } = useYearData(2023);

  const [selectedState, setSelectedState] = useState(null);
  const [toleranceMode, setToleranceMode] = useState(TOLERANCE_MODES.RELATIVE);

  useEffect(() => {
    const requested = datasetFromUrl();
    if (requested !== dataset) setDataset(requested);
    // Read the URL once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chooseDataset = (id) => {
    setDataset(id);
    const url = new URL(window.location.href);
    if (id === DEFAULT_DATASET) url.searchParams.delete('dataset');
    else url.searchParams.set('dataset', id);
    window.history.replaceState(null, '', url);
  };
  const datasetInfo = DATASETS[dataset];

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
          <p className="mt-2 text-sm text-primary-200">
            {currentYearData.summary?.metadata?.dataset?.label || datasetInfo.label}
            {' · '}
            {currentYearData.summary.totalRecords.toLocaleString()} tax units
            {currentYearData.summary?.metadata?.generatedAt && (
              <>
                {' · '}Data updated {currentYearData.summary.metadata.generatedAt.slice(0, 10)}
                {' · '}PolicyEngine US {currentYearData.summary.metadata.policyengineUsVersion}
              </>
            )}
            {currentYearData.summary?.metadata?.taxsimtestBuild && (
              <> · taxsimtest {currentYearData.summary.metadata.taxsimtestBuild}</>
            )}
          </p>
        </div>
      </div>

      {/* Dataset and interpretation notice */}
      <div className="bg-primary-50 border-b border-primary-100">
        <div className="max-w-7xl mx-auto px-6 py-3 flex gap-2.5 text-[13px] text-secondary-900">
          <IconInfoCircle size={17} className="mt-0.5 shrink-0 text-primary-600" />
          <div className="space-y-1">
            <p>
              {datasetInfo.description} <strong>{datasetInfo.caveat}</strong>
            </p>
            <p className="text-gray-600">{COMPARISON_NOTE}</p>
          </div>
        </div>
      </div>

      {/* Control bar */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex flex-wrap items-center gap-3">
          <div
            className="inline-flex rounded-md border border-gray-200 bg-gray-50 p-0.5 text-xs"
            role="group"
            aria-label="Dataset"
          >
            {Object.values(DATASETS).map((option) => (
              <button
                key={option.id}
                onClick={() => chooseDataset(option.id)}
                aria-pressed={dataset === option.id}
                className={`px-2.5 py-1 rounded font-medium transition ${
                  dataset === option.id
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

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
              onClick={() => exportAllData(dataset)}
              className="inline-flex items-center px-3 py-1.5 rounded-md border border-gray-200 text-gray-700 font-semibold text-[13px] hover:bg-gray-50 transition"
            >
              <IconDownload size={15} className="mr-1.5" />
              Export sample
            </button>

            <a
              href={fullDataUrl(selectedYear, dataset)}
              className="inline-flex items-center px-3 py-1.5 rounded-md bg-primary-600 text-white font-semibold text-[13px] hover:bg-primary-700 transition"
              title={`Download the complete ${selectedYear} ${datasetInfo.label} comparison (all ${currentYearData.summary.totalRecords.toLocaleString()} records)`}
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
          datasetLabel={datasetInfo.label}
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
