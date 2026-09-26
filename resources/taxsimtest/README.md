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

Dan also publishes fresh builds at `taxsim.nber.org/out2psl/{osx,linux}` —
in August 2026 those were newer (cd2026081819) than the stata-page osx (a
2025 build). **Do not use `out2psl/windows`**: in August 2026 it served a
stale 32-bit PE32 build (cd2026062510), older than the canonical
`taxsimtest/taxsimtest.exe` (cd2026081318, PE32+). Whatever the source,
always compare `cdate` stamps across all three platforms before committing.

Verify behavior before committing — the VA 2021 opt(30) record is the
canonical probe (expect `siitax=2068.05`, `srebate=500`; a stale binary gives
`siitax=2568.05`, `srebate=0`):

```bash
printf "taxsimid year state mstat page sage depx pwages idtl opt1 opt1v\n1 2021 47 2 45 45 0 60000 2 30 1\n" > /tmp/va21.txt
resources/taxsimtest/taxsimtest-osx.exe < /tmp/va21.txt                 # macOS
resources/taxsimtest/taxsim-docker-wrapper.sh < /tmp/va21.txt           # Linux, via Docker
```

To check a new Linux download before it replaces the bundled copy, point the
wrapper at it: `TAXSIM_LINUX_BINARY=~/Downloads/taxsimtest-linux.exe
resources/taxsimtest/taxsim-docker-wrapper.sh < /tmp/va21.txt`.

`tests/test_taxsim_opt30.py` runs this record on every CI platform, so a
stale binary cannot land silently — but its failure message points here so
nobody chases phantom upstream changes again.

## Running the Linux binary through Docker

`taxsim-docker-wrapper.sh` runs `taxsimtest-linux.exe` in a container, which
is how to exercise the Linux build from a Mac (including Apple silicon, where
Docker emulates x86-64 via `--platform linux/amd64`). It reads TAXSIM input on
stdin and writes the output to stdout, from any working directory.

- **Image.** The Linux build is a dynamically linked gfortran executable that
  needs `libgfortran.so.5` and `libquadmath.so.0`. Plain `ubuntu:24.04` and
  `debian:stable-slim` lack them and fail with `error while loading shared
  libraries: libgfortran.so.5` (exit 127). The wrapper instead uses
  `taxsimtest-linux.Dockerfile` (ubuntu:24.04 plus `libgfortran5` and
  `libquadmath0`). It builds that image on first use, tagged
  `policyengine-taxsim-linux:<hash of the Dockerfile>`, and reuses it after,
  so editing the Dockerfile triggers a rebuild.
- **Binary.** The wrapper bind-mounts the `taxsimtest-linux.exe` next to it
  (or `$TAXSIM_LINUX_BINARY`) at run time, so a refreshed binary never needs
  an image rebuild.
- **Keep files under `$HOME`.** On macOS, Docker runs in a VM and can
  bind-mount only the directories that VM shares with the host. colima
  shares just `$HOME` by default (add others under `mounts:` in
  `~/.colima/default/colima.yaml`). A file outside it, such as one under
  `/private/tmp` (where macOS's `/tmp` points), silently mounts as an empty
  directory. A raw `docker run` then fails with `exec: "/taxsim": is a
  directory` (exit 126); the wrapper detects this and says so. Likewise,
  under colima `-v /tmp:/t` mounts the VM's own `/tmp`, not the Mac's. So
  keep the checkout, and any `TAXSIM_LINUX_BINARY`, under the repo or
  `$HOME`, and pipe inputs on stdin rather than mounting them.
