import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import AlignmentHistory, { timeTicks } from '../AlignmentHistory';
import { dashboardReference } from '../../utils/alignmentHistory';
import { TOLERANCE_MODES } from '../../constants';

// A hand-built fixture for the component test only: three states, two scored
// pairs and one pair PyPI can't install. Not real measurements.
const REF = dashboardReference();
const year = (federalRel, stateRel) => ({
  status: 'measured',
  records: 300,
  federalMatches: 200,
  stateMatches: 210,
  federalMatchesRel: federalRel.reduce((a, b) => a + b, 0),
  stateMatchesRel: stateRel.reduce((a, b) => a + b, 0),
  stateMatchesRelNet: stateRel.reduce((a, b) => a + b, 0),
  byState: {
    households: [100, 100, 100],
    federalMatches: [60, 70, 70],
    stateMatches: [70, 70, 70],
    federalMatchesRel: federalRel,
    stateMatchesRel: stateRel,
    stateMatchesRelNet: stateRel,
  },
});
const FIXTURE = {
  schemaVersion: 1,
  states: ['AL', 'AK', 'AZ'],
  references: {
    [REF]: {
      release: REF,
      url: `https://github.com/PolicyEngine/policyengine-taxsim/releases/tag/${REF}`,
      years: { 2023: { records: 300, taxsimBinaryBuild: 'cd2026090910', taxsimFallback: null } },
    },
  },
  rows: [
    {
      id: `taxsim-2.10.0+us-1.587.1@${REF}`,
      policyengineTaxsimVersion: '2.10.0',
      policyengineUsVersion: '1.587.1',
      reference: REF,
      releasedAt: '2026-02-26T02:16:00Z',
      status: 'not-installable',
      reason: 'policyengine-us 1.587.1 is not on PyPI',
    },
    {
      id: `taxsim-3.0.0+us-2.17.1@${REF}`,
      policyengineTaxsimVersion: '3.0.0',
      policyengineUsVersion: '2.17.1',
      reference: REF,
      releasedAt: '2026-09-29T18:33:00Z',
      triggers: [{ package: 'policyengine-taxsim', version: '3.0.0' }],
      status: 'measured',
      years: { 2023: year([80, 90, 85], [90, 95, 80]) },
    },
    {
      id: `taxsim-3.1.1+us-2.36.0@${REF}`,
      policyengineTaxsimVersion: '3.1.1',
      policyengineUsVersion: '2.36.0',
      reference: REF,
      releasedAt: '2026-10-09T12:13:00Z',
      triggers: [{ package: 'policyengine-taxsim', version: '3.1.1' }],
      status: 'measured',
      years: { 2023: year([85, 90, 88], [92, 96, 90]) },
    },
  ],
};

const mockFetch = (body, status = 200) =>
  vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });

afterEach(() => vi.restoreAllMocks());

describe('AlignmentHistory', () => {
  it('tabulates scored pairs newest first, with the change between them', async () => {
    mockFetch(FIXTURE);
    render(
      <AlignmentHistory selectedYear={2023} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    // 263/300 = 87.7% federal (from 85.0%); 278/300 = 92.7% state (from 88.3%).
    expect(within(rows[0]).getByText('3.1.1')).toBeTruthy();
    expect(within(rows[0]).getByText('87.7%')).toBeTruthy();
    expect(within(rows[0]).getByText('+2.7')).toBeTruthy();
    expect(within(rows[0]).getByText('92.7%')).toBeTruthy();
    expect(within(rows[0]).getByText('+4.3')).toBeTruthy();
    expect(within(rows[1]).getAllByText('—')).toHaveLength(2);
  });

  it('follows the state filter and the tolerance mode', async () => {
    mockFetch(FIXTURE);
    const { rerender } = render(
      <AlignmentHistory selectedYear={2023} selectedState="AZ" toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    const table = await screen.findByRole('table');
    expect(within(table).getAllByText('88.0%').length).toBeGreaterThan(0);
    rerender(
      <AlignmentHistory selectedYear={2023} selectedState="AZ" toleranceMode={TOLERANCE_MODES.ABSOLUTE} />
    );
    expect(within(screen.getByRole('table')).getAllByText('70.0%').length).toBeGreaterThan(0);
  });

  it('lists pairs that could not be scored, with the reason', async () => {
    mockFetch(FIXTURE);
    render(
      <AlignmentHistory selectedYear={2023} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    expect(await screen.findByText('1 release not scored for 2023')).toBeTruthy();
    expect(screen.getByText('policyengine-us 1.587.1 is not on PyPI')).toBeTruthy();
    expect(screen.getByText(/build cd2026090910/)).toBeTruthy();
  });

  it('reads a release from the keyboard', async () => {
    mockFetch(FIXTURE);
    render(
      <AlignmentHistory selectedYear={2023} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    const chart = await screen.findByRole('img');
    fireEvent.focus(chart);
    let tip = screen.getByRole('status');
    expect(within(tip).getByText(/policyengine-taxsim 3\.1\.1/)).toBeTruthy();
    fireEvent.keyDown(chart, { key: 'ArrowLeft' });
    tip = screen.getByRole('status');
    expect(within(tip).getByText(/policyengine-taxsim 3\.0\.0/)).toBeTruthy();
    expect(within(tip).getByText('85.0%')).toBeTruthy();
  });

  it('says so when a year has no scored release', async () => {
    mockFetch(FIXTURE);
    render(
      <AlignmentHistory selectedYear={2021} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    expect(await screen.findByText(/No release has been scored for 2021 yet/)).toBeTruthy();
  });

  it('keeps the reference selector when the chosen reference has nothing scored', async () => {
    const other = 'full-ecps-comparison-older';
    mockFetch({ ...FIXTURE, references: { ...FIXTURE.references, [other]: { release: other, years: {} } } });
    render(
      <AlignmentHistory selectedYear={2023} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    const select = await screen.findByRole('combobox');
    fireEvent.change(select, { target: { value: other } });
    expect(screen.getByText(/No release has been scored for 2023 yet/)).toBeTruthy();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: REF } });
    expect(screen.getByRole('table')).toBeTruthy();
  });

  it('thins month labels to the room there is, and labels days on a short span', () => {
    const start = new Date(Date.UTC(2025, 0, 15));
    const end = new Date(Date.UTC(2027, 0, 15));
    expect(timeTicks(start, end)).toHaveLength(24);
    const thinned = timeTicks(start, end, 3);
    expect(thinned.length).toBeLessThanOrEqual(3);
    expect(thinned[0].label).toBe('Feb');
    const days = timeTicks(new Date(Date.UTC(2026, 9, 2)), new Date(Date.UTC(2026, 9, 9)));
    expect(days.map((t) => t.label)).toEqual(['Oct 2', 'Oct 9']);
  });

  it('treats a missing history file as no scored releases', async () => {
    mockFetch(null, 404);
    render(
      <AlignmentHistory selectedYear={2023} selectedState={null} toleranceMode={TOLERANCE_MODES.RELATIVE} />
    );
    expect(await screen.findByText(/No release has been scored for 2023 yet/)).toBeTruthy();
  });
});
