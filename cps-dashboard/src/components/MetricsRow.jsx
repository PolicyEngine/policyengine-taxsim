import React from 'react';

const MetricCard = React.memo(({ title, value, type, description }) => {
  const numericValue = parseFloat(value);
  const isPercentage = type !== 'total';

  const getBarColor = (pct) => {
    if (pct >= 90) return 'var(--green)';
    if (pct >= 70) return 'var(--teal-accent)';
    return 'var(--dark-red)';
  };

  const getBarBg = (pct) => {
    if (pct >= 90) return 'rgba(34, 197, 94, 0.1)';
    if (pct >= 70) return 'rgba(56, 178, 172, 0.1)';
    return 'rgba(239, 68, 68, 0.1)';
  };

  return (
    <div className="dash-metric-card">
      <div className="dash-metric-label">{title}</div>
      <div className="dash-metric-value" style={isPercentage ? { color: getBarColor(numericValue) } : {}}>
        {isPercentage ? `${value}%` : Number(value).toLocaleString()}
      </div>
      {isPercentage && (
        <div className="dash-metric-bar-track" style={{ background: getBarBg(numericValue) }}>
          <div
            className="dash-metric-bar-fill"
            style={{
              width: `${Math.min(numericValue, 100)}%`,
              background: getBarColor(numericValue),
            }}
          />
        </div>
      )}
      {description && <div className="dash-metric-desc">{description}</div>}
    </div>
  );
});

MetricCard.displayName = 'MetricCard';

const MetricsRow = React.memo(({ data, selectedState }) => {
  if (!data || !data.summary) {
    return (
      <div className="dash-metrics-row">
        {[1, 2, 3].map((i) => (
          <div key={i} className="dash-metric-card animate-pulse">
            <div style={{ height: 14, background: 'var(--blue-95)', borderRadius: 4, width: '60%', marginBottom: 12 }} />
            <div style={{ height: 32, background: 'var(--blue-95)', borderRadius: 4, width: '40%' }} />
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
    <div className="dash-metrics-row">
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
