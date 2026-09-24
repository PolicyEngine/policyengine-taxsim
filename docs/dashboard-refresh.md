# Refreshing dashboard data

The **Refresh dashboard data** GitHub Actions workflow regenerates the five
2021–2025 comparisons on hosted Linux runners. It does not run simulations on
the operator's laptop. There is no schedule; start it manually when needed.

Pick the population with the workflow's `dataset` input:

- `populace` (default): `populace_households.csv`, one TAXSIM record per tax
  unit in the Populace US 2024 build that policyengine.py certifies
  (`populace-us-2024-spm-20260915`). See "Building the Populace inputs" below.
- `ecps`: `cps_households.csv`, the 111,347 Enhanced CPS tax units the
  benchmark used through September 2026. policyengine-us-data archived the
  Enhanced CPS on 2026-07-02. It stays available because the Populace build
  has almost none of its high-income tail.

Each source is reused for every tax year; the year column is set per run.
Before any model runs, the refresh rejects a source with state code 0 or any
other invalid code, or with no households in some state. TAXSIM reads state 0
as "no state tax". Before September 2026, the 1,155 Alabama eCPS households
were coded 0, because the converter that built the file had no Alabama entry.
They were scored without state income tax and reported under TX.

Both models are rerun. Flags remain `assume_w2_wages=True` and
`disable_salt=False`. PolicyEngine output detail is 5 so the detailed output
columns are populated; TAXSIM retains the original output setting. eCPS
drill-down household IDs are held at the published sample. Populace drill-down
IDs are a deterministic, state-stratified draw from the source (about 3,000
records, at least 20 per state). All summary denominators use the complete
population. Every summary's `metadata.dataset` records the source's sha256
and, for Populace, the build id, Hugging Face revision and commit, H5 sha256
and the model versions that read it. `metadata` also records the benchmark's
PolicyEngine-US version and the taxsimtest build and sha256.

The rates are PolicyEngine's own comparison against NBER's taxsimtest binary.
NBER has not endorsed them as error statistics; label them that way wherever
they are quoted.

## Building the Populace inputs

`scripts/convert_h5_to_taxsim.py` downloads the certified H5 at its pinned
Hugging Face commit, checks its sha256, and refuses to run unless the
installed policyengine-us and policyengine-core are the versions
policyengine.py certifies for the build (2.2.1 and 3.32.5). That environment
is pinned in `scripts/populace-convert-requirements.txt`:

```sh
uv venv --python 3.11 .venv-populace
VIRTUAL_ENV=.venv-populace uv pip install -r scripts/populace-convert-requirements.txt
.venv-populace/bin/python scripts/convert_h5_to_taxsim.py
```

It writes `populace_households.csv` and `populace_households.json`
(provenance and coverage counts). The benchmark itself runs the emulator in
the separate, newer refresh environment below. That is outside the build's
certified model range, but the emulator never reads the H5. It builds its own
households from the TAXSIM rows. The certified model is used only where the
H5 is read. The input definitions (itemized deductions, filers' incomes,
dependents, filing status) are documented in the converter's docstring.

To move to a newer Populace build, update `POPULACE_BUILD` in the converter
from policyengine.py's `src/policyengine/data/bundle/manifest.json`, update
the requirements if the certified model changed, regenerate the inputs, and
update `records` in `DATASETS` in `scripts/refresh_dashboard.py`.

## Resource limits and recovery

- At most two hosted year jobs run concurrently; each launches one model
  worker at a time for a batch of households: 5,000 for the eCPS and 2,000
  for Populace, whose records populate more inputs and exceeded the memory
  budget at 5,000 (`batchSize` in `DATASETS`).
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
- Full results and small site data are separate artifacts, named by dataset
  and year and retained for seven days. Download only `site-data-*` to the
  laptop. The release job uploads the
  full CSVs directly from its ephemeral runner to a draft GitHub release.
- Hosted runner storage is discarded when the job ends. No unrelated local
  files are deleted.

## Validation and publication

Run the 100-household smoke test first when changing the environment. The
workflow checks paired household IDs, finite headline outputs, expected
population size, summary arithmetic and sample completeness. Before publishing,
review the new match rates against the prior summaries and inspect large changes.
Full output hashes, input hashes, model versions, code revision and measured
peak worker memory are stored in `provenance_YEAR.json`.

The workflow stages a **draft** release (`<dataset>-comparison-run-<run id>`)
whose notes are generated from the provenance files: population and build,
environment, the agreement-rate table and the not-endorsed label. After
validation, publish that release, copy the `site-data-<dataset>-*` artifacts
to `dashboard/public/data/<dataset>/`, update that dataset's release tag in
`DATASETS` in `dashboard/src/constants/index.js`, regenerate
`dashboard/public/config-data.json`, and build/deploy the dashboard. The page
shows each year's dataset, generation date and PolicyEngine-US version.

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
