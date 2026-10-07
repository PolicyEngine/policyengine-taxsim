import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const issue = (number, extra = {}) => ({ number, title: `Issue ${number}`, labels: [], ...extra });

const page = (items) => ({ ok: true, json: async () => items });

describe('fetchGitHubIssues', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reads every page of open issues and drops pull requests', async () => {
    const first = Array.from({ length: 100 }, (_, k) => issue(400 - k));
    first[5] = issue(395, { pull_request: { url: 'https://example.test/pr' } });
    const second = [issue(300), issue(299), issue(298)];
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(page(first))
      .mockResolvedValueOnce(page(second));
    vi.stubGlobal('fetch', fetchMock);

    const { fetchGitHubIssues } = await import('../githubApi');
    const issues = await fetchGitHubIssues();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toContain('page=2');
    expect(issues).toHaveLength(102);
    expect(issues.some((item) => item.pull_request)).toBe(false);
    expect(issues.map((item) => item.number)).toContain(298);
  });

  it('stops after one request when the first page is short', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(page([issue(2), issue(1)]));
    vi.stubGlobal('fetch', fetchMock);

    const { fetchGitHubIssues } = await import('../githubApi');
    const issues = await fetchGitHubIssues();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(issues).toHaveLength(2);
  });
});

describe('extractStateFromIssue', () => {
  const withLabels = (title, ...names) => ({ title, labels: names.map((name) => ({ name })) });

  it('reads state labels and ignores year and other labels', async () => {
    const { extractStateFromIssue } = await import('../githubApi');
    expect(extractStateFromIssue(withLabels('Does TAXSIM use the 2020 AGI limit?', 'CA', '2021', 'bug'))).toEqual(['CA']);
  });

  it('takes the first state code in the title and skips other capitals', async () => {
    const { extractStateFromIssue } = await import('../githubApi');
    expect(extractStateFromIssue(withLabels('Does TAXSIM use the IT-216 table for NY AGI?'))).toEqual(['NY']);
    expect(extractStateFromIssue(withLabels('AZ 2021 HoH 20Kpwages 5depx'))).toEqual(['AZ']);
    expect(extractStateFromIssue(withLabels('US joint -294Kpsemp 7Kssemp'))).toEqual([]);
  });

  it('does not repeat a state found in both the labels and the title', async () => {
    const { extractStateFromIssue } = await import('../githubApi');
    expect(extractStateFromIssue(withLabels('MI 2025 single 66page', 'MI', '2025'))).toEqual(['MI']);
  });
});
