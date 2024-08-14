# policyengine-taxsim
TAXSIM emulator using the PolicyEngine US federal and state tax calculator

## How to use the emulator ##
The emulator takes a .raw file in the form of a csv. This is the same form of input that Taxsim-35 takes.

In terminal, run python3 /Path/to/taxsim_emulator.py /Path/to/your/input_file.raw 

### Example ##
input:

<img width="641" alt="Screenshot 2024-07-10 at 6 29 17 PM" src="https://github.com/sgerson2/policyengine-taxsim/assets/113052102/db0ee3e4-9a54-42e7-a4fc-e46f07ab83f8">

If the emulator and input file are in the current working directory, run:

python3 taxsim_emulator.py taxsim_input.raw

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
11. idtl (determines the level of output. 0 = standard, 2 = full, 5 = full with text descriptions)

### Income: ###
1. pwages (wage of primary taxpayer)
2. swages (wage of spouse)
3. psemp (self-employment income of primary taxpayer)
4. ssemp (self-employment income of spouse)
5. dividends (dividend income)
6. intrec (taxable interest received)
7. stcg (short-term capital gains)
8. ltcg (long-term capital gains)
9. otherprop (other property incomes)
10. nonprop (other non-property incomes)
11. pensions (taxable pensions and IRA distributions)
12. pui (primary taxpayer unemployment compensation received)
13. sui (spouse unemployment compensation received)
14. proptax (real estate taxes paid)
