'use client';

import React from 'react';
import { getBarColor, getBarBg } from '../utils/colors';

const MetricCard = React.memo(({ title, value, type, description }) => {
  const numericValue = parseFloat(value);
  const isPercentage = type !== 'total';

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-7">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</div>
      <div className="text-3xl font-bold mt-2" style={isPercentage ? { color: getBarColor(numericValue) } : {}}>
        {isPercentage ? `${value}%` : Number(value).toLocaleString()}
      </div>
      {isPercentage && (
        <div className="h-2 rounded-full mt-3" style={{ background: getBarBg(numericValue) }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.min(numericValue, 100)}%`,
              background: getBarColor(numericValue),
            }}
          />
        </div>
      )}
      {description && <div className="text-xs text-gray-400 mt-2">{description}</div>}
    </div>
  );
});

MetricCard.displayName = 'MetricCard';

const MetricsRow = React.memo(({ data, selectedState }) => {
  if (!data || !data.summary) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-lg shadow-sm border border-gray-200 p-7 animate-pulse">
            <div className="h-3.5 bg-gray-200 rounded w-3/5 mb-3" />
            <div className="h-8 bg-gray-200 rounded w-2/5" />
          </div>
        ))}
      </div>
    );
  }

  const { summary } = data;
  let displayData = summary;

  if (selectedState && summary.stateBreakdown) {
    const stateData = summary.stateBreakdown.find(
      (state) => state.state === selectedState
    );
    if (stateData) {
      displayData = {
        totalRecords: stateData.households,
        federalMatchPct: stateData.federalPct,
        stateMatchPct: stateData.statePct,
      };
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
      <MetricCard
        title="Total Records"
        value={displayData.totalRecords}
        type="total"
        description={selectedState ? `Households in ${selectedState}` : 'All households processed'}
      />
      <MetricCard
        title="Federal Match Rate"
        value={displayData.federalMatchPct.toFixed(1)}
        type="federal"
        description="Within ±$15 tolerance"
      />
      <MetricCard
        title="State Match Rate"
        value={displayData.stateMatchPct.toFixed(1)}
        type="state"
        description="Within ±$15 tolerance"
      />
    </div>
  );
});

MetricsRow.displayName = 'MetricsRow';

export default MetricsRow;
