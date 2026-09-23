# Bundled TAXSIM (`taxsimtest`) binaries

These are NBER's `taxsimtest` binaries, bundled per platform and used by
`TaxsimRunner` (and CI) instead of downloading at run time.

## Pinned builds (verified September 23, 2026)

| Platform | Build stamp | NBER download |
| --- | --- | --- |
| macOS | `cd2026090910` | https://taxsim.nber.org/out2psl/osx |
| Linux | `cd2026090910` | https://taxsim.nber.org/out2psl/linux |
| Windows | `cd2026090110` | https://taxsim.nber.org/taxsimtest/taxsimtest.exe |

`manifest.json` records the source URLs, build stamps, download date, sizes,
and SHA-256 checksums. Windows is the newest available Windows build found;
its date differs from macOS/Linux, so do not assume cross-platform parity.
The hosted test matrix exercises each platform's bundled executable.

In July 2026, stale Linux/Windows binaries caused the opt(30) regression in
#1089. Compare all platforms when updating, and record upstream differences.

## Checking build dates

Every run reports the build: `TAXSIM completed successfully (binary build
2025Dec24)` — the binary stamps it into its output header (`cdate-...`).
To check a binary directly:

```bash
printf "taxsimid year state mstat page sage depx pwages idtl\n1 2021 47 2 45 45 0 60000 2\n" \
  | resources/taxsimtest/taxsimtest-osx.exe | head -1 | grep -oE 'cdate-[^"]*|cd[0-9]{10}'
# or, without running it:
strings resources/taxsimtest/taxsimtest-windows.exe | grep -oE 'cdate-[^"]*|cd[0-9]{10}'
```

## Updating

Download the newest verified builds from the sources above. NBER’s
[installation page](https://taxsim.nber.org/taxsimtest/low-level-local.html)
also lists mirrors, which can lag the PolicyEngine comparison builds:

```bash
curl -sL https://taxsim.nber.org/out2psl/linux -o resources/taxsimtest/taxsimtest-linux.exe
curl -sL https://taxsim.nber.org/out2psl/osx -o resources/taxsimtest/taxsimtest-osx.exe
curl -sL https://taxsim.nber.org/taxsimtest/taxsimtest.exe -o resources/taxsimtest/taxsimtest-windows.exe
```

Sanity-check each download with `file` (ELF / Mach-O / PE32+) — the server
returns a small HTML 404 page for wrong paths. Note the NBER pages sometimes
lag: in July 2026 the osx download there was older than our bundled copy, so
compare `cdate` stamps before overwriting a newer binary.

Dan also publishes fresh builds at `taxsim.nber.org/out2psl/{osx,linux}` —
in August 2026 those were newer (cd2026081819) than the stata-page osx (a
2025 build). **Do not use `out2psl/windows`**: in August 2026 it served a
stale 32-bit PE32 build (cd2026062510), older than the canonical
`taxsimtest/taxsimtest.exe` (cd2026081318, PE32+). Whatever the source,
always compare build stamps across all three platforms before committing and refresh
`manifest.json`. Do not overwrite a newer binary with an older mirror.

Verify behavior before committing — the VA 2021 opt(30) record is the
canonical probe (expect `siitax=2068.05`, `srebate=500`; a stale binary gives
`siitax=2568.05`, `srebate=0`):

```bash
printf "taxsimid year state mstat page sage depx pwages idtl opt1 opt1v\n1 2021 47 2 45 45 0 60000 2 30 1\n" > /tmp/va21.txt
cat /tmp/va21.txt | resources/taxsimtest/taxsimtest-osx.exe            # macOS
docker run --rm --platform linux/amd64 -v "$PWD/resources/taxsimtest:/b" -v /tmp:/t debian:stable-slim \
  sh -c 'cp /b/taxsimtest-linux.exe /x && chmod +x /x && cat /t/va21.txt | /x'   # Linux
```

`tests/test_taxsim_opt30.py` runs this record on every CI platform, so a
stale binary cannot land silently — but its failure message points here so
nobody chases phantom upstream changes again.
