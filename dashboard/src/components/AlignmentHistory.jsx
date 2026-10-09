'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  loadAlignmentHistory,
  releaseSeries,
  referenceOptions,
  percentScale,
  pairLabel,
  triggerLabel,
  formatChange,
  formatDate,
  round1,
} from '@/utils/alignmentHistory';
import { TOLERANCE_MODES } from '@/constants';

// Validated with the dataviz palette checker (light surface): CVD ΔE 22,
// normal-vision ΔE 31, both >= 3:1 against the surface.
export const SERIES = [
  { key: 'federal', label: 'Federal', color: '#0D9488' },
  { key: 'state', label: 'State', color: '#6D28D9' },
];

const TOLERANCE_TEXT = {
  [TOLERANCE_MODES.ABSOLUTE]: 'within ±$15',
  [TOLERANCE_MODES.RELATIVE]: 'within ±1% of income',
  [TOLERANCE_MODES.RELATIVE_NET]: 'within ±1% of income, one-time state rebates netted out',
};

const TABLE_ROWS = 12;
const HEIGHT = 260;
const MARGIN = { top: 16, right: 96, bottom: 32, left: 44 };

function useWidth(ref, fallback = 720) {
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width) setWidth(entry.contentRect.width);
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

const monthTicks = (start, end) => {
  const ticks = [];
  const d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  while (d <= end) {
    ticks.push(new Date(d));
    d.setUTCMonth(d.getUTCMonth() + 1);
  }
  return ticks;
};

const pct = (value) => (value == null ? '—' : `${round1(value).toFixed(1)}%`);

function ReleaseChart({ points, title }) {
  const box = useRef(null);
  const width = useWidth(box);
  const [active, setActive] = useState(null);
  const plotW = Math.max(120, width - MARGIN.left - MARGIN.right);
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom;

  const times = points.map((p) => p.date.getTime());
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const span = Math.max(t1 - t0, 24 * 3600 * 1000);
  const x = (t) => MARGIN.left + (points.length === 1 ? plotW / 2 : ((t - t0) / span) * plotW);
  const scale = percentScale(points.flatMap((p) => [p.federal, p.state]));
  const y = (v) => MARGIN.top + (1 - (v - scale.min) / (scale.max - scale.min)) * plotH;
  const xs = points.map((p) => x(p.date.getTime()));

  const nearest = (px) => {
    let best = 0;
    xs.forEach((value, i) => {
      if (Math.abs(value - px) < Math.abs(xs[best] - px)) best = i;
    });
    return best;
  };

  const onMove = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const scaleX = width / rect.width;
    setActive(nearest((event.clientX - rect.left) * scaleX));
  };

  const onKey = (event) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const step = event.key === 'ArrowRight' ? 1 : -1;
      setActive((i) => Math.max(0, Math.min(points.length - 1, (i ?? points.length - 1) + step)));
    } else if (event.key === 'Escape') {
      setActive(null);
    }
  };

  const last = points[points.length - 1];
  const endLabels = SERIES.map((s) => ({ ...s, y: y(last[s.key]), value: last[s.key] }));
  // Direct end labels only when they don't collide; the legend always names the lines.
  const showEndLabels = Math.abs(endLabels[0].y - endLabels[1].y) >= 14;
  const point = active == null ? null : points[active];
  const tipLeft = point ? Math.min(Math.max(xs[active] + 12, 0), width - 260) : 0;

  return (
    <div ref={box} className="relative">
      <svg
        role="img"
        aria-label={title}
        tabIndex={0}
        width={width}
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        className="block w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded"
        onPointerMove={onMove}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive((i) => i ?? points.length - 1)}
        onBlur={() => setActive(null)}
        onKeyDown={onKey}
      >
        {scale.ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={MARGIN.left}
              x2={MARGIN.left + plotW}
              y1={y(tick)}
              y2={y(tick)}
              stroke="#E2E8F0"
              strokeWidth="1"
            />
            <text
              x={MARGIN.left - 8}
              y={y(tick)}
              dy="0.32em"
              textAnchor="end"
              className="fill-gray-500 text-[11px] tnum"
            >
              {tick}%
            </text>
          </g>
        ))}
        {monthTicks(new Date(t0), new Date(t0 + span)).map((tick) => (
          <text
            key={tick.toISOString()}
            x={x(tick.getTime())}
            y={HEIGHT - 10}
            textAnchor="middle"
            className="fill-gray-500 text-[11px]"
          >
            {tick.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}
            {tick.getUTCMonth() === 0 ? ` ${tick.getUTCFullYear()}` : ''}
          </text>
        ))}
        {point && (
          <line
            x1={xs[active]}
            x2={xs[active]}
            y1={MARGIN.top}
            y2={MARGIN.top + plotH}
            stroke="#94A3B8"
            strokeWidth="1"
          />
        )}
        {SERIES.map((s) => (
          <g key={s.key}>
            <polyline
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
              points={points.map((p, i) => `${xs[i]},${y(p[s.key])}`).join(' ')}
            />
            {points.map((p, i) => (
              <circle
                key={p.row.id}
                cx={xs[i]}
                cy={y(p[s.key])}
                r={i === active ? 5 : 4}
                fill={s.color}
                stroke="#FFFFFF"
                strokeWidth="2"
              />
            ))}
          </g>
        ))}
        {showEndLabels &&
          endLabels.map((s) => (
            <text
              key={s.key}
              x={xs[xs.length - 1] + 10}
              y={s.y}
              dy="0.32em"
              className="fill-gray-700 text-[12px] font-medium"
            >
              {s.label} {pct(s.value)}
            </text>
          ))}
      </svg>
      {point && (
        <div
          role="status"
          className="pointer-events-none absolute top-2 z-10 w-[248px] rounded-lg border border-gray-200 bg-white p-3 text-xs shadow-md"
          style={{ left: tipLeft }}
        >
          <div className="text-gray-500">{formatDate(point.date)}</div>
          <div className="mt-0.5 font-mono text-[11px] text-gray-700">
            policyengine-taxsim {point.row.policyengineTaxsimVersion}
            <br />
            policyengine-us {point.row.policyengineUsVersion}
          </div>
          <div className="mt-2 space-y-1">
            {SERIES.map((s) => (
              <div key={s.key} className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} />
                <span className="tnum font-semibold text-gray-900">{pct(point[s.key])}</span>
                <span className="text-gray-500">{s.label}</span>
                <span className="tnum ml-auto text-gray-500">
                  {formatChange(point[`${s.key}Change`])}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-gray-400">
            {point.records.toLocaleString()} households
          </div>
        </div>
      )}
    </div>
  );
}

