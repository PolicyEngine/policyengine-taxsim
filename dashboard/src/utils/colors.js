/**
 * Calibration scale for agreement between PolicyEngine and TAXSIM.
 * Four bands, brand-teal at the confident end and coral at divergence, so the
 * handful of states that genuinely diverge stand out instead of blending into
 * a wall of near-identical greens.
 */
const BANDS = [
  { min: 95, color: '#0E9384', track: 'rgba(14, 147, 132, 0.12)', label: 'Strong' },
  { min: 85, color: '#15B79E', track: 'rgba(21, 183, 158, 0.12)', label: 'Good' },
  { min: 70, color: '#E0A800', track: 'rgba(224, 168, 0, 0.14)', label: 'Watch' },
  { min: 0, color: '#E5484D', track: 'rgba(229, 72, 77, 0.12)', label: 'Diverges' },
];

export const getBand = (pct) =>
  BANDS.find((b) => pct >= b.min) ?? BANDS[BANDS.length - 1];

export const getBarColor = (pct) => getBand(pct).color;
export const getBarBg = (pct) => getBand(pct).track;
export const getBandLabel = (pct) => getBand(pct).label;
