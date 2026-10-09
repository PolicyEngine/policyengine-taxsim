# Agreement by release

The dashboard's **Agreement by release** section shows how each released
`policyengine-taxsim` / `policyengine-us` pair agrees with TAXSIM. The data is
in `dashboard/public/data/alignment_history.json`. `scripts/alignment_history.py`
writes it, and the **Alignment history** GitHub Actions workflow keeps it
current.

## What a row measures

Each row is one pair of releases, scored with the dashboard's own definitions:

- **Households:** `cps_households.csv`, all 111,347 tax units, rerun for each
  tax year from 2021 to 2025.
- **TAXSIM side:** the TAXSIM rows of the published full-data release the
  dashboard links to (`FULL_DATA_RELEASE_BASE` in
  `dashboard/src/constants/index.js`, currently
  `full-ecps-comparison-run-35953332152`). Every row in a series is scored
  against the same TAXSIM outputs, so a change between rows comes from the
  emulator or the model, never from TAXSIM.
- **PolicyEngine side:** the pair installed in a fresh virtual environment as
  PyPI stood just after the later of the two releases (`uv pip install
  --exclude-newer`). The run uses the refresh's options: `assume_w2_wages=True`,
  `disable_salt=False` and output detail 5. The S-corp treatment is each
  release's default. When an older release lacks an option, the row lists it
  under `settings.unsupportedOptions`.
- **Agreement:** `match_flags()` in `scripts/refresh_dashboard.py` decides every
  match, the same function the dashboard summaries use. That gives five
  counts: `federalMatches` and `stateMatches` (within $15),
  `federalMatchesRel` and `stateMatchesRel` (within 1% of the gross-income
  proxy), and `stateMatchesRelNet` (within 1%, with one-time state rebates
  netted out).

The file stores counts only, overall and per state (in `states` order). A rate
is a count divided by `records`, or by the state's `byState.households`, and
the dashboard computes it.

## Which pairs

- **Each `policyengine-taxsim` release** is paired with the newest
  `policyengine-us` release published before it. That is what installing the
  emulator that day would have given.
- **For each day, the last `policyengine-us` release** that PyPI still serves is
  paired with the `policyengine-taxsim` release that was newest then.

PyPI does not serve every release. Older releases have been deleted (in
October 2026 the oldest `policyengine-us` on PyPI was 1.691.1, and the oldest
`policyengine-taxsim` was 2.10.0), and some releases never published because
their publish job failed. A pair that can't be installed is recorded with
`status: "not-installable"` and the reason. It is never scored with a
substitute release.

To decide which `policyengine-us` release was newest at a moment, the planner
uses PyPI upload times. Releases PyPI lacks are placed from their changelog date
and the neighbouring upload times, or from their version-bump commit when a
policyengine-us clone is given (`--us-repo`). There, a release whose
**Publish** job failed, was skipped or was cancelled is treated as never
published: nobody could have installed it. When the order still can't be
settled, the pair is recorded as not installable, with that as the reason.

## When rows are added

The workflow runs:

- after CI finishes on `main`, which is when a new release is published;
- daily, for new `policyengine-us` releases (mode `recent`: releases from the
  last seven days that are not yet recorded);
- on demand: `release` scores one emulator release, and `backfill` re-plans
  every release since the first.

It runs `plan`, then `reference`, then one `measure` job per pair, then
`record`. `measure` runs one worker process per batch of 5,000 households and
tax year, as the dashboard refresh does. Two kinds of failure are kept apart:

- A year the release itself can't compute (the worker reports the exception)
  is recorded as a failed year, with the message.
- A worker that is stopped for memory or time, or crashes, fails the job and
  records nothing, so a later run measures the pair again. A pair whose earlier
  attempt failed is planned again while it is in scope.

`record` merges the rows and commits the file to `main`. It first
waits until no CI `versioning` job is running, because that job pushes without
pulling. Per-household PolicyEngine outputs for each pair stay as workflow
artifacts for 90 days, and each row stores their SHA-256.

## Checks

- `reference` downloads the published comparison and checks its SHA-256
  against the release's provenance and its households against the source. It
  then re-scores the published PolicyEngine side and requires every committed
  `summary_{year}.json` rate and state count to come out exactly.
- `merge` refuses any row whose counts do not reconcile. The checks are:
  - every count lies between 0 and the households;
  - state households sum to the total, and state counts sum to each total
    count;
  - no state count exceeds that state's households;
  - every measured year covers the reference's full population;
  - row ids are unique, and rows are sorted by release time;
  - smoke-test rows are refused.
  `merge --check` validates the committed file, and `tests/test_alignment_history.py`
  runs the same check.
- Property tests (Hypothesis and fast-check) cover these invariants, the timing
  rules (a release's window always contains its true publish time, and a pair
  the planner reports as certain is right for every consistent history), and the
  dashboard's rate derivation. A differential test checks that `score()` and
  the refresh's `summarize()` tally identically. On pull requests that change
  this code, the workflow also checks that the history worker reproduces the
  refresh's PolicyEngine outputs household by household.

## Running it locally

```sh
python scripts/alignment_history.py plan --mode latest --output plan.json
python scripts/alignment_history.py reference --work-dir reference          # ~550 MB download
python scripts/alignment_history.py measure --taxsim-version 3.1.1 \
  --us-version 2.36.0 --years 2023 --limit 102 \
  --reference-dir reference --work-dir work                                 # smoke test
```

Don't run a full measurement (111,347 households, five years) on a laptop: each
worker holds about 3 GB. A `--limit` smoke test is never recorded.
