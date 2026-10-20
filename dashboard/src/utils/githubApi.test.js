import { describe, it, expect, vi, afterEach } from 'vitest';
import { fetchIssuesByLabel } from './githubApi';

afterEach(() => vi.unstubAllGlobals());

describe('fetchIssuesByLabel', () => {
  it('fetches every labeled page and excludes pull requests', async () => {
    const first = Array.from({ length: 100 }, (_, id) => ({ id }));
    const fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => first })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ id: 101 }, { id: 102, pull_request: {} }] });
    vi.stubGlobal('fetch', fetch);
    const issues = await fetchIssuesByLabel('model-difference');
    expect(issues).toHaveLength(101);
    expect(fetch.mock.calls[0][0]).toContain('labels=model-difference&page=1');
    expect(fetch.mock.calls[1][0]).toContain('page=2');
  });

  it('propagates failures instead of reporting an empty successful feed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403, statusText: 'Forbidden' }));
    await expect(fetchIssuesByLabel('model-difference')).rejects.toThrow('403');
  });

  it('returns an empty successful result for a genuinely empty feed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    expect(await fetchIssuesByLabel('model-difference')).toEqual([]);
  });
});
