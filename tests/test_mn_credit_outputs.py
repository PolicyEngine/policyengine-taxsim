"""Minnesota credit output columns (taxsim #1251, #1252).

TAXSIM values below are identical in taxsimtest cd2026081819 and cd2026092717.
"""

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _both_paths(records, idtl=2):
    df = pd.DataFrame(records).assign(idtl=idtl)
    batch = PolicyEngineRunner(df).run(show_progress=False).set_index("taxsimid")
    single = {
        record["taxsimid"]: export_household(
            dict(record, idtl=idtl),
            generate_household(dict(record, idtl=idtl)),
            False,
            False,
        )
        for record in records
    }
    return batch, single


# From 2023 TAXSIM reports Minnesota's whole Child and Working Family Credit in
# v39 and nothing in sctc; before 2023 v39 is the Working Family Credit alone.
CWFC_CASES = [
    # 2024 Schedule M1CWFC: min(earned income, $9,220) x 4% + $1,750 per child
    # (lines 3, 4 and 8); $15,000 is below the $31,090 phase-out start
    # (line 11): 368.80 + 1,750 = 2,118.80. TAXSIM reports 2,100.00.
    (
        dict(taxsimid=1, year=2024, mstat=1, page=30, depx=1, age1=5, pwages=15000),
        2118.80,
    ),
    # No children: 4% x 8,280 = 331.20 (TAXSIM 331.20).
    (dict(taxsimid=2, year=2024, mstat=2, page=40, sage=40, pwages=8280), 331.20),
    # 2022 Working Family Credit (TAXSIM 1,183.00).
    (
        dict(taxsimid=3, year=2022, mstat=1, page=30, depx=1, age1=5, pwages=15000),
        1183.00,
    ),
]


def test_mn_combined_credit_is_in_v39_and_not_sctc():
    records = [dict(record, state=24) for record, _ in CWFC_CASES]
    batch, single = _both_paths(records)
    for record, expected in CWFC_CASES:
        taxsimid = record["taxsimid"]
        assert float(batch.loc[taxsimid, "v39"]) == pytest.approx(expected, abs=1)
        assert float(single[taxsimid]["v39"]) == pytest.approx(expected, abs=1)
    full, _ = _both_paths(records, idtl=5)
    assert full["sctc"].tolist() == [0, 0, 0]


def test_mn_renters_credit_in_v37_and_siitax_on_both_paths():
    # Household from taxsim #1251 without its age-0 dependent. TAXSIM (no
    # option 30): v37 2,640.00, v39 160.62, siitax -2,800.62 for 2024; the
    # renter's credit is not on Form M1 before 2024, so 2023 has v37 0.00 and
    # siitax -160.62 although PE-US computes a backdated credit that year.
    base = dict(
        state=24,
        mstat=2,
        page=24,
        sage=25,
        pwages=2828.6387,
        swages=1186.9766,
        rentpaid=20811.939,
    )
    records = [dict(base, taxsimid=1, year=2024), dict(base, taxsimid=2, year=2023)]
    batch, single = _both_paths(records)
    for taxsimid, v37, siitax in [(1, 2640.00, -2800.62), (2, 0.00, -160.62)]:
        for result in (batch.loc[taxsimid], single[taxsimid]):
            assert float(result["v37"]) == pytest.approx(v37, abs=0.05)
            assert float(result["siitax"]) == pytest.approx(siitax, abs=0.05)
