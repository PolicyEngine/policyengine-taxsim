import { TOLERANCE_MODES, FULL_DATA_RELEASE_BASE } from '../constants';
import { assetUrl } from './basePath';

/**
 * Agreement with TAXSIM, release by release.
 *
 * public/data/alignment_history.json (written by
 * scripts/alignment_history.py) holds counts only: for each released
 * policyengine-taxsim / policyengine-us pair and tax year, how many households
 * agree with the TAXSIM reference at each tolerance, overall and by state. A
 * rate is always a count over its households, computed here.
 */

export const HISTORY_URL = '/data/alignment_history.json';

// The count each tolerance mode reads, matching the summary's rate names:
// unsuffixed is within $15, Rel within 1% of income, RelNet nets out one-time
// state rebates (federal tax has no rebates, so it uses Rel).
const COUNT_KEYS = {
  [TOLERANCE_MODES.ABSOLUTE]: { federal: 'federalMatches', state: 'stateMatches' },
  [TOLERANCE_MODES.RELATIVE]: { federal: 'federalMatchesRel', state: 'stateMatchesRel' },
  [TOLERANCE_MODES.RELATIVE_NET]: {
    federal: 'federalMatchesRel',
    state: 'stateMatchesRelNet',
  },
};

export const countKeys = (mode) => COUNT_KEYS[mode] ?? COUNT_KEYS[TOLERANCE_MODES.RELATIVE];

/** Percent of households, unrounded; null when there are none. */
export const rate = (count, records) => (records > 0 ? (100 * count) / records : null);

/** Rounded to one decimal the way the refresh rounds its summaries. */
export const round1 = (value) => (value == null ? null : Math.round(value * 10) / 10);

export const loadAlignmentHistory = async () => {
  const response = await fetch(assetUrl(HISTORY_URL));
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Failed to load ${HISTORY_URL}: ${response.status}`);
  return response.json();
};

/** The release tag the dashboard's full-data links point at. */
export const dashboardReference = () => FULL_DATA_RELEASE_BASE.split('/').pop();

/**
 * Counts for one year of one row, overall or for one state.
 * Returns { records, federal, state } or null when the year wasn't measured.
 */
export const countsFor = (doc, entry, { state = null, mode } = {}) => {
  if (!entry || entry.status !== 'measured') return null;
  const keys = countKeys(mode);
  if (!state) {
    return { records: entry.records, federal: entry[keys.federal], state: entry[keys.state] };
  }
  const i = (doc.states || []).indexOf(state);
  if (i < 0) return null;
  const by = entry.byState;
  return {
    records: by.households[i],
    federal: by[keys.federal][i],
    state: by[keys.state][i],
  };
};

/** "policyengine-taxsim 3.1.1 · policyengine-us 2.36.0" — the --version labels. */
export const pairLabel = (row) =>
  `policyengine-taxsim ${row.policyengineTaxsimVersion} · policyengine-us ${row.policyengineUsVersion}`;

/** Which release made this pair the one a new install got. */
export const triggerLabel = (row) => {
  const triggers = row.triggers || [];
  if (!triggers.length) return '';
  return triggers.map((t) => `${t.package} ${t.version}`).join(', ');
};

/**
 * The rows for one reference, with each one's agreement for a year.
 *
 * points: measured rows, oldest first, with federal/state rates and the change
 *   since the previous measured row.
 * unmeasured: rows with no measurement for that year (not installable, failed
 *   to install, or the year failed), each with its reason.
 */
export const releaseSeries = (doc, { reference, year, state = null, mode }) => {
  const rows = (doc?.rows || []).filter((row) => row.reference === reference);
  const points = [];
  const unmeasured = [];
  for (const row of rows) {
    const entry = row.years?.[String(year)];
    const counts = countsFor(doc, entry, { state, mode });
    if (!counts || !counts.records) {
      unmeasured.push({
        row,
        reason: row.reason || entry?.reason || `No ${year} measurement`,
        status: entry?.status || row.status,
      });
      continue;
    }
    points.push({
      row,
      date: new Date(row.releasedAt || row.generatedAt),
      records: counts.records,
      federalMatches: counts.federal,
      stateMatches: counts.state,
      federal: rate(counts.federal, counts.records),
      state: rate(counts.state, counts.records),
    });
  }
  points.forEach((point, i) => {
    const prev = points[i - 1];
    point.federalChange = prev ? point.federal - prev.federal : null;
    point.stateChange = prev ? point.state - prev.state : null;
  });
  return { points, unmeasured };
};

/** References in the file, the dashboard's own first. */
export const referenceOptions = (doc) => {
  const own = dashboardReference();
  const ids = Object.keys(doc?.references || {});
  return [...ids.filter((id) => id === own), ...ids.filter((id) => id !== own)];
};

/** Clean y-axis bounds and ticks (whole percents) around the plotted rates. */
export const percentScale = (values, { minSpan = 10, step = null } = {}) => {
  const finite = values.filter((v) => Number.isFinite(v));
  if (!finite.length) return { min: 0, max: 100, ticks: [0, 25, 50, 75, 100] };
  let lo = Math.min(...finite);
  let hi = Math.max(...finite);
  if (hi - lo < minSpan) {
    const pad = (minSpan - (hi - lo)) / 2;
    lo -= pad;
    hi += pad;
  }
  const span = hi - lo;
  const tick = step ?? (span > 40 ? 10 : span > 20 ? 5 : 2);
  let min = Math.max(0, Math.floor(lo / tick) * tick);
  let max = Math.min(100, Math.ceil(hi / tick) * tick);
  if (max - min < tick) {
    if (max < 100) max = Math.min(100, min + tick);
    else min = Math.max(0, max - tick);
  }
  const ticks = [];
  for (let v = min; v <= max + 1e-9; v += tick) ticks.push(Math.round(v * 1e6) / 1e6);
  return { min, max, ticks };
};

export const formatChange = (value) => {
  if (value == null || !Number.isFinite(value)) return '—';
  const rounded = round1(value);
  if (rounded === 0) return '0.0';
  return `${rounded > 0 ? '+' : '−'}${Math.abs(rounded).toFixed(1)}`;
};

export const formatDate = (date) =>
  date instanceof Date && !Number.isNaN(date.getTime())
    ? date.toISOString().slice(0, 10)
    : '';
