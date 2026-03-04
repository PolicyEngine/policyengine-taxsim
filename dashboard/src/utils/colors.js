/** Color helpers for percentage-based progress bars */
export const getBarColor = (pct) => {
  if (pct >= 90) return '#22c55e';
  if (pct >= 70) return '#38b2ac';
  return '#ef4444';
};

export const getBarBg = (pct) => {
  if (pct >= 90) return 'rgba(34, 197, 94, 0.1)';
  if (pct >= 70) return 'rgba(56, 178, 172, 0.1)';
  return 'rgba(239, 68, 68, 0.1)';
};
