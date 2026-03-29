"""Convert a PolicyEngine H5 dataset to TAXSIM CSV format.

Usage:
    python scripts/convert_h5_to_taxsim.py [--dataset small_enhanced_cps_2024] [--year 2024] [--output dashboard/public/sample_ecps_2024.csv]

Requires: policyengine-us, huggingface_hub
"""

import argparse
import numpy as np
import pandas as pd

# FIPS state code -> TAXSIM SOI state code
FIPS_TO_SOI = {
    1: 1,
    2: 2,
    4: 3,
    5: 4,
    6: 5,
    8: 6,
    9: 7,
    10: 8,
    11: 9,
    12: 10,
    13: 11,
    15: 12,
    16: 13,
    17: 14,
    18: 15,
    19: 16,
    20: 17,
    21: 18,
    22: 19,
    23: 20,
    24: 21,
    25: 22,
    26: 23,
    27: 24,
    28: 25,
    29: 26,
    30: 27,
    31: 28,
    32: 29,
    33: 30,
    34: 31,
    35: 32,
    36: 33,
    37: 34,
    38: 35,
    39: 36,
    40: 37,
    41: 38,
    42: 39,
    44: 40,
    45: 41,
    46: 42,
    47: 43,
    48: 44,
    49: 45,
    50: 46,
    51: 47,
    53: 48,
    54: 49,
    55: 50,
    56: 51,
}

SMALL_ECPS_REVISION = "c24d1444f381e10f81103ea853ab57a46ed3f10e"


def load_sim(dataset_name: str, year: int, revision: str):
    """Load a PolicyEngine Microsimulation for the given dataset."""
    from policyengine_us import Microsimulation

    if dataset_name == "small_enhanced_cps_2024":
        # Download the small file and use it directly
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id="policyengine/policyengine-us-data",
            repo_type="model",
            filename="small_enhanced_cps_2024.h5",
            revision=revision,
        )
        sim = Microsimulation(dataset=path)
    else:
        sim = Microsimulation(dataset=dataset_name)

    return sim


