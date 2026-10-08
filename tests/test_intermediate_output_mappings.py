"""Intermediate outputs that follow TAXSIM-35's definitions.

TAXSIM-35 lists "v19 = Tax on Taxable Income (no special capital gains
rates)", the ordinary schedule on all of taxable income, "v29 = FICA", the combined employee + employer amount it also
reports in the `fica` column (the executable gives v29 == fica for every
record), and "v36 = State Taxable Income", which for Massachusetts is the sum
of the Part A, Part B and Part C taxable incomes. Expected values are the
TAXSIM-35 executable's output for the same records.
"""

import pandas as pd
import pytest
from policyengine_us.system import system

from policyengine_taxsim.runners import PolicyEngineRunner


def _run(records):
    output = PolicyEngineRunner(pd.DataFrame(records)).run(show_progress=False)
    return output.set_index(output["taxsimid"].astype(int))


def test_v29_is_combined_fica():
    output = _run(
        {
            "taxsimid": [1],
            "year": [2025],
            "state": [0],
            "mstat": [1],
            "page": [40],
            "pwages": [10_000],
            "idtl": [2],
        }
    )
    # 15.3% of 10,000 (TAXSIM-35: fica and v29 both 1,530).
    assert output.loc[1, "v29"] == pytest.approx(1_530, abs=0.01)
    assert output.loc[1, "v29"] == pytest.approx(output.loc[1, "fica"], abs=0.01)


def test_massachusetts_v36_adds_parts_a_b_and_c():
    output = _run(
        {
            "taxsimid": [1, 2],
            "year": [2024, 2024],
            "state": [22, 22],
            "mstat": [1, 1],
            "page": [40, 40],
            "pwages": [50_000, 50_000],
            "intrec": [0, 3_000],
            "stcg": [0, 2_000],
            "ltcg": [0, 10_000],
            "idtl": [2, 2],
        }
    )
    # Part B: 50,000 - 4,400 exemption - 2,000 FICA deduction = 43,600.
    assert output.loc[1, "v36"] == pytest.approx(43_600, abs=1)
    # Plus Part A 5,000 (interest and short-term gain) and Part C 10,000.
    assert output.loc[2, "v36"] == pytest.approx(58_600, abs=1)


@pytest.mark.skipif(
    "tax_on_taxable_income_at_main_rates" not in system.variables,
    reason="needs policyengine-us 2.29.12 or later",
)
def test_v19_taxes_all_taxable_income_at_ordinary_rates():
    output = _run(
        {
            "taxsimid": [1],
            "year": [2024],
            "state": [0],
            "mstat": [1],
            "page": [40],
            "pwages": [60_000],
            "ltcg": [20_000],
            "idtl": [2],
        }
    )
    # Taxable income 80,000 - 14,600 = 65,400, all at the 2024 single
    # schedule: 1,160 + 4,266 + 22% of 18,250 = 9,441 (TAXSIM-35 v19).
    assert output.loc[1, "v18"] == pytest.approx(65_400, abs=1)
    assert output.loc[1, "v19"] == pytest.approx(9_441, abs=1)
