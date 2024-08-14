import pandas as pd

import numpy as np



# TO DO: add data validation for each row. Need same number of data points in each row

# class reads taxsim input and outputs a list of policy engine situations
class InputReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = self.read_csv()
        self.situations = self.get_situations()
        self.output_level = self.get_output_level()

    def read_csv(self):
        return pd.read_csv(self.file_path, index_col=False)

    def get_filing_status(self, mstat):
        filing_status_map = {
            1: "single",
            2: "married_jointly",
            6: "married_separately",
            8: "dependent_child",
            5: "head_of_household"
        }
        return filing_status_map.get(mstat, f"Unknown filing status: {mstat}")

    def get_state_code(self, state_number):
        state_mapping = {
            1: "AL", 2: "AK", 3: "AZ", 4: "AR", 5: "CA", 6: "CO", 7: "CT", 8: "DE", 9: "DC", 10: "FL",
            11: "GA", 12: "HI", 13: "ID", 14: "IL", 15: "IN", 16: "IA", 17: "KS", 18: "KY", 19: "LA",
            20: "ME", 21: "MD", 22: "MA", 23: "MI", 24: "MN", 25: "MS", 26: "MO", 27: "MT", 28: "NE",
            29: "NV", 30: "NH", 31: "NJ", 32: "NM", 33: "NY", 34: "NC", 35: "ND", 36: "OH", 37: "OK",
            38: "OR", 39: "PA", 40: "RI", 41: "SC", 42: "SD", 43: "TN", 44: "TX", 45: "UT", 46: "VT",
            47: "VA", 48: "WA", 49: "WV", 50: "WI", 51: "WY"
        }
        return state_mapping.get(state_number, "Invalid state number")
    

    # Default situation from policy engine
    def create_default_situation(self, year):
        return {
            "people": {
                "you": {
                    "age": { year: 40 },
                },
            },
            "families": {
                "your family": {
                    "members": ["you"],
                }
            },
            "marital_units": {
                "your marital unit": {
                    "members": ["you"],
                },
            },
            "tax_units": {
                "your tax unit": {
                    "members": ["you"],
                },
            },
            "spm_units": {
                "your household": {
                    "members": ["you"],
                }
            },
            "households": {
                "your household": {
                    "members": ["you"],
                }
            }
        }

    # iterate through the input file and add the input variable information to the situation
    def add_variables(self, situation, row, year):
        # list of working income variables
        income_variable_map = {
            "pwages": "employment_income",
            "swages": "employment_income",
            "psemp": "self_employment_income_last_year",
            "ssemp": "self_employment_income_last_year",
            "dividends": "qualified_dividend_income",
            "intrec": "taxable_interest_income",
            "stcg": "short_term_capital_gains",
            "ltcg": "long_term_capital_gains",
            "nonprop": "alimony_income",
            "otherprop": "partnership_s_corp_income",
            "pensions": "pension_income",
            "pui": "unemployment_compensation",
            "sui": "unemployment_compensation",
            "proptax": "real_estate_taxes",
            "scorp": "s_corp_self_employment_income",
            "pbusinc": "qualified_business_income",
            "sbusinc": "qualified_business_income"
        }

        primary_variables = ["pwages","psemp","dividends","intrec","stcg","ltcg","pui","proptax","pbusinc","nonprop","otherprop",
                             "scorp","pensions"]
        spouse_variables = ["swages","ssemp","sui","sbusinc"]

        primary_taxpayer = "you"
        spouse_taxpayer = "your partner"

        for taxsim_var, situation_var in income_variable_map.items():
            value = row.get(taxsim_var, None)
            if pd.notna(value):
                if taxsim_var in primary_variables:
                    if primary_taxpayer not in situation["people"]:
                        situation["people"][primary_taxpayer] = {}
                    situation["people"][primary_taxpayer].setdefault(situation_var, {})[year] = value
                elif taxsim_var in spouse_variables:
                    if spouse_taxpayer not in situation["people"]:
                        situation["people"][spouse_taxpayer] = {
                            "age": { year: 40 },  # Default age, should be updated from row if available
                        }
                    situation["people"][spouse_taxpayer].setdefault(situation_var, {})[year] = value
                else:
                    situation["people"][primary_taxpayer].setdefault(situation_var, {})[year] = value


    # add the spouse and their age/income to correct units in situation
    def add_spouse(self, situation, row, year):
        spouse_person_id = "your partner"
        situation["people"][spouse_person_id] = {
            "age": { year: int(row.get('sage', 40)) },
            "employment_income": { year: int(row.get('swages', 0)) },
            "is_tax_unit_spouse": { year: True },
        }
        # Update units with spouse
        units_to_update = {
            "families": "your family",
            "marital_units": "your marital unit",
            "tax_units": "your tax unit",
            "spm_units": "your household",
            "households": "your household"
        }
        for unit, unit_name in units_to_update.items():
            situation[unit][unit_name].setdefault("members", []).append(spouse_person_id)
    
    # add dependents and their ages to the correct units
    def add_dependents(self, situation, row, year, depx):
        ordinal = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
            5: "fifth"
        }
        # taxsim limits the number of dependents at 3.
        for i in range(1, min(depx, 3) + 1):
            dependent_id = ordinal.get(i)
            dependent_name = "your " + dependent_id + " dependent"
            dependent_age = int(row.get(f'age{i}', 10))
            situation["people"][dependent_name] = {
                "age": { year: dependent_age },
            }
            situation["families"]["your family"]["members"].append(dependent_name)
            situation["spm_units"]["your household"]["members"].append(dependent_name)
            situation["households"]["your household"]["members"].append(dependent_name)
            situation["tax_units"]["your tax unit"]["members"].append(dependent_name)

    # create the situation 
    def create_situation(self, row):
        year = str(convert_to_int(row['year']))
        state = self.get_state_code(row['state'])
        mstat = row['mstat']
        depx_value = row.get('depx')

        if pd.notna(depx_value):
            depx = int(depx_value) 
        else:
            depx = 0

        situation = self.create_default_situation(year)

        # Add primary taxpayer details
        main_person_id = "you"
        situation["people"][main_person_id]["age"] = { year: int(row.get('page', 40)) }
        situation["people"][main_person_id]["employment_income"] = { year: int(row.get('pwages', 0)) }

        # Add state to the household
        situation["households"]["your household"]["state_name"] = { year: state }

        if mstat == 2:
            self.add_spouse(situation, row, year)

        if depx > 0:
            self.add_dependents(situation, row, year, depx)

        # Add additional variables
        self.add_variables(situation, row, year)

        return situation


    # return the output level based on input idtl value
    def get_output_level(self):
        idtl_values = self.df['idtl'].unique()
        if 5 in idtl_values:
            return "text_descriptions"
        elif 2 in idtl_values:
            return "full"
        elif 0 in idtl_values:
            return "standard"
        else:
            raise ValueError("Unknown idtl value")
    
    def get_situations(self):
        situations = []
        for index, row in self.df.iterrows():
            situation = self.create_situation(row)
            situation = convert_to_int(situation)
            situations.append(situation)
        return situations
    
    # Convert int64 and floats to int in the situation 
def convert_to_int(obj):
    if isinstance(obj, np.int64):
        return int(obj)
    elif isinstance(obj, dict):
        return {key: convert_to_int(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_int(element) for element in obj]
    elif isinstance(obj, float):
        return(int(obj))
    else:
        return obj
    

        
