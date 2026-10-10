import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  rate,
  round1,
  countsFor,
  countKeys,
  releaseSeries,
  percentScale,
  formatChange,
  referenceOptions,
  dashboardReference,
} from '../alignmentHistory';
import { TOLERANCE_MODES } from '../../constants';

const STATES = ['AL', 'AK', 'AZ', 'AR', 'CA'];
const COUNTS = [
  'federalMatches',
  'stateMatches',
  'federalMatchesRel',
  'stateMatchesRel',
  'stateMatchesRelNet',
];
const MODES = Object.values(TOLERANCE_MODES);

// A measured year whose counts reconcile by construction: per-state matches
// never exceed that state's households, and totals are the per-state sums.
const yearEntry = fc
  .array(fc.integer({ min: 0, max: 500 }), { minLength: STATES.length, maxLength: STATES.length })
  .filter((households) => households.some((h) => h > 0))
  .chain((households) =>
    fc
      .tuple(
        ...COUNTS.map(() =>
          fc.tuple(...households.map((h) => fc.integer({ min: 0, max: h })))
        )
      )
      .map((columns) => {
        const byState = { households };
        const entry = { status: 'measured', records: households.reduce((a, b) => a + b, 0) };
        COUNTS.forEach((name, i) => {
          byState[name] = columns[i];
          entry[name] = columns[i].reduce((a, b) => a + b, 0);
        });
        return { ...entry, byState };
      })
  );

const docWith = (entries) => ({
  states: STATES,
  references: { ref: { release: 'ref', years: {} } },
  rows: entries.map((entry, i) => ({
    id: `taxsim-1.${i}+us-2.${i}@ref`,
    policyengineTaxsimVersion: `1.${i}`,
    policyengineUsVersion: `2.${i}`,
    reference: 'ref',
    releasedAt: new Date(Date.UTC(2026, 6, 1 + i)).toISOString(),
    status: entry ? 'measured' : 'not-installable',
    reason: entry ? undefined : 'policyengine-us 2.0 is not on PyPI',
    years: entry ? { 2023: entry } : undefined,
  })),
});

describe('rates', () => {
  it('stay within 0–100% and are a count over its households', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 200000 }), fc.double({ min: 0, max: 1, noNaN: true }), (n, share) => {
        const count = Math.floor(share * n);
        const value = rate(count, n);
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(100);
        expect(value).toBeCloseTo((100 * count) / n, 9);
      })
    );
    expect(rate(0, 0)).toBeNull();
  });

  it('reconcile: state counts add up to the overall counts in every mode', () => {
    fc.assert(
      fc.property(yearEntry, fc.constantFrom(...MODES), (entry, mode) => {
        const doc = docWith([entry]);
        const overall = countsFor(doc, entry, { mode });
        const states = STATES.map((state) => countsFor(doc, entry, { state, mode }));
        const sum = (key) => states.reduce((a, s) => a + s[key], 0);
        expect(sum('records')).toBe(overall.records);
        expect(sum('federal')).toBe(overall.federal);
        expect(sum('state')).toBe(overall.state);
        states.forEach((s) => {
          expect(s.federal).toBeLessThanOrEqual(s.records);
          expect(s.state).toBeLessThanOrEqual(s.records);
        });
      })
    );
  });

  it('net of rebates changes only the state count', () => {
    expect(countKeys(TOLERANCE_MODES.RELATIVE_NET)).toEqual({
      federal: 'federalMatchesRel',
      state: 'stateMatchesRelNet',
    });
    expect(countKeys(TOLERANCE_MODES.ABSOLUTE).federal).toBe('federalMatches');
  });
});

describe('releaseSeries', () => {
  it('splits rows into scored and unscored, and changes telescope', () => {
    fc.assert(
      fc.property(
        fc.array(fc.option(yearEntry, { nil: null }), { minLength: 1, maxLength: 12 }),
        fc.constantFrom(...MODES),
        fc.option(fc.constantFrom(...STATES), { nil: null }),
        (entries, mode, state) => {
          const doc = docWith(entries);
          const { points, unmeasured } = releaseSeries(doc, { reference: 'ref', year: 2023, state, mode });
          expect(points.length + unmeasured.length).toBe(entries.length);
          for (let i = 1; i < points.length; i += 1) {
            expect(points[i].date >= points[i - 1].date).toBe(true);
          }
          if (points.length > 1) {
            const total = points.slice(1).reduce((a, p) => a + p.federalChange, 0);
            expect(total).toBeCloseTo(points[points.length - 1].federal - points[0].federal, 6);
          }
          points.forEach((p) => {
            expect(p.federal).toBeGreaterThanOrEqual(0);
            expect(p.state).toBeLessThanOrEqual(100);
          });
          unmeasured.forEach((u) => expect(u.reason).toBeTruthy());
        }
      )
    );
  });

  it('ignores rows scored against another reference', () => {
    const doc = docWith([null]);
    expect(releaseSeries(doc, { reference: 'other', year: 2023, mode: 'relative' }).unmeasured).toHaveLength(0);
  });
});

