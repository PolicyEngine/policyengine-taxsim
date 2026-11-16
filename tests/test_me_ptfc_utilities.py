"""Maine property tax fairness credit: TAXSIM's rentpaid does not include
heat or utilities (taxsim #1474, which replaces the #1126 convention), so the
emulator leaves utilities_included_in_rent at PolicyEngine's default (False)
and Schedule PTFC/STFC line 5b is "No" for every state, Maine included.
"""

import numpy as np
import pandas as pd

from policyengine_taxsim.core.input_mapper import form_household_situation
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)


def _record(state, rentpaid):
    return {
        "taxsimid": 1,
        "year": 2022,
        "state": state,
        "mstat": 1,
        "page": 49,
        "depx": 1,
        "pwages": 44452.57,
        "rentpaid": rentpaid,
    }


def test_maine_rent_does_not_set_flag():
    situation = form_household_situation(2022, "ME", _record(20, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


def test_maine_without_rent_does_not_set_flag():
    situation = form_household_situation(2022, "ME", _record(20, 0))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


def test_michigan_rent_does_not_set_flag():
    situation = form_household_situation(2022, "MI", _record(24, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


# The production PolicyEngineRunner (batch/CLI path) builds its own
# Microsimulation dataset, so check that path too: rent never includes
# utilities there either (taxsim #1474).
def _batch_utilities_flag(state, rentpaid):
    df = pd.DataFrame([_record(state, rentpaid)])
    runner = PolicyEngineRunner(df, logs=False)
    chunk_df = runner._ensure_required_columns(df.copy())
    dataset = TaxsimMicrosimDataset(chunk_df)
    dataset.generate()
    try:
        sim = runner._build_configured_sim(dataset, chunk_df)
        return bool(np.asarray(sim.calculate("utilities_included_in_rent", 2022))[0])
    finally:
        dataset.cleanup()


def test_batch_path_does_not_set_flag_for_maine_renter():
    assert _batch_utilities_flag(20, 17139.244) is False  # SOI code 20 = Maine


def test_batch_path_does_not_set_flag_for_maine_without_rent():
    assert _batch_utilities_flag(20, 0) is False


def test_batch_path_does_not_set_flag_for_michigan():
    assert _batch_utilities_flag(23, 17139.244) is False  # SOI code 23 = Michigan


def test_maine_2024_credit_matches_taxact_return():
    # taxsim #1474: TaxAct answers Schedule PTFC/STFC line 5b "No" (rent does
    # not include heat or utilities) and allows a $503 credit (whole dollars).
    df = pd.DataFrame(
        [
            {
                "taxsimid": 2,
                "year": 2024,
                "state": 20,
                "mstat": 1,
                "page": 68,
                "pwages": 55523.809,
                "intrec": 743.35437,
                "rentpaid": 18363.477,
                "idtl": 2,
            }
        ]
    )
    result = PolicyEngineRunner(df, logs=False).run(show_progress=False)
    assert 503 <= float(result["v37"].iloc[0]) < 504
