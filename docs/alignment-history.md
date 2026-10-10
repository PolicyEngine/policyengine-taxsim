# Agreement by release

The dashboard's **Agreement by release** section shows how released
`policyengine-taxsim` / `policyengine-us` pairs agree with TAXSIM. The data is
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
- **PolicyEngine side:** the pair installed in a fresh virtual environment with
  `uv pip install --exclude-newer`, set to one minute after both releases'
  files were uploaded. Other packages then resolve from the files PyPI had by
  that moment and still serves. This can't restore a dependency version PyPI
  has deleted since. The run uses the refresh's options: `assume_w2_wages=True`,
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

A plan lists two kinds of pair:

- **A `policyengine-taxsim` release** with the newest `policyengine-us` release
  that was installable when it came out and that its requirement allows. That
  is what installing the emulator then would have given.
- **For each day, the last `policyengine-us` release PyPI serves**, with the
  `policyengine-taxsim` release that was newest then. A pair the emulator's
  requirement excludes is skipped and logged.

A release counts as out from the upload of its first file.

PyPI does not serve every release. On 2026-10-09 its oldest `policyengine-us`
was 1.691.1 and its oldest `policyengine-taxsim` was 2.10.0, while the
changelogs go back further, and some later versions are missing too. A missing
`policyengine-us` version was either published and later deleted, or never
published. The planner tells these apart from the version's **Publish** job in
policyengine-us's CI (it needs a clone of that repository, `--us-repo`):

- **The job succeeded.** The version was out between the job's start and its
  end. If it was the newest when an emulator release came out, that pair is
  recorded with `status: "not-installable"` and the missing version as the
  reason. It is never scored with a substitute.
- **The job failed, was skipped or was cancelled.** Nobody could install that
  version, so it is not what a user got. For example, `policyengine-us`
  2.6.18 to 2.6.20 never published, so `policyengine-taxsim` 2.31.3 pairs with
  2.6.17.
- **No job is on record, or the timing can't be settled.** The pair is logged
  as undetermined and not recorded, so a later plan with better evidence can
  settle it. The same goes for a version published within the last day that
  PyPI's index does not list yet.

A version-bump commit only bounds a publication from below. Without the job,
the planner knows that a missing version came out no earlier than its bump
commit, its changelog date and the previous version PyPI has, and no later
than the next version PyPI has. This assumes versions publish in order.

An emulator release that is itself gone from PyPI is recorded as not
installable. Its release moment is known only to the day, so its row names the
newest `policyengine-us` version dated on or before that day, and says so.

## When rows are added

The workflow runs:

- after each CI run on `main` succeeds (CI publishes a release when the merge
  carried a changelog fragment), and daily. Both plan the releases of the last
  seven days that are not recorded yet (mode `recent`);
- on demand: `release` plans one emulator release, and `backfill` plans every
  release since the first.

Its jobs are `plan`, `reference`, one `measure` job per pair, and `record`.

`measure` runs one worker process per batch of 5,000 households and tax year,
as the dashboard refresh does. It keeps two kinds of failure apart:

- **The release can't compute a year.** The worker reports the exception, the
  year is recorded as failed with the message, and its remaining batches are
  skipped.
- **The machine fails.** A worker that runs out of memory, hits an I/O or
  network error, exceeds its memory or time limit, or crashes is retried once
  with its batch split in two. If that fails too, the job fails and records
  nothing.

A pair that isn't fully measured is planned again while it is in scope. A new
row replaces the recorded one only if it measured more years.

`record` merges the rows and commits the file to the branch the workflow ran
on, which is `main` for the scheduled and after-CI runs. Per-household
PolicyEngine outputs stay as workflow artifacts for 90 days, and each measured
year stores their SHA-256.

### Recording without breaking a release

CI's `versioning` job checks out the commit that triggered it and pushes
"Update package version" without pulling. A commit that lands on `main` in
between makes that push fail, and the release with it. Two things keep a
recorded row from doing that:

- `versioning` first fast-forwards over commits that touch only
  `alignment_history.json` (see `ci.yml`).
- `record` does not push while a `versioning` job is running, checks this
  right before each push, and treats a GitHub API error as "running".

A push made with the workflow's token starts no workflow run, so recording
never triggers CI. It does reach Vercel: the recording commit on the scratch
branch used for the first backfill got a Vercel deployment and no workflow
runs.

## Checks

- `reference` downloads the published comparison and checks its SHA-256
  against the release's provenance. For every household it requires each
  TAXSIM input, the state and the tax year to equal the source's. It then
  re-scores the published PolicyEngine side and requires every committed
  `summary_{year}.json` rate and state count to come out exactly. `measure`
  refuses a reference or a source whose hash differs from the verified one.
- `merge` refuses a row unless:
  - every count lies between 0 and the households;
  - state households sum to the total, and state counts sum to each total
    count;
  - no state count exceeds that state's households;
  - every measured year is one the reference has, and covers its full
    population;
  - the row came from a plan (it has its triggers and install moment) and is
    not a `--limit` smoke test;
  - row ids are unique and rows are sorted by release time.
  `merge --check` applies the same rules to the committed file, and so does
  `tests/test_alignment_history.py`.
- Property tests (Hypothesis and fast-check) cover:
  - these invariants, and the dashboard's rate derivation;
  - the timing rules. Over random release histories with bump commits,
    publish jobs, failed publishes and deletions, a release's window always
    contains its true publish time, and a pairing the planner calls certain is
    the true one.
- Differential tests check that `score()` and the refresh's `summarize()`
  tally identically, and that the dashboard's rates reproduce the committed
  summaries from the recorded counts. On pull requests that change this code,
  the workflow also checks that the history worker reproduces the refresh's
  PolicyEngine outputs household by household.

## Running it locally

```sh
python scripts/alignment_history.py plan --mode latest --output plan.json
python scripts/alignment_history.py reference --work-dir reference    # five ~110 MB CSVs
python scripts/alignment_history.py measure --taxsim-version 3.1.1 \
  --us-version 2.36.0 --years 2023 --limit 102 \
  --reference-dir reference --work-dir work                           # smoke test
```

Don't run a full measurement on a laptop. On a GitHub-hosted runner, the first
full run (38006256962) took 34 minutes per pair, and its workers peaked at
4,480 MiB each. A `--limit` smoke test, or any measurement not started from a
plan's pair, is never recorded.