describe('percentScale', () => {
  it('covers every value with clean, increasing ticks inside 0–100%', () => {
    fc.assert(
      fc.property(fc.array(fc.double({ min: 0, max: 100, noNaN: true }), { minLength: 1, maxLength: 50 }), (values) => {
        const { min, max, ticks } = percentScale(values);
        expect(min).toBeGreaterThanOrEqual(0);
        expect(max).toBeLessThanOrEqual(100);
        expect(min).toBeLessThan(max);
        values.forEach((v) => {
          expect(v).toBeGreaterThanOrEqual(min - 1e-9);
          expect(v).toBeLessThanOrEqual(max + 1e-9);
        });
        expect(ticks[0]).toBe(min);
        expect(ticks[ticks.length - 1]).toBeCloseTo(max, 6);
        ticks.slice(1).forEach((t, i) => expect(t).toBeGreaterThan(ticks[i]));
      })
    );
  });
});

describe('formatting', () => {
  it('signs changes and rounds to a tenth', () => {
    expect(formatChange(0.04)).toBe('0.0');
    expect(formatChange(1.26)).toBe('+1.3');
    expect(formatChange(-0.35)).toBe('−0.3');
    expect(formatChange(null)).toBe('—');
  });

  it('lists the dashboard reference first', () => {
    const own = dashboardReference();
    expect(referenceOptions({ references: { zzz: {}, [own]: {} } })).toEqual([own, 'zzz']);
  });
});

// Differential: the published counts the history file records for its
// reference, turned into rates here, equal the rates the dashboard refresh
// (Python) wrote into each year's summary.
// Vitest runs from dashboard/ (jsdom gives import.meta.url no file: scheme).
const dataPath = (...parts) => join(process.cwd(), 'public', 'data', ...parts);
const historyPath = dataPath('alignment_history.json');
const summaryPath = (year) => dataPath(String(year), `summary_${year}.json`);

describe.runIf(existsSync(historyPath))('committed alignment history', () => {
  const doc = JSON.parse(readFileSync(historyPath, 'utf8'));

  it('reproduces each year summary from the reference counts', () => {
    const meta = doc.references[dashboardReference()];
    expect(meta).toBeTruthy();
    for (const [year, entry] of Object.entries(meta.years)) {
      const summary = JSON.parse(readFileSync(summaryPath(year), 'utf8'));
      const p = entry.published;
      expect(p.records).toBe(summary.totalRecords);
      expect(round1(rate(p.federalMatchesRel, p.records))).toBe(summary.federalMatchPctRel);
      expect(round1(rate(p.stateMatchesRel, p.records))).toBe(summary.stateMatchPctRel);
      expect(round1(rate(p.stateMatchesRelNet, p.records))).toBe(summary.stateMatchPctRelNet);
      expect(round1(rate(p.federalMatches, p.records))).toBe(summary.federalMatchPct);
      expect(round1(rate(p.stateMatches, p.records))).toBe(summary.stateMatchPct);
    }
  });

  it('has counts that reconcile in every measured year', () => {
    for (const row of doc.rows) {
      for (const entry of Object.values(row.years || {})) {
        if (entry.status !== 'measured') continue;
        for (const mode of MODES) {
          const overall = countsFor(doc, entry, { mode });
          const states = doc.states.map((state) => countsFor(doc, entry, { state, mode }));
          expect(states.reduce((a, s) => a + s.records, 0)).toBe(overall.records);
          expect(states.reduce((a, s) => a + s.federal, 0)).toBe(overall.federal);
          expect(states.reduce((a, s) => a + s.state, 0)).toBe(overall.state);
        }
      }
    }
  });
});
