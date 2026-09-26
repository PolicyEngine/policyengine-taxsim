# Refreshing dashboard data

The **Refresh dashboard data** GitHub Actions workflow regenerates the five
2021–2025 comparisons on hosted Linux runners. It does not run simulations on
the operator's laptop. There is no schedule; start it manually when needed.

The source is `cps_households.csv`: TAXSIM inputs for 111,347 eCPS tax units,
reused for every tax year (the year column is set per run). Both models are
rerun. Flags remain `assume_w2_wages=True` and `disable_salt=False`.
PolicyEngine output detail is 5 so the detailed output columns are populated;
TAXSIM retains the original output setting. Drill-down household IDs are held
constant, and all summary denominators use the complete population.

Before any model runs, the refresh rejects a source with state code 0, any
other code that is not an integer from 1 to 51, or no households in some state.
TAXSIM reads state 0 as "no state tax". Until September 23, 2026 (including the
July 7 and September 21 data), the 1,155 Alabama households were coded 0,
because the converter that built the file (`vectorized_validation.py`, 4ccfead)
had no entry for FIPS 1. They were scored without state income tax and
reported under TX. The file also lacks Alabama's other 1,155 tax units: the
eCPS stacks a CPS-income half and a PUF-imputed half, and d317b05 deleted
Alabama's CPS-income block (taxsimid 31801–32955). Restoring it would make the
population 112,502.

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
  Rerunning failed jobs from the Actions UI automatically restores checkpoints
  from that same run when available.
- Full results and small site data are separate artifacts, retained for seven
  days. Download only `site-data-*` to the laptop. The release job uploads the
  full CSVs directly from its ephemeral runner to a draft GitHub release.
- The source (`cps_households.csv`) is only read. Each batch's input file is
  removed once that batch completes. Hosted runner storage is discarded when
  the job ends. No unrelated local files are deleted.

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