def extract_taxsim_csv(sim, year: int) -> pd.DataFrame:
    """Extract TAXSIM-format rows from a Microsimulation, one row per tax unit."""

    period = str(year)

    # Get entity arrays
    person_tax_unit_id = sim.calculate("person_tax_unit_id", period).values
    tax_unit_id = sim.calculate("tax_unit_id", period).values

    # Person-level variables
    age = sim.calculate("age", period).values
    is_tax_unit_head = sim.calculate("is_tax_unit_head", period).values
    is_tax_unit_spouse = sim.calculate("is_tax_unit_spouse", period).values
    is_tax_unit_dependent = sim.calculate("is_tax_unit_dependent", period).values

    # Person-level income
    employment_income = sim.calculate("employment_income", period).values
    self_employment_income = sim.calculate("self_employment_income", period).values
    unemployment_comp = sim.calculate("unemployment_compensation", period).values

    # Tax-unit or person-level income (assigned to primary, split if needed)
    taxable_interest = sim.calculate("taxable_interest_income", period).values
    qualified_dividends = sim.calculate("qualified_dividend_income", period).values
    short_term_cg = sim.calculate("short_term_capital_gains", period).values
    long_term_cg = sim.calculate("long_term_capital_gains", period).values
    pensions = sim.calculate("taxable_private_pension_income", period).values
    ss_retirement = sim.calculate("social_security_retirement", period).values
    ss_disability = sim.calculate("social_security_disability", period).values
    ss_survivors = sim.calculate("social_security_survivors", period).values
    ss_dependents = sim.calculate("social_security_dependents", period).values
    rental_income = sim.calculate("rental_income", period).values

    # Try to get S-corp income (only in ECPS)
    try:
        scorp_income = sim.calculate("partnership_s_corp_income", period).values
    except Exception:
        scorp_income = np.zeros_like(employment_income)

    # Household-level
    state_fips = sim.calculate("state_fips", period).values
    household_weight = sim.calculate("household_weight", period).values

    # Person -> household mapping
    person_household_id = sim.calculate("person_household_id", period).values
    household_id = sim.calculate("household_id", period).values

    # Expense variables (person or household level)
    try:
        real_estate_taxes = sim.calculate("real_estate_taxes", period).values
    except Exception:
        real_estate_taxes = np.zeros(len(household_id))

    try:
        mortgage_interest = sim.calculate("deductible_mortgage_interest", period).values
    except Exception:
        mortgage_interest = np.zeros(len(household_id))

    try:
        rent = sim.calculate("rent", period).values
    except Exception:
        rent = np.zeros(len(household_id))

    # Build household-level lookups
    hh_state = dict(zip(household_id, state_fips))
    hh_weight = dict(zip(household_id, household_weight))
    hh_proptax = dict(zip(household_id, real_estate_taxes))
    hh_mortgage = dict(zip(household_id, mortgage_interest))
    hh_rent = dict(zip(household_id, rent))

    # Build person lookup by tax unit
    rows = []
    for tu_id in tax_unit_id:
        person_mask = person_tax_unit_id == tu_id
        person_indices = np.where(person_mask)[0]

        if len(person_indices) == 0:
            continue

        # Find head, spouse, dependents
        head_idx = None
        spouse_idx = None
        dep_indices = []

        for idx in person_indices:
            if is_tax_unit_head[idx]:
                head_idx = idx
            elif is_tax_unit_spouse[idx]:
                spouse_idx = idx
            elif is_tax_unit_dependent[idx]:
                dep_indices.append(idx)

        if head_idx is None:
            continue  # Skip malformed tax units

        # Get household info for this person
        hh_id = person_household_id[head_idx]

        # Marital status: 1=single, 2=married filing jointly
        mstat = 2 if spouse_idx is not None else 1

        # Gross social security = sum of all SS types
        def person_gssi(idx):
            return (
                ss_retirement[idx]
                + ss_disability[idx]
                + ss_survivors[idx]
                + ss_dependents[idx]
            )

        row = {
            "taxsimid": int(tu_id),
            "year": year,
            "state": FIPS_TO_SOI.get(int(hh_state.get(hh_id, 0)), 0),
            "mstat": mstat,
            "page": max(int(age[head_idx]), 0),
            "sage": max(int(age[spouse_idx]), 0) if spouse_idx is not None else 0,
            "depx": len(dep_indices),
            "pwages": round(float(employment_income[head_idx]), 2),
            "swages": round(float(employment_income[spouse_idx]), 2)
            if spouse_idx is not None
            else 0,
            "psemp": round(float(self_employment_income[head_idx]), 2),
            "ssemp": round(float(self_employment_income[spouse_idx]), 2)
            if spouse_idx is not None
            else 0,
            "dividends": round(
                float(sum(qualified_dividends[i] for i in person_indices)),
                2,
            ),
            "intrec": round(float(sum(taxable_interest[i] for i in person_indices)), 2),
            "stcg": round(float(sum(short_term_cg[i] for i in person_indices)), 2),
            "ltcg": round(float(sum(long_term_cg[i] for i in person_indices)), 2),
            "otherprop": round(float(sum(rental_income[i] for i in person_indices)), 2),
            "pensions": round(float(sum(pensions[i] for i in person_indices)), 2),
            "gssi": round(float(sum(person_gssi(i) for i in person_indices)), 2),
            "pui": round(float(unemployment_comp[head_idx]), 2),
            "sui": round(float(unemployment_comp[spouse_idx]), 2)
            if spouse_idx is not None
            else 0,
            "scorp": round(float(sum(scorp_income[i] for i in person_indices)), 2),
            "proptax": round(float(hh_proptax.get(hh_id, 0)), 2),
            "mortgage": round(float(hh_mortgage.get(hh_id, 0)), 2),
            "rentpaid": round(float(hh_rent.get(hh_id, 0)), 2),
        }

        # Add dependent ages
        for i, dep_idx in enumerate(dep_indices[:11]):  # TAXSIM max 11 dependents
            row[f"age{i + 1}"] = max(int(age[dep_idx]), 0)

        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort by taxsimid
    df = df.sort_values("taxsimid").reset_index(drop=True)

    # Fill NaN with 0 and convert numeric columns
    df = df.fillna(0)

    return df


def main():
    parser = argparse.ArgumentParser(description="Convert H5 dataset to TAXSIM CSV")
    parser.add_argument(
        "--dataset",
        default="small_enhanced_cps_2024",
        help="Dataset name (default: small_enhanced_cps_2024)",
    )
    parser.add_argument(
        "--year", type=int, default=2024, help="Tax year (default: 2024)"
    )
    parser.add_argument(
        "--output",
        default="dashboard/public/sample_ecps_2024.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--revision",
        default=SMALL_ECPS_REVISION,
        help=(
            "Hugging Face revision for small_enhanced_cps_2024 "
            f"(default: {SMALL_ECPS_REVISION})"
        ),
    )
    args = parser.parse_args()

    print(f"Loading dataset: {args.dataset}")
    sim = load_sim(args.dataset, args.year, args.revision)

    print(f"Extracting TAXSIM CSV for year {args.year}...")
    df = extract_taxsim_csv(sim, args.year)

    print(f"Writing {len(df)} tax units to {args.output}")
    df.to_csv(args.output, index=False)

    # Print summary
    print(f"\nSummary:")
    print(f"  Tax units: {len(df)}")
    print(f"  Single filers: {(df['mstat'] == 1).sum()}")
    print(f"  Joint filers: {(df['mstat'] == 2).sum()}")
    print(f"  With dependents: {(df['depx'] > 0).sum()}")
    print(f"  States represented: {df['state'].nunique()}")
    print(f"  Mean wages: ${df['pwages'].mean():,.0f}")


if __name__ == "__main__":
    main()
