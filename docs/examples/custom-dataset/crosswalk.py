"""Turn a survey extract into TAXSIM input, compute taxes, and merge them back.

Run from this directory:  python crosswalk.py
survey_extract.csv is made up; swap in your own file and column names.
"""

import pandas as pd

from policyengine_taxsim.runners import StitchedRunner

survey = pd.read_csv("survey_extract.csv")

# 1. Blank amounts mean "none". TAXSIM input has no missing values, so make
#    them zeros.
amounts = [
    "wages_head", "wages_spouse", "self_emp_head", "interest", "dividends",
    "pension", "social_security", "unemployment", "rent_paid",
    "property_tax", "mortgage_interest", "charity", "childcare_cost",
]  # fmt: skip
survey[amounts] = survey[amounts].fillna(0)

# 2. Map each survey concept to a TAXSIM column. This survey codes married
#    as 1; everyone else files as unmarried (head of household with a child).
married = survey["marital_status"] == 1
taxsim = pd.DataFrame(
    {
        "taxsimid": survey["hh_id"],
        "year": survey["tax_year"],
        "statefip": survey["state_fips"],  # FIPS codes; SOI codes go in `state`
        "mstat": married.map({True: 2, False: 1}),
        "page": survey["age_head"],
        "sage": survey["age_spouse"].where(married, 0).fillna(0),
        "depx": survey["num_children"].fillna(0),
        "pwages": survey["wages_head"],
        "swages": survey["wages_spouse"].where(married, 0),
        "psemp": survey["self_emp_head"],
        "intrec": survey["interest"],
        "dividends": survey["dividends"],
        "pensions": survey["pension"],
        "gssi": survey["social_security"],
        "pui": survey["unemployment"],
        "rentpaid": survey["rent_paid"],
        "proptax": survey["property_tax"],
        # Mortgage interest and charity are both itemized deductions that
        # are not AMT preferences, so both go in `mortgage`.
        "mortgage": survey["mortgage_interest"] + survey["charity"],
        "childcare": survey["childcare_cost"],
        "idtl": 2,  # full output
    }
)

# 3. Dependent ages. The emulator reads an age of 0 as "not given" (and uses
#    10), so code infants as 1, as TAXSIM-35 instructs.
for slot in (1, 2, 3):
    age = survey[f"child_age_{slot}"]
    taxsim[f"age{slot}"] = age.mask(age == 0, 1).fillna(0)

# 4. Check before running: the emulator does not reject most bad values.
assert taxsim.notna().all().all(), "recode every missing value first"
assert taxsim["mstat"].isin([1, 2, 6]).all(), "mstat must be 1, 2 or 6"
assert taxsim["taxsimid"].is_unique, "taxsimid must identify each record"

# 5. Keep the TAXSIM input for the record, then compute. StitchedRunner is
#    what the policyengine-taxsim command uses: 2021 and later go to
#    PolicyEngine, earlier years to TAXSIM-35.
taxsim.to_csv("taxsim_input.csv", index=False)
results = StitchedRunner(taxsim).run()

# 6. Merge back on taxsimid. Amounts are computed in 32-bit floating point,
#    so round them to cents.
keep = ["taxsimid", "fiitax", "siitax", "fica", "v10"]
taxes = results[keep].astype(float).round(2)
merged = survey.merge(taxes, left_on="hh_id", right_on="taxsimid", how="left")
merged.drop(columns="taxsimid").to_csv("survey_with_taxes.csv", index=False)
print(merged[["hh_id", "tax_year", "fiitax", "siitax", "fica", "v10"]])
