"""TAXSIM has no health coverage input, so the emulator turns off PE-US's ACA
take-up for every record. Otherwise PE-US assigns a premium tax credit to
every eligible tax unit, and Oregon's federal tax liability subtraction nets
it out (PE-US #10093)."""

import numpy as np
import pandas as pd

from policyengine_us import Simulation

from policyengine_taxsim.core.input_mapper import form_household_situation
from policyengine_taxsim.runners.policyengine_runner import (
    PolicyEngineRunner,
    TaxsimMicrosimDataset,
)

# Joint Oregon couple aged 51 and 52 with $147,714 of wages: PE-US finds
# them eligible for a 2025 premium tax credit when take-up is on.
RECORD = {
    "taxsimid": 1,
    "year": 2025,
    "state": 38,
    "mstat": 2,
    "page": 51,
    "sage": 52,
    "depx": 0,
    "pwages": 86952.38,
    "swages": 60761.90,
    "intrec": 38.63,
    "idtl": 2,
}


def test_single_household_path_turns_off_aca_takeup():
    situation = form_household_situation(2025, "OR", dict(RECORD))
    tax_unit = situation["tax_units"]["your tax unit"]
    assert tax_unit["takes_up_aca_if_eligible"] == {"2025": False}
    sim = Simulation(situation=situation)
    assert sim.calculate("assigned_aca_ptc", 2025)[0] == 0


def test_batch_path_turns_off_aca_takeup():
    df = pd.DataFrame([RECORD])
    runner = PolicyEngineRunner(df, logs=False)
    chunk_df = runner._ensure_required_columns(df.copy())
    dataset = TaxsimMicrosimDataset(chunk_df)
    dataset.generate()
    try:
        sim = runner._build_configured_sim(dataset, chunk_df)
        assert not np.asarray(sim.calculate("takes_up_aca_if_eligible", 2025)).any()
        assert np.asarray(sim.calculate("assigned_aca_ptc", 2025))[0] == 0
    finally:
        dataset.cleanup()
