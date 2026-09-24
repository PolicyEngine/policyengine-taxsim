"""Convert PolicyEngine-US microdata to TAXSIM input rows, one per tax unit.

The default input is the Populace US build that policyengine.py certifies
(``POPULACE_BUILD``). The converter downloads it by immutable Hugging Face
commit, checks its sha256, refuses to read it with a policyengine-us or
policyengine-core version other than the certified one, and writes
``populace_households.csv`` plus ``populace_households.json`` (provenance).
The dashboard refresh then scores those rows under every tax year's law.

Usage (from the repo root, in the certified environment):
    uv venv --python 3.11 .venv-populace
    VIRTUAL_ENV=.venv-populace uv pip install -r scripts/populace-convert-requirements.txt
    .venv-populace/bin/python scripts/convert_h5_to_taxsim.py

    # Any other PolicyEngine-US H5 (no certification check):
    python scripts/convert_h5_to_taxsim.py --h5 path/to/data.h5 --output out.csv

Field definitions follow the NBER taxsimtest documentation
(https://taxsim.nber.org/taxsimtest/), which the bundled binary implements:

- Incomes belong to the return's filers: the primary taxpayer and spouse.
  Dependents' own income is left out; they would file their own returns,
  which the benchmark does not represent.
- proptax: real estate taxes.
- mortgage: deductions that are not AMT preferences, as net deductible
  amounts (taxsimtest applies no floor or limit to this field, and a
  negative value is a fatal record error): deductible home mortgage
  interest, medical expenses above the 7.5%-of-AGI floor, charitable
  contributions after AGI limits, and casualty losses above their floor.
- otheritem: AMT-preference itemized deductions. For 2021-2025 that is
  interest other than on the taxpayers' residence (investment interest).
  Miscellaneous deductions are disallowed after 2017 (IRC 67(h)), Form 6251
  has no medical adjustment after 2017, and no other state or local tax
  besides income and real estate taxes is a PolicyEngine input. Local income
  tax is a PolicyEngine output, not an input, so it is not included.
- nonprop stays zero: the emulator does not map it to any PolicyEngine
  input, so a value would be dropped on the PolicyEngine side only.
- Dependent ages are listed youngest first, and infants are coded 1, as the
  TAXSIM documentation instructs ("Code infants as 1").
- Tax-unit roles and filing status come from the build's explicit
  ``tax_unit_role_input`` and ``filing_status_input`` columns, pinned into
  PolicyEngine before anything is calculated. policyengine-us has no variable
  that reads them and would otherwise take the two oldest adults as head and
  spouse, turning adult dependents into spouses.
- Joint returns are mstat 2 and every other return mstat 1; TAXSIM infers
  head of household from dependents. Tax units with no filer are dropped.

Deductions are computed by PolicyEngine for the build's data year. The same
records are reused for every tax year, like the Enhanced CPS benchmark.
"""

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# The US data release policyengine.py certifies, from its bundle manifest.
POPULACE_BUILD = {
    "buildId": "populace-us-2024-spm-20260915",
    "hfRepo": "policyengine/populace-us",
    "hfRepoType": "dataset",
    "hfRevision": "populace-us-2024-spm-20260915",
    # The commit the tag resolved to on 2026-09-23; downloads pin to it.
    "hfCommit": "8ab57ffc2ca41d8af631ff62ebbce95e966299f3",
    "h5File": "populace_us_2024.h5",
    "h5Sha256": "6496cc4393d4d3c6574f76eca231de5898c803b9067645591fd5c4d3e65aee84",
    "dataYear": 2024,
    "certifiedModel": {"policyengine-us": "2.2.1", "policyengine-core": "3.32.5"},
    "certifiedBy": (
        "policyengine.py 6.1.1 (bundle manifest at PolicyEngine/policyengine.py "
        "4dc5959, src/policyengine/data/bundle/manifest.json)"
    ),
}

