# TAXSIM stdout captures

Each `<name>.stdout.txt` is the verbatim stdout of a real taxsimtest binary
fed `<name>.input.csv` on stdin:

```bash
<binary> < <name>.input.csv > <name>.stdout.txt
```

Every capture exited 0 with empty stderr. They were captured on 2026-10-10 on
macOS 26.6.2 (arm64, running the x86-64 binaries under Rosetta).
`tests/test_taxsim_debug_output.py` reads its expected values from these files
and re-runs the binaries to check them byte for byte when the binary is
available. `.gitattributes` keeps them LF on every platform.

| Capture | Binary | What it shows |
| --- | --- | --- |
| `utah_elderly_idtl2` | 20260521 macOS | Six `d2` lines before the row of record 2 (Utah, age 73). Record 3 (age 72) and record 1 (California) have none. |
| `utah_elderly_first_idtl0` | 20260521 macOS | The same records with record 2 first: its six lines come before the header. |
| `utah_elderly_consecutive_idtl2` | 20260521 macOS | Three consecutive Utah records (single 74, single 80, joint 74/74 with Social Security), each preceded by its own six lines. |
| `utah_elderly_idtl5` | 20260521 macOS | Verbose output (`idtl=5`) for record 2. The six lines sit before `Basic Output:`. |
| `west_virginia_idtl0` | August 2026 macOS | Twelve `d3`/`d4` pairs before the West Virginia row. The bundled Linux build of the same date writes identical bytes. |

These are the triggers observed for these profiles, not a mechanism. On a
510-record grid (51 states, 2024 and 2026, five filer profiles), the 20260521
build wrote `d2` lines only before Utah rows with a filer aged 73 or older, and
the August builds wrote `d3`/`d4` lines before every West Virginia row. The
September 2026 macOS build (`02286eda…`, from the unmerged #1206) wrote none.

## Binaries

| Build | Header stamp | SHA-256 | Where to get it |
| --- | --- | --- | --- |
| 20260521 macOS | `"cdate-20260521"` | `0d9e43a983055d44eec9e5de7edfc933fa061b2a336716d760fe98abf4336319` | Bundled in policyengine-taxsim 2.30.0. In this repository's history as git blob `9e91184e205744a4e2049b2bcdd95a1c7fb0e56c` (`resources/taxsimtest/taxsimtest-osx.exe` at commit 9aa9c88, #928). |
| August 2026 macOS | `"cd2026081819"` | `4a17af9c2adbea27b1e6cce240610aede264e008bcdf64b131e0c81220f62b8c` | `resources/taxsimtest/taxsimtest-osx.exe` since #1150. |
| August 2026 Linux | `"cd2026081819"` | `00a321d2467ba011992f8b83c6e485a9b710c48fca4262a23fec1de26942a89b` | `resources/taxsimtest/taxsimtest-linux.exe`. Run on macOS with `resources/taxsimtest/taxsim-docker-wrapper.sh`. |

To extract the 20260521 binary from a full clone:

```bash
git cat-file blob 9e91184e205744a4e2049b2bcdd95a1c7fb0e56c > taxsimtest-osx-20260521.exe
chmod +x taxsimtest-osx-20260521.exe
```
