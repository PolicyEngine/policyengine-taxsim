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
| `west_virginia_idtl0` | August 2026 macOS | Twelve `d3`/`d4` pairs before the West Virginia row. |
| `mixed_idtl_full_first` | August 2026 macOS | `idtl` 2, 0, 0. The header and row 1 have 54 fields; rows 2 and 3 have 11 (ten basic values and the build-stamp value). Row 2 is the West Virginia profile, so its `d3`/`d4` lines precede a short row. |
| `mixed_idtl_basic_first` | August 2026 macOS | `idtl` 0, 2. The header and row 1 have 11 fields; row 2 has 54, so 43 of its fields have no column name. |

The bundled Linux build of the same date writes identical bytes for all three
August captures.

These are the triggers observed for these profiles, not a mechanism. On the
510-record grid below (51 states, 2024 and 2026, five filer profiles), the
20260521 build wrote 36 `d2` lines, six before each Utah row with a filer aged
73 or older, and the August macOS and Linux builds wrote 240 `d3`/`d4` lines,
24 before each West Virginia row. The September 2026 macOS build
(`02286eda…`, from the unmerged #1206) wrote none.

```python
rows = ["taxsimid,year,state,mstat,page,sage,depx,pwages,gssi,pensions,idtl"]
profiles = [  # mstat, page, sage, pwages, gssi, pensions
    (1, 40, 0, 50000, 0, 0),
    (1, 73, 0, 30000, 0, 0),
    (2, 75, 74, 30000, 20000, 10000),
    (1, 80, 0, 0, 25000, 40000),
    (2, 45, 44, 150000, 0, 0),
]
taxsimid = 0
for state in range(1, 52):
    for year in (2024, 2026):
        for mstat, page, sage, pwages, gssi, pensions in profiles:
            taxsimid += 1
            rows.append(
                f"{taxsimid},{year},{state},{mstat},{page},{sage},0,"
                f"{pwages},{gssi},{pensions},2"
            )
open("grid.csv", "w").write("\n".join(rows) + "\n")
```

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
