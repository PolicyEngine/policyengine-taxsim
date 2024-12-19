# PolicyEngine-TAXSIM

A TAXSIM emulator using the PolicyEngine US federal and state tax calculator.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
  - [From Source](#from-source)
  - [From PyPI](#from-pypi)
- [Uninstall](#uninstall)
- [Usage](#usage)
  - [How to Run](#how-to-run)
- [Input Variables](#input-variables)
  - [Supported Inputs](#supported-inputs)
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
## Uninstall

If you encounter any unexpected system errors, you can uninstall the package and reinstall it

   ```bash
   pip uninstall policyengine_taxsim
   ```

### From PyPI

```bash
pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git
```

## Usage

### How to Run

Run the simulation by providing your input CSV file:

```bash
python policyengine_taxsim/cli.py your_input_file.csv
```

The output will be generated as `output.txt` in the same directory. (Note that the file can be used as CSV when the output type is only `idtl = 0, 2`)

## Input Variables

The emulator accepts CSV files with the following variables:

### Supported Inputs

| Variable  | Description                                                | Notes                                                                             |
|-----------|------------------------------------------------------------|-----------------------------------------------------------------------------------|
| taxsimid  | Unique identifier                                          |                                                                                   |
| year      | Tax year                                                   |                                                                                   |
| state     | [State code (FIPS)](https://taxsim.nber.org/statesoi.html) | Two-digit code, e.g. 44 for Texas (Default is Texas if no state code is provided) |
| mstat     | Marital status                                             | Only supports: 1 (single), 2 (joint)                                              |
| page      | Primary taxpayer age                                       |                                                                                   |
| sage      | Spouse age                                                 |                                                                                   |
| depx      | Number of dependents                                       |                                                                                   |
| age1      | First dependent's age                                      |                                                                                   |
| age2      | Second dependent's age                                     |                                                                                   |
| ageN      | Nth dependent's age                                        | Taxsim only allows upto 8 child dependents                                        |
| pwages    | Primary taxpayer wages                                     |                                                                                   |
| swages    | Spouse wages                                               |                                                                                   |
| psemp     | Self-employment income of primary taxpayer                 |                                                                                   |
| ssemp     | Self-employment income of secondary taxpayer               |                                                                                   |
| dividends | Dividend Income                                            |                                                                                   |
| intrec    | Taxable Interest Received                                  |                                                                                   |
| stcg      | Short Term Capital Gains or losses                         |                                                                                   |
| ltcg      | Long Term Capital Gains or losses                          |                                                                                   |
| gssi      | Gross Social Security Benefits                             |                                                                                   |
| pensions  | Taxable Pensions and IRA distributions                     |                                                                                   |
| rentpaid  | Rent Paid                                                  |                                                                                   |


### Output Types

Depending on the idtl input value it can generate output types as following:

| idtl | Description                                    |
|------|------------------------------------------------|
| 0    | Standard output (Outputs 10 result columns)    |
| 2    | Full output  (Outputs 45 result columns)       |
| 5    | Full text output (human-readable explanations) |

### Household Types

| Supported household types               |
|-----------------------------------------|
| Single                                  |
| Joint                                   |
| Household with Dependent                |
| Household with Dependent single parent  |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License 
[MIT License](https://github.com/PolicyEngine/policyengine-taxsim?tab=License-1-ov-file#)

## Support

For issues and feature requests, please [open an issue](https://github.com/PolicyEngine/policyengine-taxsim/issues).