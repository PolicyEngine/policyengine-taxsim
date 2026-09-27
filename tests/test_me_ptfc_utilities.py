"""Maine property tax fairness credit: rentpaid is treated as gross rent that
includes heat/utilities, so the emulator flags utilities_included_in_rent for
Maine records with rent. This is scoped to Maine because the same variable also
feeds Michigan's home heating credit. See taxsim issue #1126.
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


def test_maine_rent_sets_utilities_included_in_rent():
    situation = form_household_situation(2022, "ME", _record(20, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert tax_unit["utilities_included_in_rent"] == {"2022": True}


def test_maine_without_rent_does_not_set_flag():
    situation = form_household_situation(2022, "ME", _record(20, 0))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


def test_michigan_rent_does_not_set_flag():
    # utilities_included_in_rent also feeds Michigan's home heating credit, so
    # the Maine flag must not leak to other states.
    situation = form_household_situation(2022, "MI", _record(24, 17139.244))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert "utilities_included_in_rent" not in tax_unit


# The production PolicyEngineRunner (batch/CLI path) builds its own
# Microsimulation dataset and never calls add_additional_units, so the Maine
# flag has to be set there too. These regressions confirm the flag reaches the
# batch path for Maine renters and does not leak to Michigan (taxsim #1128).
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


def test_batch_path_sets_utilities_flag_for_maine_renter():
    assert _batch_utilities_flag(20, 17139.244) is True  # SOI code 20 = Maine


def test_batch_path_does_not_set_flag_for_maine_without_rent():
    assert _batch_utilities_flag(20, 0) is False


def test_batch_path_does_not_set_flag_for_michigan():
    assert _batch_utilities_flag(23, 17139.244) is False  # SOI code 23 = Michigan