export default function AlignmentHistory({ selectedYear, selectedState, toleranceMode }) {
  const [doc, setDoc] = useState(undefined);
  const [error, setError] = useState(null);
  const [reference, setReference] = useState(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let live = true;
    loadAlignmentHistory()
      .then((data) => live && setDoc(data))
      .catch((err) => live && setError(err.message));
    return () => {
      live = false;
    };
  }, []);

  const references = useMemo(() => referenceOptions(doc), [doc]);
  const activeReference = reference ?? references[0];
  const series = useMemo(
    () =>
      doc && activeReference
        ? releaseSeries(doc, {
            reference: activeReference,
            year: selectedYear,
            state: selectedState,
            mode: toleranceMode,
          })
        : { points: [], unmeasured: [] },
    [doc, activeReference, selectedYear, selectedState, toleranceMode]
  );

  const meta = doc?.references?.[activeReference];
  const yearMeta = meta?.years?.[String(selectedYear)];
  const where = selectedState ? `${selectedState} households` : 'all households';
  const tolerance = TOLERANCE_TEXT[toleranceMode] ?? TOLERANCE_TEXT[TOLERANCE_MODES.RELATIVE];
  const newestFirst = [...series.points].reverse();
  const tableRows = showAll ? newestFirst : newestFirst.slice(0, TABLE_ROWS);

  return (
    <section className="mt-10" aria-labelledby="alignment-history-heading">
      <div className="mb-4">
        <div className="font-mono text-[11px] tracking-[0.18em] uppercase text-gray-400">
          By release
        </div>
        <h2
          id="alignment-history-heading"
          className="mt-1 text-2xl font-bold text-secondary-900 tracking-tight"
        >
          Agreement by release
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-gray-500">
          Each point is a released policyengine-taxsim and policyengine-us pair, installed
          as PyPI stood when it came out and scored against the same TAXSIM run: share of{' '}
          {where} {tolerance}, tax year {selectedYear}. TAXSIM does not change between
          points, so a move comes from the emulator or the model.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">Could not load the release history: {error}</p>}

      {doc === undefined && !error && (
        <div className="h-[260px] animate-pulse rounded-xl border border-gray-200 bg-white" />
      )}

      {doc !== undefined && !error && series.points.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No release has been scored for {selectedYear} yet. A workflow scores each new
          release after it is published and adds it here.
        </div>
      )}

      {series.points.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-gray-600">
            {SERIES.map((s) => (
              <span key={s.key} className="inline-flex items-center gap-1.5">
                <span className="inline-block h-0.5 w-4 rounded" style={{ background: s.color }} />
                {s.label} income tax
              </span>
            ))}
            <span className="text-gray-400">
              {series.points.length} release pairs scored
              {series.unmeasured.length > 0 && ` · ${series.unmeasured.length} not scored`}
            </span>
            {references.length > 1 && (
              <label className="ml-auto inline-flex items-center gap-2">
                TAXSIM reference
                <select
                  className="rounded border border-gray-200 bg-white px-2 py-1 font-mono text-[11px]"
                  value={activeReference}
                  onChange={(event) => setReference(event.target.value)}
                >
                  {references.map((id) => (
                    <option key={id} value={id}>
                      {id}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <ReleaseChart
            points={series.points}
            title={`Federal and state agreement with TAXSIM by release, ${selectedYear}, ${where}`}
          />
          <p className="mt-1 text-[11px] text-gray-400">
            Hover, or focus the chart and use the arrow keys, to read a release.
          </p>
        </div>
      )}

      {series.points.length > 0 && (
        <div className="mt-5 overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <caption className="sr-only">
              Agreement with TAXSIM by release, {selectedYear}, {where}, {tolerance}
            </caption>
            <thead className="bg-gray-50 text-left text-[11px] uppercase tracking-[0.08em] text-gray-500">
              <tr>
                <th className="px-4 py-2 font-semibold">Released</th>
                <th className="px-4 py-2 font-semibold">policyengine-taxsim</th>
                <th className="px-4 py-2 font-semibold">policyengine-us</th>
                <th className="px-4 py-2 text-right font-semibold">Federal</th>
                <th className="px-4 py-2 text-right font-semibold">Change</th>
                <th className="px-4 py-2 text-right font-semibold">State</th>
                <th className="px-4 py-2 text-right font-semibold">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tableRows.map((p) => (
                <tr key={p.row.id} title={`New with ${triggerLabel(p.row)}`}>
                  <td className="px-4 py-2 text-gray-600 tnum">{formatDate(p.date)}</td>
                  <td className="px-4 py-2 font-mono text-[12px]">{p.row.policyengineTaxsimVersion}</td>
                  <td className="px-4 py-2 font-mono text-[12px]">{p.row.policyengineUsVersion}</td>
                  <td className="px-4 py-2 text-right tnum font-medium">{pct(p.federal)}</td>
                  <td className="px-4 py-2 text-right tnum text-gray-500">
                    {formatChange(p.federalChange)}
                  </td>
                  <td className="px-4 py-2 text-right tnum font-medium">{pct(p.state)}</td>
                  <td className="px-4 py-2 text-right tnum text-gray-500">
                    {formatChange(p.stateChange)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {newestFirst.length > TABLE_ROWS && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="w-full border-t border-gray-100 px-4 py-2 text-sm font-semibold text-primary-700 hover:bg-gray-50"
            >
              {showAll ? 'Show the newest releases' : `Show all ${newestFirst.length} releases`}
            </button>
          )}
        </div>
      )}

      {series.unmeasured.length > 0 && (
        <details className="mt-4 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm">
          <summary className="cursor-pointer font-semibold text-gray-700">
            {series.unmeasured.length} releases not scored for {selectedYear}
          </summary>
          <p className="mt-2 text-gray-500">
            PyPI no longer serves every release: older ones have been deleted, and some
            failed to publish. These pairs are listed rather than scored with a substitute.
          </p>
          <ul className="mt-2 divide-y divide-gray-100">
            {[...series.unmeasured].reverse().map(({ row, reason }) => (
              <li key={row.id} className="flex flex-wrap gap-x-4 py-1.5">
                <span className="tnum text-gray-500">{(row.releasedAt || '').slice(0, 10)}</span>
                <span className="font-mono text-[12px]">{pairLabel(row)}</span>
                <span className="text-gray-500">{reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {meta && (
        <p className="mt-3 text-[11px] text-gray-400">
          TAXSIM reference: the TAXSIM side of{' '}
          <a className="underline" href={meta.url}>
            {meta.release}
          </a>
          {yearMeta?.taxsimBinaryBuild && <> (build {yearMeta.taxsimBinaryBuild}</>}
          {yearMeta?.taxsimFallback?.states && (
            <>
              ; {yearMeta.taxsimFallback.states.join(' and ')} from build{' '}
              {yearMeta.taxsimFallback.taxsimBinaryBuild || 'previous'}
            </>
          )}
          {yearMeta?.taxsimBinaryBuild && ')'}.{' '}
          <a
            className="underline"
            href="https://github.com/PolicyEngine/policyengine-taxsim/blob/main/docs/alignment-history.md"
          >
            How releases are scored
          </a>
          .
        </p>
      )}
    </section>
  );
}
