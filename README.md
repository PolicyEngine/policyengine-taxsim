# PolicyEngine-TAXSIM

A TAXSIM emulator using the PolicyEngine US federal and state tax calculator.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
  - [From Source](#from-source)
  - [From PyPI](#from-pypi)
- [Usage](#usage)
- [Input Variables](#input-variables)
  - [Demographics](#demographics)
  - [Income](#income)
  - [Output Types](#output-types)
  - [Household Types](#household-types)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

This project provides an emulator for TAXSIM-35, utilizing PolicyEngine's US federal and state tax calculator. It processes tax calculations through a CSV input format compatible with TAXSIM-35 specifications.

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

Run the simulation by providing your input CSV file:

```bash
python policyengine_taxsim/cli.py your_input_file.csv
```

The output will be generated as `output.csv` in the same directory.

### Optional Arguments

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Specify the output file path (default: output.txt) |
| `--logs` | Generate PolicyEngine YAML Tests Logs |
| `--disable-salt` | Set State and Local Sales or Income Taxes used for the SALT deduction to 0 |

Example with optional arguments:
```bash
python policyengine_taxsim/cli.py your_input_file.csv --logs --disable-salt
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
| psemp     | Spouse self-employment income                                |
| pensions  | Taxable private pension income                               |
| psemp     | Spouse self-employment income                                |
| scorp     | Partnership/S-corp income                                    |
| pbusinc   | Primary taxpayer Business income that qualifies for the QBID |


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