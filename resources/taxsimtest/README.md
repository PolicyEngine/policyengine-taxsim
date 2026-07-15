# Bundled TAXSIM (`taxsimtest`) binaries

These are NBER's `taxsimtest` binaries, bundled per platform and used by
`TaxsimRunner` (and CI) instead of downloading at run time.

**All three platforms must be kept in sync.** In July 2026 the Linux/Windows
binaries were ~10 months older than the macOS one; `taxsimtest` had since
gained the opt(30) liability-year rebate handling, so
`tests/test_taxsim_opt30.py` failed only on ubuntu/windows CI and looked like
an upstream TAXSIM change (#1089). It wasn't — the bundled binaries were stale.

## Checking build dates

Every run reports the build: `TAXSIM completed successfully (binary build
2025Dec24)` — the binary stamps it into its output header (`cdate-...`).
To check a binary directly:

```bash
printf "taxsimid year state mstat page sage depx pwages idtl\n1 2021 47 2 45 45 0 60000 2\n" \
  | resources/taxsimtest/taxsimtest-osx.exe | head -1 | grep -o 'cdate-[^"]*'
# or, without running it:
strings resources/taxsimtest/taxsimtest-windows.exe | grep -o '"cdate-[^"]*"'
```

## Updating

Download the current builds (URLs from
https://taxsim.nber.org/taxsimtest/low-level-local.html):

```bash
curl -sL https://taxsim.nber.org/stata/taxsimtest/linux -o resources/taxsimtest/taxsimtest-linux.exe
curl -sL https://taxsim.nber.org/stata/taxsimtest/osx -o resources/taxsimtest/taxsimtest-osx.exe
curl -sL https://taxsim.nber.org/taxsimtest/taxsimtest.exe -o resources/taxsimtest/taxsimtest-windows.exe
```

Sanity-check each download with `file` (ELF / Mach-O / PE32+) — the server
returns a small HTML 404 page for wrong paths. Note the NBER pages sometimes
lag: in July 2026 the osx download there was older than our bundled copy, so
compare `cdate` stamps before overwriting a newer binary.

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
