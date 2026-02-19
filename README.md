# PolicyEngine-TAXSIM

A comprehensive TAXSIM emulator using the PolicyEngine US federal and state tax calculator, with advanced comparison tools and an interactive dashboard for analyzing tax calculation accuracy across different scenarios.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [From Source](#from-source)
  - [From GitHub](#from-github)
- [Usage](#usage)
  - [PolicyEngine Calculations](#policyengine-calculations)
  - [TAXSIM Calculations](#taxsim-calculations)
  - [Comparison Analysis](#comparison-analysis)
  - [Data Sampling](#data-sampling)
- [Dashboard](#dashboard)
  - [Setup](#dashboard-setup)
  - [Features](#dashboard-features)
- [Input Variables](#input-variables)
  - [Demographics](#demographics)
  - [Income](#income)
  - [Expenses](#expenses)
  - [Output Types](#output-types)
- [State-Specific Features](#state-specific-features)
- [Output Variables](#output-variables)


## Overview

This project provides a high-fidelity emulator for TAXSIM-35, leveraging PolicyEngine's comprehensive US federal and state tax calculator. It enables researchers, analysts, and policymakers to run large-scale tax microsimulations with full compatibility to TAXSIM-35 input/output formats.

### Key Features

- **High-Performance Microsimulation**: Process thousands of households simultaneously using PolicyEngine's vectorized calculations
- **TAXSIM-35 Compatibility**: Full compatibility with TAXSIM input CSV format and output variables
- **Advanced State Handling**: Correctly handles state-specific tax conformity rules (e.g., states that adopt federal AGI vs federal taxable income)
- **Comprehensive Comparison Tools**: Side-by-side comparison of PolicyEngine vs TAXSIM results with detailed mismatch analysis
- **Interactive Dashboard**: React-based dashboard for exploring results across years, states, and household characteristics
- **Flexible Output Options**: Standard, full, and text description output formats matching TAXSIM specifications
- **YAML Test Generation**: Generate PolicyEngine test cases for reproducibility and validation

## Quick Start

```bash
# Install (requires uv: https://docs.astral.sh/uv/getting-started/installation/)
uv pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git

# Run a comparison analysis on sample data
policyengine-taxsim compare your_data.csv --sample 1000 --year 2021
```

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/PolicyEngine/policyengine-taxsim.git
   cd policyengine-taxsim
   ```
2. Create a virtual environment and install:
   ```bash
   uv venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. To update the project codebase (for existing project):
    ```bash
   git pull origin main
   ```

4. To update dependencies used by the project (for existing project):
   ```bash
   uv pip install -e . --upgrade
   ```

### From GitHub

```bash
uv pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git
```

## Usage

The CLI provides several commands for different use cases. All commands are accessed through the main CLI interface:

```bash
policyengine-taxsim [COMMAND] [OPTIONS]
```

### PolicyEngine Calculations

Calculate taxes using PolicyEngine:

```bash
policyengine-taxsim policyengine your_input_file.csv
```

**Options:**
| Option | Description |
|--------|-------------|
| `--output`, `-o` | Specify the output file path (default: output.txt) |
| `--logs` | Generate PolicyEngine YAML Tests Logs |
| `--disable-salt` | Set State and Local Sales or Income Taxes used for the SALT deduction to 0 |
| `--sample N` | Sample N records from input for testing |

**Example:**
```bash
policyengine-taxsim policyengine input.csv --output results.csv --logs --sample 1000
```

### TAXSIM Calculations

Run native TAXSIM-35 calculations:

```bash
policyengine-taxsim taxsim your_input_file.csv
```

**Options:**
| Option | Description |
|--------|-------------|
| `--output`, `-o` | Output file path (default: taxsim_output.csv) |
| `--sample N` | Sample N records from input |
| `--taxsim-path` | Custom path to TAXSIM executable |

**Example:**
```bash
policyengine-taxsim taxsim input.csv --output taxsim_results.csv
```

### Comparison Analysis

Run comprehensive side-by-side comparisons between PolicyEngine and TAXSIM:

```bash
policyengine-taxsim compare your_input_file.csv
```

**Options:**
| Option | Description |
|--------|-------------|
| `--output-dir` | Directory for comparison results (default: comparison_output) |
| `--year` | Override tax year for calculations |
| `--sample N` | Sample N records for comparison |
| `--disable-salt` | Disable SALT deduction in PolicyEngine |
| `--logs` | Generate PolicyEngine YAML test logs |

The comparison uses a $15 tolerance for both federal and state tax comparisons, which accounts for reasonable rounding differences.

**Examples:**

Basic comparison:
```bash
policyengine-taxsim compare cps_households.csv --sample 1000
```

Year-specific analysis with detailed logging:
```bash
policyengine-taxsim compare input.csv --year 2023 --logs --sample 5000
```

**Output Files:**
- `comparison_results_YYYY.csv` - Consolidated results with both PolicyEngine and TAXSIM outputs for each household
- Console output with match statistics and summary

The consolidated output includes (by default):
- All input variables for each household
- Complete TAXSIM output variables
- Complete PolicyEngine output variables  
- Match/mismatch indicators for federal and state taxes
- State codes for easy filtering
- **All mismatches are automatically included** - no separate mismatch files needed

### Data Sampling

Extract a sample from large datasets:

```bash
policyengine-taxsim sample-data input.csv --sample 1000
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sample N` | Number of records to sample |
| `--output`, `-o` | Output file (auto-generated if not specified) |

## Dashboard

The project includes a comprehensive React-based interactive dashboard for visualizing and exploring tax calculation comparisons across multiple years and states.

### Dashboard Setup

1. **Navigate to the dashboard directory:**
   ```bash
   cd cps-dashboard
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm start
   ```

4. **Open your browser to [http://localhost:3000](http://localhost:3000)**

### Dashboard Features

- **Multi-Year Analysis**: Compare results across tax years 2021-2024 with year-over-year trends
- **State-by-State Breakdown**: Detailed analysis by all 50 US states plus DC
- **Interactive Filtering**: Advanced filtering by state, match status, and household characteristics
- **Variable-Level Comparisons**: Drill down to see differences in specific tax variables (v10, v32, etc.)
- **Match Rate Analytics**: Visualize federal vs state tax calculation accuracy rates
- **Household Explorer**: Expand individual households to examine all input and output variables
- **Mismatch Analysis**: Identify patterns in calculation differences
- **Export Capabilities**: Download filtered comparison data in CSV format
- **Smart Tolerance**: Uses $15 tolerance accounting for reasonable calculation differences
- **Real-Time Statistics**: Dynamic summary statistics that update with filtering
- **GitHub Integration**: Direct links to relevant issues and documentation

### Data Management

The dashboard loads comparison data from `public/data/YYYY/comparison_results_YYYY.csv` files. To update:

1. **Generate new comparison data:**
   ```bash
   policyengine-taxsim compare your_data.csv --year 2024
   ```

2. **Copy results to dashboard:**
   ```bash
   cp comparison_output/comparison_results_2024.csv cps-dashboard/public/data/2024/
   ```

3. **Restart dashboard** to load new data

**Production Build:**
```bash
npm run build
```

The dashboard provides an intuitive interface for researchers and analysts to explore large-scale tax calculation comparisons without requiring technical expertise.

## Input Variables

The emulator accepts CSV files with the following variables:

### Demographics

| Variable  | Description                    | Notes                                       |
|-----------|--------------------------------|---------------------------------------------|
| taxsimid  | Unique identifier              |                                             |
| year      | Tax year                       |                                             |
| state     | State code                     |                                             |
| mstat     | Marital status                 | Only supports: 1 (single), 2 (joint)        |
| page      | Primary taxpayer age           |                                             |
| sage      | Age of secondary taxpayer                     |                                             |
| depx      | Number of dependents           |                                             |
| age1      | First dependent's age          |                                             |
| age2      | Second dependent's age         |                                             |
| ageN      | Nth dependent's age            | Taxsim only allows up to 8 dependents       |

### Income

| Variable  | Description                                                  |
|-----------|--------------------------------------------------------------|
| pwages    | Primary taxpayer wages                                       |
| swages    | Wage and salary income of secondary taxpayer                                                 |
| intrec    | Taxable interest income                                      |
| dividends | Qualified dividend income                                    |
| ltcg      | Long-term capital gains                                      |
| stcg      | Short-term capital gains                                     |
| psemp     | Primary taxpayer self-employment income                      |
| ssemp     | Spouse self-employment income                                |
| gssi      | Social security retirement benefits                          |
| pensions  | Taxable private pension income                               |
| scorp     | Partnership/S-corp income                                    |
| pbusinc   | Primary taxpayer business income that qualifies for the QBID |


### Expenses

| Variable  | Description                    |
|-----------|--------------------------------|
| rentpaid  | Amount of rent paid            |
| mortgage  | Deductible mortgage interest   |
| proptax   | Real Estate Taxes              |
| childcare | Childcare expenses             |

### Output Types

Depending on the idtl input value it can generate output types as following:

| idtl | Description     |
|------|-----------------|
| 0    | Standard output |
| 2    | Full output     |
| 5    | Full text description output |

## Output Variables

The emulator produces all standard TAXSIM output variables:

### Basic Output (idtl = 0, 2, 5)
| Variable | Description |
|----------|-------------|
| taxsimid | Record identifier |
| year | Tax year |
| state | State code |
| fiitax | Federal income tax liability |
| siitax | State income tax liability |
| fica | FICA taxes |

### Extended Output (idtl = 2, 5)
| Variable | Description |
|----------|-------------|
| v10 | Federal adjusted gross income |
| v11 | Unemployment compensation in AGI |
| v12 | Social Security benefits in AGI |
| v13 | Zero bracket amount/standard deduction |
| v14 | Personal exemptions |
| v17 | Itemized deductions |
| v18 | Federal taxable income |
| v19 | Federal income tax before credits |
| v22 | Child tax credit |
| v23 | Additional child tax credit (refundable portion) |
| v24 | Child and dependent care credit |
| v25 | Earned income tax credit |
| v26 | Alternative minimum tax income |
| v27 | Alternative minimum tax |
| v28 | Income tax before credits |
| v29 | FICA taxes |
| v32 | **State AGI** (or federal AGI/taxable income for conformity states) |
| v34 | State standard deduction |
| v35 | State itemized deductions |
| v36 | State taxable income |
| v37 | Property tax credit |
| v38 | State child care credit |
| v39 | State earned income credit |
| v40 | Total state credits |
| qbid | Qualified business income deduction |
| niit | Net investment income tax |
| cares | COVID-related recovery rebate credit |
