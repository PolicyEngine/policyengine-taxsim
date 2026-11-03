# policyenginetaxsim

An R package for calculating US federal and state income taxes using [PolicyEngine](https://policyengine.org). It gives the same results as the `policyengine-taxsim` command line: tax years from 2021 on are computed by PolicyEngine US, and earlier years by TAXSIM-35 (see [Which engine computes each record](#which-engine-computes-each-record)).

## Requirements

- R 4.0+
- Python 3.10 to 3.13; current tax rules need 3.11 or later
- ~500MB disk space (for Python dependencies)
- Internet connection for the initial setup, or a folder of Python wheels (see [Setup without internet access](#setup-without-internet-access))

## Installation

```r
install.packages("devtools")
devtools::install_github("PolicyEngine/policyengine-taxsim",
                          subdir = "r-package/policyenginetaxsim")
```

## Setup (One-Time)

Run this once after installation. Takes 5-10 minutes.

```r
library(policyenginetaxsim)
setup_policyengine()
```

This creates a Python virtual environment and installs one released version of policyengine-taxsim from PyPI into it: the release that was current at the commit you installed this R package from. The same copy of the R package therefore installs the same policyengine-taxsim on any day. (Versions before 0.2.0 installed the `main` branch from GitHub, so what you got depended on the day of the first run.) If you skip this step, the first `policyengine_calculate_taxes()` call runs it for you.

### Pinning versions

policyengine-us, which holds the tax rules, is installed as a dependency. Unless you pin it, pip takes the newest release that fits your Python version, so two machines set up on different days can give different results for the same data. To get the same results everywhere, pin both packages:

```r
setup_policyengine(
  force = TRUE,
  policyengine_taxsim_version = "3.1.1",
  policyengine_us_version = "2.38.0"
)
```

`setup_policyengine()` ends by printing the versions it installed and this call with those versions filled in; `policyengine_versions()` shows them at any time. policyengine-us 2.x needs Python 3.11 or later. With Python 3.10, pip installs an older policyengine-us 1.x release with older tax rules; pass `python = "/path/to/python3.11"` to choose the interpreter when a machine has several.

PyPI does not keep every policyengine-us release, so a version you pin today may not be installable later. A folder of wheels is.

### Setup without internet access

`setup_policyengine()` can install from a folder of Python wheels instead of PyPI. On a machine with internet access and the same operating system, processor type and Python version as the target machine, download policyengine-taxsim and everything it depends on (add `==<version>` to choose a release other than the newest):

```bash
python -m pip download --only-binary=:all: --dest policyengine-wheels policyengine-taxsim
```

Copy the folder to the target machine and point the setup at it:

```r
setup_policyengine(wheel_dir = "path/to/policyengine-wheels")
```

The function then downloads nothing: pip runs with `--no-index --find-links`, and if no compatible Python is installed the function stops instead of downloading Miniconda. It installs the policyengine-taxsim version in the folder, so the folder also fixes every version: keep it with your results to reproduce them later. If the machine has more than one Python, pass the one the wheels were downloaded for as `python`.

## Usage

### Basic Example

```r
library(policyenginetaxsim)

# Single filer with $50,000 wages in California
my_data <- data.frame(
  year = 2023,
  state = "CA",
  mstat = 1,
  pwages = 50000
)

results <- policyengine_calculate_taxes(my_data)
print(results)
#>   taxsimid year state fiitax siitax tfica
#> 1        1 2023     5   4118   1157  3825
```

### Married Couple with Children

```r
family <- data.frame(
  year = 2023,
  state = "NY",
  mstat = 2,
  pwages = 80000,
  swages = 60000,
  depx = 2,
  age1 = 8,
  age2 = 5
)

results <- policyengine_calculate_taxes(family)
```

### Multiple Households

```r
households <- data.frame(
  year = 2023,
  state = c("CA", "TX", "NY"),
  mstat = 1,
  pwages = c(50000, 75000, 100000)
)

results <- policyengine_calculate_taxes(households)
print(results)
#>   taxsimid year state fiitax siitax  tfica
#> 1        1 2023     5   4118   1157   3825
#> 2        2 2023    44   8760      0   5738
#> 3        3 2023    33  14260   3865   7650
```

### From CSV File

```r
# Load data from CSV
my_data <- read.csv("tax_units.csv")

# Calculate taxes
results <- policyengine_calculate_taxes(my_data)

# Save results
write.csv(results, "tax_results.csv", row.names = FALSE)
```

### Detailed Output

```r
results <- policyengine_calculate_taxes(my_data, return_all_information = TRUE)
# Returns 30+ variables: AGI, deductions, credits, etc.
```

The function sets the TAXSIM `idtl` option itself (0, or 2 with `return_all_information = TRUE`) and ignores an `idtl` column in the data.

## Which engine computes each record

`policyengine_calculate_taxes()` sends each record to one of two engines by its tax year, as the `policyengine-taxsim` command line does:

| Tax year | Engine |
|---|---|
| 2021 and later | PolicyEngine US |
| Before 2021 | TAXSIM-35, the NBER program bundled with policyengine-taxsim, run on your machine |

The progress message says how many records each engine computed, and rows come back in the order of the input.

**This changed in version 0.2.0.** Earlier versions computed every year with PolicyEngine. If your data include years before 2021, those records are now computed by TAXSIM-35, so their results change. This project compares PolicyEngine with TAXSIM-35 only for 2021 and later. To compute every year with PolicyEngine as before:

```r
results <- policyengine_calculate_taxes(my_data, engine = "policyengine")
```

With records on both sides of 2021:

- The result has the columns of both engines. A cell is `NA` where the engine that computed the row does not produce that column.
- TAXSIM-35 adds a column named for its build, such as `cd2026081819`, filled only for the records it computed.
- TAXSIM-35 is an x86-64 program. On a Mac with Apple silicon it needs Rosetta 2.

## Input/Output Variables

This package uses the standard TAXSIM 35 input and output format. See the [TAXSIM 35 documentation](https://taxsim.nber.org/taxsim35/) for the full list of supported variables.

**Note:** State codes can be specified as numbers (1-51) or abbreviations ("CA", "NY", etc.).

## Compare with TAXSIM

Compare PolicyEngine results with the embedded TAXSIM executable:

```r
comparison <- compare_with_taxsim(my_data)
print(comparison)
#>   taxsimid year state fiitax_taxsim fiitax_pe fiitax_diff fiitax_match ...
#> 1        1 2023     5          4118      4118           0         TRUE ...

# Check match rates
mean(comparison$fiitax_match)  # Federal match rate
mean(comparison$siitax_match)  # State match rate

# Detailed summary
summary_comparison(comparison)
```

## Troubleshooting

```r
# Check if setup is complete
check_policyengine_setup()

# Reinstall if something went wrong
setup_policyengine(force = TRUE)
```

## License

MIT