# FIPS state code -> TAXSIM SOI state code. The exact inverse of
# policyengine_taxsim.core.utils.SOI_TO_FIPS_MAP (tests/test_state_codes.py).
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

MAX_DEPENDENT_AGES = 11
# Column order of the committed TAXSIM input files (refresh_dashboard.py
# INPUT_COLUMNS).
TAXSIM_COLUMNS = (
    "taxsimid year state mstat page sage depx pwages psemp swages ssemp "
    "dividends intrec stcg ltcg otherprop nonprop pensions gssi pui sui "
    "transfers rentpaid proptax otheritem childcare mortgage scorp idtl "
    + " ".join(f"age{i}" for i in range(1, MAX_DEPENDENT_AGES + 1))
).split()
# The 16 TAXSIM income fields. Their sum is the "total income" used for the
# top-income coverage counts.
INCOME_COLUMNS = (
    "pwages swages psemp ssemp dividends intrec stcg ltcg otherprop nonprop "
    "pensions gssi pui sui transfers scorp"
).split()
ITEMIZED_COLUMNS = ("proptax", "mortgage", "otheritem")

SMALL_ECPS_REVISION = "c24d1444f381e10f81103ea853ab57a46ed3f10e"


def fips_to_soi(fips) -> int:
    """Return the TAXSIM SOI state code for a state FIPS code.

    Unknown codes raise rather than default to 0, because TAXSIM reads state 0
    as "no state tax". The converter that built cps_households.csv had no
    entry for FIPS 1 and fell back to 0, so every Alabama household was
    scored without state income tax.
    """
    try:
        return FIPS_TO_SOI[int(fips)]
    except KeyError:
        raise ValueError(f"No TAXSIM state code for FIPS {fips!r}") from None


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch_certified_h5(build=POPULACE_BUILD) -> Path:
    """Download the certified H5 at its pinned commit and verify its sha256."""
    from huggingface_hub import hf_hub_download

    path = Path(
        hf_hub_download(
            repo_id=build["hfRepo"],
            repo_type=build["hfRepoType"],
            filename=build["h5File"],
            revision=build["hfCommit"],
        )
    )
    actual = sha256_file(path)
    if actual != build["h5Sha256"]:
        raise ValueError(
            f"{build['h5File']} sha256 is {actual}, expected {build['h5Sha256']}"
        )
    return path


def installed_versions(packages):
    return {name: importlib.metadata.version(name) for name in packages}


def require_certified_model(build=POPULACE_BUILD):
    """Refuse to read the build with a model version it was not certified for."""
    installed = installed_versions(build["certifiedModel"])
    if installed != build["certifiedModel"]:
        raise RuntimeError(
            f"{build['buildId']} is certified for {build['certifiedModel']}, but "
            f"{installed} is installed. Install "
            "scripts/populace-convert-requirements.txt (see module docstring)."
        )
    return installed


def load_sim(dataset_name: str, year: int, revision: str):
    """Load a Microsimulation from a local H5 path or a legacy eCPS name."""
    from policyengine_us import Microsimulation

    if dataset_name in ("small_enhanced_cps_2024", "enhanced_cps_2024"):
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id="policyengine/policyengine-us-data",
            repo_type="model",
            filename=f"{dataset_name}.h5",
            revision=revision if dataset_name == "small_enhanced_cps_2024" else None,
        )
        return Microsimulation(dataset=path)
    return Microsimulation(dataset=str(dataset_name))


ROLE_VARIABLES = {
    "HEAD": "is_tax_unit_head",
    "SPOUSE": "is_tax_unit_spouse",
    "DEPENDENT": "is_tax_unit_dependent",
}


def _decode(values):
    return np.array([v.decode() if isinstance(v, bytes) else str(v) for v in values])


