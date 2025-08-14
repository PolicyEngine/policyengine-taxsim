# PolicyEngine-TAXSIM

A TAXSIM emulator using the PolicyEngine US federal and state tax calculator, with comparison tools and an interactive dashboard for analyzing results.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
  - [From Source](#from-source)
  - [From PyPI](#from-pypi)
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
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

This project provides an emulator for TAXSIM-35, utilizing PolicyEngine's US federal and state tax calculator. It processes tax calculations through a CSV input format compatible with TAXSIM-35 specifications.

### Key Features

- **PolicyEngine Integration**: Calculate taxes using PolicyEngine's comprehensive US tax system
- **TAXSIM Compatibility**: Run native TAXSIM-35 calculations for comparison
- **Automated Comparison**: Compare results between PolicyEngine and TAXSIM with configurable tolerances
- **Interactive Dashboard**: Visualize and explore tax calculation comparisons across years and states
- **Data Analysis**: Generate detailed statistics and mismatch reports
- **Flexible CLI**: Multiple commands for different use cases

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/PolicyEngine/policyengine-taxsim.git
   cd policyengine-taxsim
   ```
2. Create a virtual environment:
   ```bash
   # For Windows
   python -m venv venv
   venv\Scripts\activate

   # For macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the package:
   ```bash
   pip install -e .
   ```
4. To update the project codebase (for existing project)
    ```bash
   git pull origin main
   ```

5. To update dependencies used by the project (for existing project):
   ```bash
   pip install -e . --upgrade
   ```

### From PyPI

```bash
pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git
```

## Usage

The CLI provides several commands for different use cases. All commands are accessed through the main CLI interface:

```bash
python policyengine_taxsim/cli.py [COMMAND] [OPTIONS]
```

### PolicyEngine Calculations

Calculate taxes using PolicyEngine:

```bash
python policyengine_taxsim/cli.py policyengine your_input_file.csv
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
python policyengine_taxsim/cli.py policyengine input.csv --output results.csv --logs --sample 1000
```

### TAXSIM Calculations

Run native TAXSIM-35 calculations:

```bash
python policyengine_taxsim/cli.py taxsim your_input_file.csv
```

**Options:**
| Option | Description |
|--------|-------------|
| `--output`, `-o` | Output file path (default: taxsim_output.csv) |
| `--sample N` | Sample N records from input |
| `--taxsim-path` | Custom path to TAXSIM executable |

**Example:**
```bash
python policyengine_taxsim/cli.py taxsim input.csv --output taxsim_results.csv
```

### Comparison Analysis

Compare PolicyEngine and TAXSIM results side-by-side:

```bash
python policyengine_taxsim/cli.py compare your_input_file.csv
```

**Options:**
| Option | Description |
|--------|-------------|
| `--output-dir` | Directory for comparison results (default: comparison_output) |
| `--save-mismatches` | Save detailed mismatch files |
| `--year` | Override tax year for calculations |
| `--sample N` | Sample N records for comparison |
| `--disable-salt` | Disable SALT deduction in PolicyEngine |
| `--logs` | Generate PolicyEngine YAML logs |

The comparison uses a fixed $15 tolerance for both federal and state tax comparisons.

**Example:**
```bash
python policyengine_taxsim/cli.py compare input.csv --save-mismatches --sample 5000 --year 2023
```

This generates:
- `policyengine_results_2023.csv` - PolicyEngine output
- `taxsim_results_2023.csv` - TAXSIM output  
- `comparison_report_2023.txt` - Summary statistics
- `federal_mismatches_2023.csv` - Federal tax mismatches (if `--save-mismatches`)
- `state_mismatches_2023.csv` - State tax mismatches (if `--save-mismatches`)

### Data Sampling

Extract a sample from large datasets:

```bash
python policyengine_taxsim/cli.py sample-data input.csv --sample 1000
```

**Options:**
| Option | Description |
|--------|-------------|
| `--sample N` | Number of records to sample |
| `--output`, `-o` | Output file (auto-generated if not specified) |

## Dashboard

The project includes an interactive React dashboard for visualizing and exploring tax calculation comparisons across multiple years and states.

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

- **Multi-Year Analysis**: Compare results across tax years 2021-2024
- **State-by-State Breakdown**: Detailed analysis by US state
- **Interactive Filtering**: Filter by state and view specific mismatches
- **Match/Mismatch Visualization**: Visual indicators for calculation accuracy
- **Household-Level Detail**: Expand individual households to see variable-by-variable comparisons
- **Export Functionality**: Download comparison data for further analysis
- **Fixed Tolerance**: Uses $15 tolerance for realistic tax calculation comparisons
- **GitHub Integration**: View related issues and discussions

The dashboard automatically loads pre-generated comparison data from the `public/data/` directory. To update this data, run comparison analyses using the CLI and copy results to the appropriate year folders.

**Production Build:**
```bash
npm run build
```

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
| sage      | Spouse age                     |                                             |
| depx      | Number of dependents           |                                             |
| age1      | First dependent's age          |                                             |
| age2      | Second dependent's age         |                                             |
| ageN      | Nth dependent's age            | Taxsim only allows up to 8 dependents       |

### Income

| Variable  | Description                                                  |
|-----------|--------------------------------------------------------------|
| pwages    | Primary taxpayer wages                                       |
| swages    | Spouse wages                                                 |
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


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License 
[MIT License](https://github.com/PolicyEngine/policyengine-taxsim?tab=License-1-ov-file#)

## Support

For issues and feature requests, please [open an issue](https://github.com/PolicyEngine/policyengine-taxsim/issues).