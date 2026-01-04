# policyenginetaxsim

An R package for calculating US federal and state income taxes using [PolicyEngine](https://policyengine.org).

## Requirements

- R 4.0+
- ~500MB disk space (for Python dependencies)
- Internet connection (for initial setup only)

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
