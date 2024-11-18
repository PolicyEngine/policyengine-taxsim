# Policyengine-taxsim
TAXSIM emulator using the PolicyEngine US federal and state tax calculator
## How to install the emulator ##
    git clone https://github.com/PolicyEngine/policyengine-taxsim
    pip install -U policyengine-us

## How to use the emulator ##
The emulator takes a .csv file in the form of a csv. This is the same form of input that Taxsim-35 takes.

**Open your terminal in the parent directory**

1. To install this package

`pip install -e .`

2. to execute the simulation, run 

`python policyengine_taxsim/cli.py resources/taxsim35/taxsim_input.csv `

Output will be generated as `output.csv` in the same directory


**For directly installing from pip**

You can install through to execute directly

`pip install git+https://github.com/PolicyEngine/policyengine-taxsim.git`

### Example ##
input file:

<img width="641" alt="Screenshot 2024-07-10 at 6 29 17 PM" src="https://github.com/sgerson2/policyengine-taxsim/assets/113052102/db0ee3e4-9a54-42e7-a4fc-e46f07ab83f8">


## List of working input variables ##

### Demographics: ###
1. taxsimid 
2. year
3. state
4. mstat (only 1 (single) and 2 (joint) filing options work)
5. page (age of primary taxpayer)
6. sage (age of spouse)
7. depx (number of dependents)
8. age1 (age of first dependent)
9. age2 (age of second dependent)
10. age3 (age of third dependent)

### Income: ###
1. pwages (wage of primary taxpayer)
2. swages (wage of spouse)
3. psemp (self-employment income of primary taxpayer)
4. ssemp (self-employment income of spouse)
5. dividends (dividend income)
6. intrec (taxable interest received)
7. stcg (short-term capital gains)
8. ltcg (long-term capital gains)
9. pui (primary taxpayer unemployment compensation received)
10. sui (spouse unemployment compensation received)
11. proptax (real estate taxes paid)
