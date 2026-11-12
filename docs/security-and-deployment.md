# Security and deployment notes

For IT and security reviewers deciding whether policyengine-taxsim can run on their systems. It covers what the package installs and runs, what touches the network and what does not, which files it writes, and how to install it on a machine without internet access.

Blocks marked as generated come from the code, the bundled files and the committed dependency snapshot, through `scripts/generate_docs_reference.py`; `tests/test_docs_reference.py` fails when one is out of date. Statements about the network were checked on 2026-10-09 as described under [How this was checked](#how-this-was-checked).

Contents:

- [Summary](#summary)
- [Network use](#network-use)
- [Files and processes](#files-and-processes)
- [Bundled TAXSIM-35 executables](#bundled-taxsim-35-executables)
- [Python versions](#python-versions)
- [Dependencies](#dependencies)
- [Installing without internet access](#installing-without-internet-access)
- [Updates and patching](#updates-and-patching)

## Summary

- **A local run makes no network connections.** Installed with pip and run from the command line, Python or R, the emulator computes everything on the machine. Nothing is sent to PolicyEngine or anyone else. A test in CI runs the command line and fails if Python tries to open a connection.
- **The hosted web runner is different.** The upload page at policyengine.org/us/taxsim/run sends your CSV to PolicyEngine's server. Do not use it for confidential data.
- **Installing needs the network** (PyPI, or your internal mirror), unless you install from downloaded files as described below.
- **It runs a bundled third-party executable** for tax years before 2021: NBER's TAXSIM-35, unsigned, x86-64 only. On Linux it needs glibc 2.34 or newer, so it does not run on Red Hat Enterprise Linux 8.
- **It writes your input records to temporary files** while it runs. It tries to delete them, but that is not guaranteed.
- **It installs dozens of Python packages**, including networking and developer libraries that a run never calls. The [full list](#dependencies) has versions and licenses. Two of them, policyengine-us and policyengine-core, are licensed under the GNU Affero General Public License v3; policyengine-taxsim itself is MIT-licensed.
- **It needs Python 3.10 or later**; use 3.11 or later to get current tax rules.

## Network use

### A local run: nothing

A standard run means any of the following, installed from PyPI or a mirror:

- `policyengine-taxsim < input.csv > output.csv`
- the `policyengine`, `taxsim`, `compare` and `sample-data` subcommands
- `PolicyEngineRunner` or `StitchedRunner` from Python
- `policyengine_calculate_taxes()` from the R package, once installed

None of these opens a network connection, sends data anywhere, or downloads data, tax rules or executables. Specifically:

- **Tax rules** are Python and YAML files inside the policyengine-us package, read from disk.
- **No survey data is downloaded.** PolicyEngine US downloads its default dataset (from Hugging Face) only when a simulation is created without a dataset (`policyengine_us/system.py`, `Microsimulation.__init__`). The emulator always passes its own dataset built from your input file, so that download never happens.
- **The TAXSIM-35 executables** ship inside the package; nothing is fetched for years before 2021. They import no networking functions (see [Bundled TAXSIM-35 executables](#bundled-taxsim-35-executables)).
- **Supplemental Poverty Measure data** that policyengine-us 2.x loads comes from a file bundled in the spm-calculator package. The spm-calculator functions that download Consumer Expenditure Survey files are research tools that a tax calculation does not call.
- **No update checks, telemetry or license checks** are made.

Several installed packages can make network requests (requests, urllib3, httpx, huggingface-hub, census), because policyengine-core and spm-calculator use them for other tasks. A run imports some of them but makes no requests. On import, urllib3 opens a socket bound to the loopback address `::1` to test for IPv6 support; it sends nothing and is closed at once.

### What does use the network

| What | When | Where it connects | What it sends |
|---|---|---|---|
| Installing with pip or uv | Install and upgrade | PyPI (or your configured mirror); GitHub for `git+https://` installs | Package requests |
| R package setup, `setup_policyengine()` | Run once by you, or automatically by the first `policyengine_calculate_taxes()` when no environment exists | GitHub and PyPI, to install `policyengine-taxsim` from GitHub's `main` branch with `--upgrade`; may download Miniconda through reticulate | Package requests |
| `StitchedRunner(..., use_remote_taxsim=True)` or `RemoteTaxsimRunner` | Only when Python code asks for it; no command-line flag sets it | NBER, `https://taxsim.nber.org/taxsim35/redirect.cgi` | Records before 2021, all TAXSIM input columns |
| Local API server, `uvicorn policyengine_taxsim.api:local_app` | Only if you start it; needs the `api` extra and the `modal` package | NBER for records before 2021; Mailchimp and Resend if its email endpoint is used | As above, plus the email address and the results |
| Web runner at policyengine.org/us/taxsim/run | When you upload a file in a browser | PolicyEngine's API on Modal (`policyengine--policyengine-taxsim-taxsimapi-serve.modal.run`) | The whole uploaded CSV |
| Web runner, "email results" option | When you ask for results by email | The same API, which sends results through Resend and, if "Keep me updated" is checked (it is by default), adds the address to PolicyEngine's Mailchimp list | The CSV, the email address, and the results as an attachment |
| `resources/taxsimtest/taxsim-docker-wrapper.sh` | Developer tool, not used by the package | Docker Hub (`ubuntu:24.04`) and Ubuntu's package mirrors, on its first build | Image and package requests |

The hosted service's code (`policyengine_taxsim/api.py`) computes results in memory and writes nothing to permanent storage. What Modal, the hosting platform, logs is outside this repository.

### How this was checked

On 2026-10-09, with policyengine-taxsim at this commit, policyengine-us 2.38.0 (Python 3.11) and 1.783.0 (Python 3.10), on macOS:

1. **Code review** of every network call in policyengine-taxsim, and of the download paths in policyengine-us, policyengine-core and spm-calculator listed above.
2. **Recording every network call.** A Python audit hook logged socket, DNS and HTTP events during a command-line run of records from 2019 (computed by TAXSIM-35) and 2023 to 2025 (PolicyEngine), with empty download caches. It recorded no connection, DNS lookup or HTTP request; the only socket event was urllib3's loopback test.
3. **Blocking the network.** The same run under macOS's `sandbox-exec` with all inbound and outbound network access denied completed and produced the same output.
4. **Inspecting the executables'** imported libraries and symbols (below).
5. **Installing offline.** The install step of the [offline installation](#installing-without-internet-access) was carried out on macOS with Python 3.11 inside the same no-network sandbox, using uv's equivalents of the pip commands (`uv pip install --no-index --find-links ... --require-hashes`), and the check command printed the expected result. The `pip download` commands themselves were not run. Their `--platform` flags were checked by computing the tags pip accepts with the `packaging` library: in each of the five snapshots, every package has a file with a listed hash that those flags accept.

`tests/test_no_network.py` repeats step 2 in CI on Linux, macOS and Windows with Python 3.10 and 3.11. It runs the `policyengine` subcommand on four records (one from 2019, one with no state, `idtl` 0 and 2) with an audit hook that refuses any connection leaving the machine, DNS lookup or HTTP request made through Python. A change that adds one on that path fails the build. What it does not cover:

- Other paths: the stdin command, `compare`, `--logs`, `idtl` 5, the R package, and states and inputs outside those four records. Steps 1 to 3 above covered the stdin command.
- Connections to the loopback address, which stay on the machine and are allowed.
- Anything Python's audit hooks cannot see: the TAXSIM-35 executable, a separate process (step 4 inspects its imports instead), and compiled extensions that open sockets without Python's `socket` module.

To check an installation yourself, run your own input with your firewall blocking the Python process, as in step 3; the [worked example](input-guide.md#worked-example-from-a-survey-file-to-taxes) is a suitable input.

## Files and processes

What a run writes:

| What | Where | When | Removed |
|---|---|---|---|
| Your input records, as PolicyEngine variables, in an HDF5 file | Python's temporary directory (`TMPDIR` on macOS and Linux, `TEMP` on Windows) | Each chunk of up to 10,000 records from 2021 on | Deletion is attempted when the chunk finishes |
| Records before 2021 as CSV, and TAXSIM-35's output | The same temporary directory | Each batch of records before 2021 | Deletion is attempted when TAXSIM-35 finishes |
| Results | The output file you name, or stdout | Every run | No |
| PolicyEngine test files (YAML) holding each record's inputs | The working directory | Only with `--logs` | No |

Treat the temporary directory as holding your data. The emulator tries to delete its temporary files when each chunk or batch ends, including after an error, but deletion is not guaranteed:

- A failed deletion is ignored without a message (`TaxsimMicrosimDataset.cleanup`, `TaxsimRunner.run`).
- If writing the TAXSIM-35 input file fails partway, for example on a full disk, the partial file is left behind.
- A process killed outright, for example by `kill -9` or a power loss, leaves whatever it had written.
- On Windows the emulator tries to delete the HDF5 file while it still holds it open, which Windows normally refuses. This has not been checked on a Windows machine.

`tests/test_no_network.py` gives its run a private temporary directory and checks that nothing is left in it after a normal run. On Linux and macOS a leftover file fails the test; on Windows it is reported as an expected failure until the behavior there is confirmed. If your input is confidential, point `TMPDIR` or `TEMP` at an approved location before running, and clear it afterward.

Processes started:

- **TAXSIM-35**, for records before 2021: run through the system shell as `cat <temp input> | <executable> > <temp output>` (`cmd.exe` with `type` on Windows). Only paths generated by the emulator reach the command line, never values from your data.
- **`uname -p`**, once, from Python's standard `platform` module during import (seen on macOS).

Before running TAXSIM-35 on macOS or Linux, the emulator sets the executable's permissions to 755 (`os.chmod`). On a shared installation owned by another account, that call fails with a permission error even when the file is already executable, so records before 2021 cannot be computed. Until [#1412](https://github.com/PolicyEngine/policyengine-taxsim/pull/1412) changes this to skip files that are already executable, install the package as the account that runs it, or compute only 2021 and later.

## Bundled TAXSIM-35 executables

The package includes NBER's TAXSIM-35 executables, installed to `share/policyengine_taxsim/` inside the Python environment. The emulator runs one of the three `taxsimtest` builds; the `taxsim35` builds are used only by this repository's tests. Generated from the files in `resources/`:

<!-- BEGIN GENERATED: taxsim-binaries -->
| File | Format | Build stamp | Bytes | SHA-256 | Run by the emulator |
|---|---|---|---|---|---|
| `resources/taxsim35/taxsim-latest-windows.exe` | Windows PE, 32-bit x86 | Not found | 2,317,791 | `85325403b2b6b40bebb2b7680b5dbceb29a9b1019dabf7f0596bb99e429b1e47` | No (tests only) |
| `resources/taxsim35/taxsim35-osx.exe` | macOS Mach-O, x86-64 | cdate-2025Aug23 | 1,661,800 | `0c879416a3bb96f9903cd21aab84108402fd760c4bf280f68aad331f7b57ff1e` | No (tests only) |
| `resources/taxsim35/taxsim35-unix.exe` | Linux ELF, x86-64 | Not found | 4,545,432 | `c83d6a214e49f0206f69eb675502968ffe1109dff4420f5ec4b8d85f7386055d` | No (tests only) |
| `resources/taxsimtest/taxsimtest-linux.exe` | Linux ELF, x86-64 | cd2026081819 | 2,129,624 | `00a321d2467ba011992f8b83c6e485a9b710c48fca4262a23fec1de26942a89b` | Yes, on Linux |
| `resources/taxsimtest/taxsimtest-osx.exe` | macOS Mach-O, x86-64 | cd2026081819 | 2,070,264 | `4a17af9c2adbea27b1e6cce240610aede264e008bcdf64b131e0c81220f62b8c` | Yes, on macOS |
| `resources/taxsimtest/taxsimtest-windows.exe` | Windows PE, x86-64 | cd2026081318 | 3,035,784 | `a8207e7cf207ee9ce066eedc51cc5dd531c956de0a8b567fca1933ca0fa0e9c3` | Yes, on Windows |

- `resources/taxsim35/taxsim35-unix.exe` needs no shared libraries (statically linked).
- `resources/taxsimtest/taxsimtest-linux.exe` needs glibc 2.34 or newer, and `libc.so.6`, `libgcc_s.so.1`, `libgfortran.so.5`, `libm.so.6`, `libquadmath.so.0`.
<!-- END GENERATED: taxsim-binaries -->

- **Source.** NBER distributes these as compiled programs; their source is not in this repository. `resources/taxsimtest/README.md` records where each is downloaded from and how a new build is checked before it is committed.
- **Signatures.** None is code-signed: the macOS build is unsigned (`codesign` reports "not signed at all") and the Windows build has no Authenticode certificate. Check the hashes above instead (`shasum -a 256 <file>` on macOS and Linux, `Get-FileHash <file>` in PowerShell).
- **Platforms.** All three are x86-64. On Apple silicon Macs the macOS build runs under Rosetta 2, which must be installed. There is no build for ARM Linux.
- **Linux requirements.** The Linux build needs glibc 2.34 or newer and the GNU Fortran runtime, as listed under the table. glibc 2.34 rules out Red Hat Enterprise Linux 8 (glibc 2.28) and Ubuntu 20.04 (glibc 2.31); it is met by Red Hat Enterprise Linux 9 and Ubuntu 22.04. This is separate from the Python packages, which install on older systems. The Fortran runtime is the `libgfortran5` and `libquadmath0` packages on Debian and Ubuntu, `libgfortran` and `libquadmath` on Red Hat systems; without it, records before 2021 fail with "error while loading shared libraries". On a system that cannot meet these, compute only 2021 and later.
- **Libraries.** The macOS build links only the system library (`libSystem`). The Linux build links the libraries listed under the table. The Windows build imports only from `KERNEL32.dll` and `msvcrt.dll`. None of the three imports a socket, DNS or HTTP function.

## Python versions

<!-- BEGIN GENERATED: python-versions -->
- `pyproject.toml` requires Python `>=3.10`.
- CI runs the test suite on `ubuntu-latest`, `macos-latest`, `windows-latest` with Python 3.10 and 3.11.
- As of 2026-10-09T19:00:00Z, the latest policyengine-us (2.38.1) requires Python `<3.15,>=3.11`. Which policyengine-us each Python version installs:

| Python | policyengine-us | policyengine-core |
|---|---|---|
| 3.10 | 1.783.0 | 3.31.1 |
| 3.11 | 2.38.1 | 3.32.29 |
| 3.12 | 2.38.1 | 3.32.29 |
| 3.13 | 2.38.1 | 3.32.29 |
| 3.14 | 2.38.1 | 3.32.29 |
<!-- END GENERATED: python-versions -->

What this means in practice:

- **Use Python 3.11 or later.** policyengine-us stopped supporting Python 3.10 after release 1.783.0 (July 2026), so a Python 3.10 installation keeps the tax rules of that release and gets none of the corrections made since.
- **Python 3.9 and earlier cannot install policyengine-taxsim.** For an older system Python, install a newer Python alongside it (from python.org, your package manager, or `uv python install`) in its own environment; the emulator does not depend on the system Python.
- CI tests Python 3.10 and 3.11. Python 3.12 to 3.14 install the same packages, some at newer versions (see the table below), but are not tested in CI.

## Dependencies

### Direct

What `pyproject.toml` requires:

<!-- BEGIN GENERATED: direct-dependencies -->
| Requirement | Installed |
|---|---|
| `policyengine-us>=1.711.0` | Always |
| `spm-calculator<1; python_version < "3.11"` | Always |
| `pandas` | Always |
| `PyYAML` | Always |
| `click` | Always |
| `matplotlib` | Always |
| `numpy` | Always |
| `tqdm` | Always |
| `fastapi>=0.100.0` | Only with `policyengine-taxsim[api]` |
| `uvicorn>=0.20.0` | Only with `policyengine-taxsim[api]` |
| `resend>=2.0.0` | Only with `policyengine-taxsim[api]` |
<!-- END GENERATED: direct-dependencies -->

### Everything installed

Every package an installation pulls in, resolved for Linux x86-64, with the package that requires it and its license from PyPI. Generated from the snapshot in [`docs/dependencies/`](dependencies/):

<!-- BEGIN GENERATED: dependency-tree -->
| Package | 3.10 | 3.11 | 3.12 | 3.13 | 3.14 | Required by | License |
|---|---|---|---|---|---|---|---|
| annotated-types | 0.8.0 | 0.8.0 | 0.8.0 | 0.8.0 | 0.8.0 | pydantic | MIT |
| anyio | 4.15.1 | 4.15.1 | 4.15.1 | 4.15.1 | 4.15.1 | httpx, httpx2 | MIT |
| asttokens | 3.0.2 | 3.0.2 | 3.0.2 | 3.0.2 | 3.0.2 | stack-data | Apache 2.0 |
| blosc2 | 4.3.3 | 4.14.1 | 4.14.1 | 4.14.1 | 4.14.1 | tables | BSD-3-Clause |
| census | 0.8.27 | 0.8.27 | 0.8.27 | 0.8.27 | 0.8.27 | spm-calculator | BSD |
| certifi | 2026.7.22 | 2026.7.22 | 2026.7.22 | 2026.7.22 | 2026.7.22 | httpcore, httpx, requests | MPL-2.0 |
| charset-normalizer | 3.5.2 | 3.5.2 | 3.5.2 | 3.5.2 | 3.5.2 | requests | MIT |
| click | 8.5.0 | 8.5.0 | 8.5.0 | 8.5.0 | 8.5.0 | huggingface-hub, policyengine-taxsim | BSD-3-Clause |
| contourpy | 1.3.2 | 1.3.3 | 1.4.0 | 1.4.0 | 1.4.0 | matplotlib | BSD License |
| cycler | 0.12.1 | 0.12.1 | 0.12.1 | 0.12.1 | 0.12.1 | matplotlib | BSD License |
| decorator | 5.3.1 | 5.3.1 | 5.3.1 | 5.3.1 | 5.3.1 | ipython | BSD-2-Clause |
| dpath | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | policyengine-core | MIT |
| et-xmlfile | 2.0.0 | 2.0.0 | 2.0.0 | 2.0.0 | 2.0.0 | openpyxl | MIT |
| exceptiongroup | 1.3.1 | - | - | - | - | anyio, ipython, pytest | MIT License |
| executing | 2.2.1 | 2.2.1 | 2.2.1 | 2.2.1 | 2.2.1 | stack-data | MIT |
| filelock | 4.0.12 | 4.0.12 | 4.0.12 | 4.0.12 | 4.0.12 | huggingface-hub | MIT |
| fonttools | 4.65.0 | 4.66.1 | 4.66.1 | 4.66.1 | 4.66.1 | matplotlib | MIT |
| fsspec | 2026.9.0 | 2026.9.0 | 2026.9.0 | 2026.9.0 | 2026.9.0 | huggingface-hub | BSD-3-Clause |
| h11 | 0.16.0 | 0.16.0 | 0.16.0 | 0.16.0 | 0.16.0 | httpcore, httpcore2 | MIT |
| h2 | - | 4.4.1 | 4.4.1 | 4.4.1 | 4.4.1 | httpx | MIT |
| h5py | 3.16.0 | 3.16.0 | 3.16.0 | 3.16.0 | 3.16.0 | policyengine-core | BSD-3-Clause |
| hf-xet | 1.7.0 | 1.7.0 | 1.7.0 | 1.7.0 | 1.7.0 | huggingface-hub | Apache-2.0 |
| hpack | - | 4.2.0 | 4.2.0 | 4.2.0 | 4.2.0 | h2 | MIT |
| httpcore | - | 1.0.9 | 1.0.9 | 1.0.9 | 1.0.9 | httpx | BSD-3-Clause |
| httpcore2 | 2.13.1 | 2.13.1 | 2.13.1 | 2.13.1 | 2.13.1 | httpx2 | BSD-3-Clause |
| httpx | - | 0.28.1 | 0.28.1 | 0.28.1 | 0.28.1 | blosc2 | BSD-3-Clause |
| httpx2 | 2.13.1 | 2.13.1 | 2.13.1 | 2.13.1 | 2.13.1 | huggingface-hub | BSD-3-Clause |
| huggingface-hub | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 | policyengine-core | Apache-2.0 |
| hyperframe | - | 6.1.0 | 6.1.0 | 6.1.0 | 6.1.0 | h2 | MIT License |
| idna | 3.20 | 3.20 | 3.20 | 3.20 | 3.20 | anyio, httpx, httpx2, requests | BSD-3-Clause |
| iniconfig | 2.3.1 | 2.3.1 | 2.3.1 | 2.3.1 | 2.3.1 | pytest | MIT |
| ipython | 8.39.0 | 8.39.0 | 8.39.0 | 8.39.0 | 8.39.0 | policyengine-core, pyvis | BSD-3-Clause |
| jedi | 0.20.0 | 0.20.0 | 0.20.0 | 0.20.0 | 0.20.0 | ipython | MIT |
| jellyfish | 1.2.1 | 1.2.1 | 1.2.1 | 1.2.1 | 1.2.1 | us | MIT License |
| jinja2 | 3.1.6 | 3.1.6 | 3.1.6 | 3.1.6 | 3.1.6 | pyvis | BSD License |
| jsonpickle | 4.1.3 | 4.1.3 | 4.1.3 | 4.1.3 | 4.1.3 | pyvis | BSD-3-Clause |
| kiwisolver | 1.5.1 | 1.5.1 | 1.5.1 | 1.5.1 | 1.5.1 | matplotlib | BSD License |
| markdown-it-py | - | 4.2.0 | 4.2.0 | 4.2.0 | 4.2.0 | rich | MIT License |
| markupsafe | 3.0.4 | 3.0.4 | 3.0.4 | 3.0.4 | 3.0.4 | jinja2 | BSD-3-Clause |
| matplotlib | 3.10.9 | 3.11.2 | 3.11.2 | 3.11.2 | 3.11.2 | policyengine-taxsim | Python Software Foundation License |
| matplotlib-inline | 0.2.2 | 0.2.2 | 0.2.2 | 0.2.2 | 0.2.2 | ipython | BSD-3-Clause |
| mdurl | - | 0.1.2 | 0.1.2 | 0.1.2 | 0.1.2 | markdown-it-py | MIT License |
| microdf-python | 1.5.11 | 1.5.11 | 1.5.11 | 1.5.11 | 1.5.11 | policyengine-core, policyengine-us | MIT |
| msgpack | 1.2.3 | 1.2.3 | 1.2.3 | 1.2.3 | 1.2.3 | blosc2 | Apache-2.0 |
| ndindex | 1.10.1 | 1.10.1 | 1.10.1 | 1.10.1 | 1.10.1 | blosc2 | MIT |
| networkx | 3.4.2 | 3.6.1 | 3.7 | 3.7 | 3.7 | pyvis | BSD License |
| numexpr | 2.14.1 | 2.14.2 | 2.14.2 | 2.14.2 | 2.14.2 | blosc2, policyengine-core, tables | MIT |
| numpy | 2.2.6 | 2.4.6 | 2.5.3 | 2.5.3 | 2.5.3 | blosc2, contourpy, h5py, matplotlib, microdf-python, numexpr, pandas, policyengine-core, policyengine-taxsim, spm-calculator, tables | BSD License |
| openpyxl | 3.1.5 | 3.1.5 | 3.1.5 | 3.1.5 | 3.1.5 | spm-calculator | MIT |
| packaging | 26.3 | 26.3 | 26.3 | 26.3 | 26.3 | huggingface-hub, matplotlib, plotly, pytest, tables, wheel | Apache-2.0 OR BSD-2-Clause |
| pandas | 2.3.3 | 3.0.6 | 3.0.6 | 3.0.6 | 3.0.6 | microdf-python, policyengine-core, policyengine-taxsim, policyengine-us, spm-calculator | BSD License |
| parso | 0.8.7 | 0.8.7 | 0.8.7 | 0.8.7 | 0.8.7 | jedi | MIT |
| pexpect | 4.9.0 | 4.9.0 | 4.9.0 | 4.9.0 | 4.9.0 | ipython | ISC license |
| pillow | 12.3.0 | 12.3.0 | 12.3.0 | 12.3.0 | 12.3.0 | matplotlib | MIT-CMU |
| plotly | 5.24.1 | 5.24.1 | 5.24.1 | 5.24.1 | 5.24.1 | policyengine-core | MIT |
| pluggy | 1.6.0 | 1.6.0 | 1.6.0 | 1.6.0 | 1.6.0 | pytest | MIT |
| policyengine-core | 3.31.1 | 3.32.29 | 3.32.29 | 3.32.29 | 3.32.29 | policyengine-us | GNU Affero General Public License v3 |
| policyengine-us | 1.783.0 | 2.38.1 | 2.38.1 | 2.38.1 | 2.38.1 | policyengine-taxsim | GNU Affero General Public License v3 |
| prompt-toolkit | 3.0.53 | 3.0.53 | 3.0.53 | 3.0.53 | 3.0.53 | ipython | BSD License |
| psutil | 6.1.1 | 6.1.1 | 6.1.1 | 6.1.1 | 6.1.1 | policyengine-core | BSD-3-Clause |
| ptyprocess | 0.7.0 | 0.7.0 | 0.7.0 | 0.7.0 | 0.7.0 | pexpect | ISC License (ISCL) |
| pure-eval | 0.2.4 | 0.2.4 | 0.2.4 | 0.2.4 | 0.2.4 | stack-data | MIT |
| py-cpuinfo | 9.0.0 | 9.0.0 | 9.0.0 | 9.0.0 | 9.0.0 | tables | MIT |
| pydantic | 2.14.0 | 2.14.0 | 2.14.0 | 2.14.0 | 2.14.0 | blosc2 | MIT |
| pydantic-core | 2.50.0 | 2.50.0 | 2.50.0 | 2.50.0 | 2.50.0 | pydantic | MIT |
| pygments | 2.21.0 | 2.21.0 | 2.21.0 | 2.21.0 | 2.21.0 | ipython, pytest, rich | BSD-2-Clause |
| pyparsing | 3.3.3 | 3.3.3 | 3.3.3 | 3.3.3 | 3.3.3 | matplotlib | MIT |
| pytest | 8.4.2 | 9.1.1 | 9.1.1 | 9.1.1 | 9.1.1 | policyengine-core | MIT |
| python-dateutil | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 | 2.9.0.post0 | matplotlib, pandas | Dual License |
| pytz | 2026.5 | - | - | - | - | pandas | MIT |
| pyvis | 0.3.2 | 0.3.2 | 0.3.2 | 0.3.2 | 0.3.2 | policyengine-core | BSD |
| pyyaml | 6.0.3 | 6.0.3 | 6.0.3 | 6.0.3 | 6.0.3 | huggingface-hub, policyengine-taxsim | MIT |
| requests | 2.34.2 | 2.34.2 | 2.34.2 | 2.34.2 | 2.34.2 | blosc2, census, policyengine-core, spm-calculator | Apache-2.0 |
| rich | - | 15.0.0 | 15.0.0 | 15.0.0 | 15.0.0 | blosc2 | MIT |
| six | 1.17.0 | 1.17.0 | 1.17.0 | 1.17.0 | 1.17.0 | python-dateutil | MIT |
| sortedcontainers | 2.4.0 | 2.4.0 | 2.4.0 | 2.4.0 | 2.4.0 | policyengine-core | Apache 2.0 |
| spm-calculator | 0.3.1 | 1.0.0.post1 | 1.0.0.post1 | 1.0.0.post1 | 1.0.0.post1 | policyengine-taxsim, policyengine-us | MIT |
| stack-data | 0.6.3 | 0.6.3 | 0.6.3 | 0.6.3 | 0.6.3 | ipython | MIT |
| standard-imghdr | 3.13.0 | 3.13.0 | 3.13.0 | 3.13.0 | 3.13.0 | policyengine-core | PSF-2.0 |
| tables | 3.10.1 | 3.11.1 | 3.11.1 | 3.11.1 | 3.11.1 | policyengine-us | BSD 3-Clause License |
| tenacity | 9.2.1 | 9.2.1 | 9.2.1 | 9.2.1 | 9.2.1 | plotly | Apache-2.0 |
| threadpoolctl | 3.7.0 | 3.7.0 | 3.7.0 | 3.7.0 | 3.7.0 | blosc2 | BSD-3-Clause |
| tomli | 2.5.0 | - | - | - | - | huggingface-hub, pytest | MIT |
| tqdm | 4.70.1 | 4.70.1 | 4.70.1 | 4.70.1 | 4.70.1 | huggingface-hub, policyengine-taxsim, policyengine-us | MPL-2.0 AND MIT |
| traitlets | 5.16.1 | 5.16.1 | 5.16.1 | 5.16.1 | 5.16.1 | ipython, matplotlib-inline | BSD License |
| truststore | 0.10.4 | 0.10.4 | 0.10.4 | 0.10.4 | 0.10.4 | httpcore2, httpx2 | MIT |
| typing-extensions | 4.16.0 | 4.16.0 | 4.16.0 | 4.16.0 | 4.16.0 | anyio, exceptiongroup, httpx2, huggingface-hub, ipython, pydantic, pydantic-core, tables, typing-inspection | PSF-2.0 |
| typing-inspection | 0.4.4 | 0.4.4 | 0.4.4 | 0.4.4 | 0.4.4 | pydantic | MIT |
| tzdata | 2026.5 | - | - | - | - | pandas | Apache-2.0 |
| urllib3 | 2.8.0 | 2.8.0 | 2.8.0 | 2.8.0 | 2.8.0 | requests | MIT |
| us | 4.0.0 | 4.0.0 | 4.0.0 | 4.0.0 | 4.0.0 | spm-calculator | BSD-style (full text in metadata) |
| wcwidth | 0.9.2 | 0.9.2 | 0.9.2 | 0.9.2 | 0.9.2 | prompt-toolkit | MIT License |
| wheel | 0.48.0 | 0.48.0 | 0.48.0 | 0.48.0 | 0.48.0 | policyengine-core | MIT |

Packages, not counting policyengine-taxsim itself: 85 on Python 3.10, 89 on Python 3.11, 89 on Python 3.12, 89 on Python 3.13, 89 on Python 3.14.

Packages that differ from Linux on other platforms:

- Windows (x86-64): on Python 3.10, adds colorama; leaves out pexpect, ptyprocess; on Python 3.11 to 3.14, adds colorama, tzdata; leaves out h2, hpack, httpcore, httpx, hyperframe, markdown-it-py, mdurl, pexpect, ptyprocess, rich.
- macOS (Apple silicon): on Python 3.11 to 3.14, leaves out h2, hpack, httpcore, httpx, hyperframe, markdown-it-py, mdurl, rich.
<!-- END GENERATED: dependency-tree -->

Most of these come from policyengine-core and policyengine-us rather than from the emulator. Some exist for tasks a tax calculation never performs: pytest and IPython (developer tools), plotly, matplotlib and pyvis (charts), huggingface-hub (dataset downloads), census, openpyxl and us (spm-calculator's survey tools). They are installed because their parent packages declare them, not because a run uses them.

### The snapshot

The snapshot fixes one reviewed set of versions. Each `docs/dependencies/requirements-py3.X.txt` lists every package with its version and SHA-256 hashes, and `snapshot.json` records the platform differences and licenses. To regenerate it for a later date:

<!-- BEGIN GENERATED: snapshot-command -->
```bash
python scripts/generate_docs_reference.py --refresh-dependencies 2026-10-09T19:00:00Z
```

The committed snapshot was resolved with uv 0.11.7 (9d177269e 2026-04-15 aarch64-apple-darwin) for `x86_64-manylinux_2_28` and packages published before 2026-10-09T19:00:00Z.
<!-- END GENERATED: snapshot-command -->

The resolution is reproducible: re-running the command with the same timestamp gives the same versions, as long as PyPI still has them. For a platform other than Linux, run the `uv pip compile` command at the top of a snapshot file with a different `--python-platform` (for example `x86_64-pc-windows-msvc`).

## Installing without internet access

On a machine with internet access, download every file the installation needs. This example targets a Linux x86-64 server with Python 3.11, the platform the snapshot is resolved for:

```bash
pip download --dest wheels --only-binary=:all: \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --python-version 3.11 \
    --require-hashes -r docs/dependencies/requirements-py3.11.txt
pip download --dest wheels --only-binary=:all: --no-deps \
    --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
    --python-version 3.11 \
    policyengine-taxsim==3.1.1
```

Both `--platform` flags are needed: pip matches each one exactly, and the packages' Linux files carry one tag or the other. For another Python version, change `--python-version` and the requirements file. On Windows and macOS a few packages differ (see the list under the dependency table), so first resolve the snapshot for that platform: run the `uv pip compile` command at the top of the requirements file with a different `--python-platform`, then download with that platform's tag (`win_amd64` for 64-bit Windows). If the connected machine has the same operating system and Python version as the target, leave out `--platform` and `--python-version`.

Copy `wheels/` and the requirements file to the target machine, then install from them with no network access:

```bash
python3.11 -m venv taxsim-env
taxsim-env/bin/pip install --no-index --find-links wheels \
    --require-hashes -r requirements-py3.11.txt
taxsim-env/bin/pip install --no-index --find-links wheels --no-deps \
    policyengine-taxsim==3.1.1
```

`--require-hashes` makes pip refuse any file whose SHA-256 differs from the snapshot. To install into an internal package repository instead, upload the contents of `wheels/` and install `policyengine-taxsim==3.1.1` from it as usual.

Check the installation. With the snapshot's policyengine-us (2.38.1) this prints `fiitax` 4358 and `siitax` 2255; other versions can differ:

```bash
printf 'taxsimid,year,state,mstat,page,pwages\n1,2023,33,1,30,52000\n' | taxsim-env/bin/policyengine-taxsim
```

## Updates and patching

- The package never updates itself. Upgrades happen only when you run pip.
- policyengine-taxsim and policyengine-us release frequently; policyengine-us released three versions on 2026-10-09 alone. For production work, pick versions, review them once, and keep the downloaded files; see [Versions and pinning](design.md#versions-and-pinning).
- To scan a snapshot for published vulnerabilities, run `pip-audit` against it (it queries the PyPI and OSV vulnerability databases):

  ```bash
  uvx pip-audit --disable-pip --require-hashes -r docs/dependencies/requirements-py3.11.txt
  ```

  On 2026-10-09 this found no known vulnerabilities in the Python 3.11 to 3.14 snapshots. The Python 3.10 snapshot had one, in pytest 8.4.2 ([PYSEC-2026-1845](https://osv.dev/vulnerability/PYSEC-2026-1845), fixed in 9.0.3), a test tool that a run never imports.
- Report security problems through [GitHub](https://github.com/PolicyEngine/policyengine-taxsim/issues) or to hello@policyengine.org.