def source_roles(h5_path):
    """The build's explicit tax-unit roles and filing statuses, or None.

    Populace stores each person's role (``tax_unit_role_input``: HEAD, SPOUSE
    or DEPENDENT) and each unit's ``filing_status_input``. policyengine-us has
    no variable that reads them: it infers the head as the oldest adult and
    the spouse as the next-oldest, which turns adult dependents into spouses.
    """
    with pd.HDFStore(h5_path, mode="r") as store:
        if not {"/person", "/tax_unit"} <= set(store.keys()):
            return None  # variable-centric H5 (e.g. the legacy eCPS files)
        people = store["person"]
        units = store["tax_unit"]
    if "tax_unit_role_input" not in people or "filing_status_input" not in units:
        return None
    return {
        "person_id": people["person_id"].to_numpy(),
        "role": _decode(people["tax_unit_role_input"]),
        "tax_unit_id": units["tax_unit_id"].to_numpy(),
        "filing_status": _decode(units["filing_status_input"]),
    }


def pin_source_roles(sim, year, roles):
    """Set PolicyEngine's role and filing-status variables to the source's.

    Must run before anything that depends on them is calculated.
    """
    period = str(year)
    person_id = _values(sim, "person_id", period)
    role = pd.Series(roles["role"], index=roles["person_id"]).reindex(person_id)
    tax_unit_id = _values(sim, "tax_unit_id", period)
    status = pd.Series(roles["filing_status"], index=roles["tax_unit_id"])
    status = status.reindex(tax_unit_id)
    if role.isna().any() or status.isna().any():
        raise ValueError("Source roles do not cover every person and tax unit")
    unknown = set(role) - set(ROLE_VARIABLES)
    if unknown:
        raise ValueError(f"Unknown tax_unit_role_input values {sorted(unknown)}")
    for name, variable in ROLE_VARIABLES.items():
        sim.set_input(variable, period, (role == name).to_numpy())
    sim.set_input("filing_status", period, status.to_numpy())


def _values(sim, variable, period):
    return np.asarray(sim.calculate(variable, period).values)


