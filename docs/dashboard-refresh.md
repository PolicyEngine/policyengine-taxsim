# Refreshing dashboard data

The **Refresh dashboard data** GitHub Actions workflow regenerates the five
2021–2025 comparisons on hosted Linux runners. It does not run simulations on
the operator's laptop. There is no schedule; start it manually when needed.

The source is the July 7, 2026 full comparison release. Only the original
TAXSIM input rows are reused, preserving the 111,347 households per year. Both
models are rerun. Flags remain `assume_w2_wages=True` and `disable_salt=False`.
PolicyEngine output detail is 5 so the detailed output columns are populated;
TAXSIM retains the original output setting. Drill-down household IDs are held
constant, and all summary denominators use the complete population.

## Resource limits and recovery

- At most two hosted year jobs run concurrently; each launches one model
  worker at a time for 5,000 households.
- The coordinator streams the source and output CSVs. It never imports the
  model. Each worker exits after saving its result, releasing model caches.
- A worker is stopped above 5 GiB RSS (including child processes), after 15
  minutes, or when free disk falls below 4 GiB. These are monitored limits,
  not OS-enforced reservations; the runner has additional memory headroom.
- Successfully completed batches are compressed and checksummed. Failed year
  jobs upload checkpoint artifacts for seven days. Select the same code ref
  and pass that run ID as `resume_run_id` to continue. Checkpoints with a
  different source, code revision, lockfile, batch size or limit are rejected.
  Resume individual failed matrix jobs from the Actions UI only if no previous
  checkpoints are needed; standard reruns otherwise start those jobs afresh.
- Full results and small site data are separate artifacts, retained for seven
  days. Download only `site-data-*` to the laptop. The release job uploads the
  full CSVs directly from its ephemeral runner to a draft GitHub release.
- Sources are removed after a successful year. Hosted runner storage is
  discarded when the job ends. No unrelated local files are deleted.

## Validation and publication

Run the 100-household smoke test first when changing the environment. The
workflow checks paired household IDs, finite headline outputs, expected
population size, summary arithmetic and sample completeness. Before publishing,
review the new match rates against the prior summaries and inspect large changes.
Full output hashes, input hashes, model versions, code revision and measured
peak worker memory are stored in `provenance_YEAR.json`.

The workflow stages a **draft** release only. After validation, publish that
release, replace `dashboard/public/data` with the small site artifacts, update
`FULL_DATA_RELEASE_BASE` in `dashboard/src/constants/index.js`, regenerate
`dashboard/public/config-data.json`, and build/deploy the dashboard. The page
shows each year's generation date and PolicyEngine-US version.

## Dependencies

The refresh environment is fully pinned in
`scripts/dashboard-refresh-requirements.txt`. Regenerate it intentionally with:

```sh
uv pip compile pyproject.toml scripts/dashboard-refresh.in --python-version 3.11 \
  --output-file scripts/dashboard-refresh-requirements.txt
```

Separately, Python 3.10 users resolve an older PolicyEngine-US version that
imports `spm_calculator.geoadj`; its compatibility constraint is in
`pyproject.toml`. The Python 3.11 refresh uses the current model/API.
