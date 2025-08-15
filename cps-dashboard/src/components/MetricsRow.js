import React from 'react';

const MetricCard = ({ title, value, type, description }) => {
  const getPercentageClass = (percentage) => {
    if (percentage >= 80) return 'percentage-good';
    if (percentage >= 60) return 'percentage-warning';
    return 'percentage-poor';
  };

  return (
    <div className={`metric-card ${type}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className={`text-2xl font-bold ${
            type !== 'total' ? getPercentageClass(parseFloat(value)) : 'text-gray-900'
          }`}>
            {value}{type !== 'total' ? '%' : ''}
          </p>
          {description && (
            <p className="text-xs text-gray-500 mt-1">{description}</p>
          )}
        </div>
      </div>
    </div>
  );
};

const MetricsRow = ({ data, selectedState }) => {
  if (!data || !data.summary) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="metric-card total animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-8 bg-gray-200 rounded w-1/2"></div>
          </div>
        ))}
      </div>
    );
  }

  const { summary } = data;
  let displayData = summary;

  // Filter data by state if selected
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
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
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
};

export default MetricsRow;