def extract_taxsim_csv(sim, year: int) -> pd.DataFrame:
    """TAXSIM input rows from a Microsimulation, one per tax unit, sorted by id.

    ``sim`` needs only ``calculate(variable, period).values``. Person-level
    arrays are aggregated to tax units; tax-unit-level arrays are in
    ``tax_unit_id`` order.
    """
    period = str(year)

    def calc(variable):
        return _values(sim, variable, period)

    tax_unit_id = calc("tax_unit_id").astype(np.int64)
    n = len(tax_unit_id)
    unit = pd.Index(tax_unit_id).get_indexer(calc("person_tax_unit_id"))
    if (unit < 0).any():
        raise ValueError("Some people belong to no tax unit")
    head = calc("is_tax_unit_head").astype(bool)
    spouse = calc("is_tax_unit_spouse").astype(bool) & ~head
    dependent = calc("is_tax_unit_dependent").astype(bool) & ~head & ~spouse
    heads = np.bincount(unit[head], minlength=n)
    if (heads > 1).any():
        raise ValueError(f"{int((heads > 1).sum())} tax units have several heads")
    # A unit of dependents alone (no head or spouse) has no filer, so it is
    # not a return. With the source roles pinned, Populace has none.
    no_filer = heads == 0
    non_dependents = np.bincount(unit[~dependent], minlength=n)
    if (no_filer & (non_dependents > 0)).any():
        raise ValueError("A tax unit without a head has non-dependent members")
    if (np.bincount(unit[spouse], minlength=n) > 1).any():
        raise ValueError("A tax unit has more than one spouse")
    has_spouse = np.bincount(unit[spouse], minlength=n) == 1
    filer = head | spouse

    def of(role, values):
        out = np.zeros(n)
        out[unit[role]] = values[role]
        return out

    def filers(*variables):
        values = sum(calc(v) for v in variables)
        return np.bincount(unit[filer], weights=values[filer], minlength=n)

    def members(*variables):
        return np.bincount(unit, weights=sum(calc(v) for v in variables), minlength=n)

    def unit_level(*variables):
        return sum(calc(v) for v in variables).astype(float)

    # State of the head's household.
    household = pd.Index(calc("household_id")).get_indexer(calc("person_household_id"))
    if (household < 0).any():
        raise ValueError("Some people belong to no household")
    head_fips = of(head, calc("state_fips")[household]).astype(int)
    state = np.array(
        [fips_to_soi(f) if filer else 0 for f, filer in zip(head_fips, ~no_filer)]
    )

    age = np.floor(np.maximum(calc("age"), 0))
    mortgage = unit_level(
        "medical_expense_deduction",
        "charitable_deduction",
        "casualty_loss_deduction",
    ) + members("deductible_mortgage_interest")

    data = {
        "taxsimid": tax_unit_id,
        "year": np.full(n, year),
        "state": state,
        "mstat": np.where(has_spouse, 2, 1),
        "page": of(head, age),
        "sage": of(spouse, age),
        "depx": np.bincount(unit[dependent], minlength=n),
        "pwages": of(head, calc("employment_income")),
        "psemp": of(head, calc("self_employment_income")),
        "swages": of(spouse, calc("employment_income")),
        "ssemp": of(spouse, calc("self_employment_income")),
        "dividends": filers("qualified_dividend_income"),
        # "After 2003 unqualified dividends can go here."
        "intrec": filers("taxable_interest_income", "non_qualified_dividend_income"),
        "stcg": filers("short_term_capital_gains"),
        "ltcg": filers("long_term_capital_gains"),
        "otherprop": filers("rental_income"),
        "nonprop": np.zeros(n),
        # "Taxable Pensions and IRA distributions"
        "pensions": filers(
            "taxable_pension_income", "taxable_retirement_distributions"
        ),
        "gssi": filers("social_security"),
        "pui": of(head, calc("unemployment_compensation")),
        "sui": of(spouse, calc("unemployment_compensation")),
        # Non-taxable transfers affecting state property tax rebates.
        "transfers": members(
            "veterans_benefits", "workers_compensation", "child_support_received"
        ),
        "rentpaid": members("rent"),
        "proptax": members("real_estate_taxes"),
        "otheritem": members("non_mortgage_interest"),
        "childcare": unit_level("tax_unit_childcare_expenses"),
        "mortgage": mortgage,
        "scorp": filers("partnership_s_corp_income"),
        "idtl": np.full(n, 2),
    }
    df = pd.DataFrame(data)
    df.attrs["droppedNoFiler"] = int(no_filer.sum())
    # TAXSIM has no surviving-spouse status, and the emulator's Microsimulation
    # path treats mstat 6 as a two-person unit, so every unit without a spouse
    # is coded mstat 1 (single or head of household, which TAXSIM infers from
    # dependents), as in the Enhanced CPS inputs. Record the filing statuses
    # this collapses.
    status = pd.Series(calc("filing_status").astype(str))[~no_filer]
    df.attrs["filingStatus"] = status.value_counts().sort_index().to_dict()
    if (df["mortgage"] < -0.005).any():
        raise ValueError("Negative mortgage deductions; taxsimtest rejects them")
    df["mortgage"] = df["mortgage"].clip(lower=0)

    # Dependent ages, youngest first; infants coded 1 per the TAXSIM docs.
    dep = pd.DataFrame(
        {"unit": unit[dependent], "age": np.maximum(age[dependent], 1).astype(int)}
    ).sort_values(["unit", "age"], kind="stable")
    dep["slot"] = dep.groupby("unit").cumcount() + 1
    dep = dep[dep["slot"] <= MAX_DEPENDENT_AGES]
    ages = dep.pivot(index="unit", columns="slot", values="age")
    for slot in range(1, MAX_DEPENDENT_AGES + 1):
        column = np.full(n, np.nan)
        if slot in ages.columns:
            column[ages.index.to_numpy()] = ages[slot].to_numpy()
        df[f"age{slot}"] = column

    money = [c for c in df.columns if c in INCOME_COLUMNS or c in ITEMIZED_COLUMNS]
    money += ["rentpaid", "childcare"]
    numeric = df[money].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Non-finite TAXSIM input values")
    df[money] = df[money].round(2)
    for column in ("page", "sage", "depx", "mstat", "state", "idtl"):
        df[column] = df[column].astype(int)
    attrs = dict(df.attrs)
    df = (
        df.loc[~no_filer, TAXSIM_COLUMNS].sort_values("taxsimid").reset_index(drop=True)
    )
    df.attrs.update(attrs)
    return df


