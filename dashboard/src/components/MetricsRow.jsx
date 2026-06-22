'use client';

import React from 'react';
import { getBarColor, getBarBg, getBandLabel } from '../utils/colors';
import { TOLERANCE_MODES } from '../constants';

const MetricCard = React.memo(({ label, value, type, description }) => {
  const numericValue = parseFloat(value);
  const isPercentage = type !== 'total';
  const color = isPercentage ? getBarColor(numericValue) : '#0C2426';

  return (
    <div className="relative bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Calibration accent: band-colored rule for rates, brand teal for the count */}
      <div
        className="h-1 w-full"
        style={{ background: isPercentage ? color : '#2C7A7B' }}
      />
      <div className="p-5">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-500">
            {label}
          </span>
          {isPercentage && (
            <span
              className="text-[10px] font-semibold uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-full"
              style={{ color, background: getBarBg(numericValue) }}
            >
              {getBandLabel(numericValue)}
            </span>
          )}
        </div>

        <div className="mt-2 flex items-baseline gap-1">
          <span
            className="tnum font-mono font-semibold leading-none"
            style={{ fontSize: '2rem', color }}
          >
            {isPercentage ? Number(value).toFixed(1) : Number(value).toLocaleString()}
          </span>
          {isPercentage && (
            <span className="tnum font-mono text-base font-medium" style={{ color }}>
              %
            </span>
          )}
        </div>

        {isPercentage && (
          <div
            className="h-1.5 rounded-full mt-3 overflow-hidden"
            style={{ background: getBarBg(numericValue) }}
          >
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.min(numericValue, 100)}%`, background: color }}
            />
          </div>
        )}

        {description && (
          <div className="text-[11px] text-gray-400 mt-2.5">{description}</div>
        )}
      </div>
    </div>
  );
});

MetricCard.displayName = 'MetricCard';

const MetricsRow = React.memo(({ data, selectedState, toleranceMode = TOLERANCE_MODES.ABSOLUTE }) => {
  if (!data || !data.summary) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
            <div className="h-3 bg-gray-200 rounded w-3/5 mb-4" />
            <div className="h-10 bg-gray-200 rounded w-2/5" />
          </div>
        ))}
      </div>
    );
  }

  const { summary } = data;
  const isRel = toleranceMode === TOLERANCE_MODES.RELATIVE;

  let displayData = {
    totalRecords: summary.totalRecords,
    federalMatchPct: isRel
      ? summary.federalMatchPctRel ?? summary.federalMatchPct
      : summary.federalMatchPct,
    stateMatchPct: isRel
      ? summary.stateMatchPctRel ?? summary.stateMatchPct
      : summary.stateMatchPct,
  };

  if (selectedState && summary.stateBreakdown) {
    const stateData = summary.stateBreakdown.find(
      (state) => state.state === selectedState
    );
    if (stateData) {
      displayData = {
        totalRecords: stateData.households,
        federalMatchPct: isRel
          ? stateData.federalPctRel ?? stateData.federalPct
          : stateData.federalPct,
        stateMatchPct: isRel
          ? stateData.statePctRel ?? stateData.statePct
          : stateData.statePct,
      };
    }
  }

  const toleranceLabel = isRel
    ? 'Within ±1% of gross income'
    : 'Within ±$15';

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      <MetricCard
        label={selectedState ? `${selectedState} households` : 'Households compared'}
        value={displayData.totalRecords}
        type="total"
        description={selectedState ? 'In this state' : 'Full eCPS, both engines'}
      />
      <MetricCard
        label="Federal agreement"
        value={displayData.federalMatchPct.toFixed(1)}
        type="federal"
        description={toleranceLabel}
      />
      <MetricCard
        label="State agreement"
        value={displayData.stateMatchPct.toFixed(1)}
        type="state"
        description={toleranceLabel}
      />
    </div>
  );
});

MetricsRow.displayName = 'MetricsRow';

export default MetricsRow;