def coverage(df: pd.DataFrame) -> dict:
    """Population coverage counts reported alongside each TAXSIM input file."""
    total_income = df[INCOME_COLUMNS].fillna(0).sum(axis=1)
    return {
        "records": int(len(df)),
        "states": int(df["state"].nunique()),
        "joint": int((df["mstat"] == 2).sum()),
        "withDependents": int((df["depx"] > 0).sum()),
        "totalIncomeAtLeast1M": int((total_income >= 1e6).sum()),
        "totalIncomeAtLeast10M": int((total_income >= 1e7).sum()),
        "maxTotalIncome": round(float(total_income.max()), 2),
        "longTermGainsNonzero": int((df["ltcg"] != 0).sum()),
        "scorpNonzero": int((df["scorp"] != 0).sum()),
        "nonzero": {
            column: int((df[column].fillna(0) != 0).sum())
            for column in TAXSIM_COLUMNS
            if column not in ("taxsimid", "year", "state", "mstat", "idtl", "page")
            and not column.startswith("age")
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--h5",
        help="Local PolicyEngine-US H5 (default: download the certified Populace build)",
    )
    parser.add_argument(
        "--dataset",
        help="Legacy eCPS dataset name (small_enhanced_cps_2024, enhanced_cps_2024)",
    )
    parser.add_argument("--revision", default=SMALL_ECPS_REVISION)
    parser.add_argument("--year", type=int, help="Data year (default: the build's)")
    parser.add_argument("--output", type=Path, default=ROOT / "populace_households.csv")
    parser.add_argument(
        "--provenance",
        type=Path,
        help="Provenance JSON (default: the output path with a .json suffix)",
    )
    args = parser.parse_args()
    provenance_path = args.provenance or args.output.with_suffix(".json")

    certified = not args.h5 and not args.dataset
    if certified:
        build = POPULACE_BUILD
        models = require_certified_model(build)
        year = args.year or build["dataYear"]
        print(f"Fetching {build['buildId']} ({build['hfRepo']}@{build['hfCommit']})")
        h5 = fetch_certified_h5(build)
        sim = load_sim(h5, year, args.revision)
    else:
        year = args.year or 2024
        models = installed_versions(["policyengine-us", "policyengine-core"])
        h5 = args.h5
        sim = load_sim(args.h5 or args.dataset, year, args.revision)
    roles = source_roles(h5) if h5 else None
    if roles is not None:
        pin_source_roles(sim, year, roles)

    print(f"Extracting TAXSIM inputs for {year}...")
    df = extract_taxsim_csv(sim, year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    stats = coverage(df)
    provenance = {
        "records": stats["records"],
        "output": args.output.name,
        "outputSha256": sha256_file(args.output),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "conversionModel": models,
        "converterSha256": sha256_file(__file__),
        "rolesFrom": (
            "tax_unit_role_input and filing_status_input in the H5"
            if roles is not None
            else "policyengine-us formulas"
        ),
        "droppedNoFiler": df.attrs["droppedNoFiler"],
        "filingStatus": df.attrs["filingStatus"],
        "coverage": stats,
    }
    if certified:
        provenance = {
            **{k: v for k, v in build.items() if k != "certifiedModel"},
            **provenance,
        }
    else:
        provenance["input"] = str(args.h5 or args.dataset)
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Wrote {len(df):,} tax units to {args.output} and {provenance_path}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
