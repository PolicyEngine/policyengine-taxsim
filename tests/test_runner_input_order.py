"""PolicyEngineRunner returns records in input order, as TAXSIM does.

The runner simulates one tax year at a time. It used to return the rows
grouped by year, so a file whose first records were 2022 and whose next
records were 2021 came back with the 2021 records first (taxsim #1400).
"""

import pandas as pd

from policyengine_taxsim.runners import PolicyEngineRunner


def test_mixed_years_come_back_in_input_order():
    # Years out of order, and taxsimid 1 repeated across years (panel input),
    # so the order must follow positions, not ids.
    records = pd.DataFrame(
        {
            "taxsimid": [1, 2, 3, 1, 4],
            "year": [2022, 2022, 2021, 2021, 2023],
            "state": [44, 44, 44, 44, 44],
            "mstat": [1, 1, 1, 1, 1],
            "page": [40, 40, 40, 40, 40],
            "pwages": [10_000, 20_000, 30_000, 40_000, 50_000],
            "idtl": [2, 2, 2, 2, 2],
        }
    )

    output = PolicyEngineRunner(records).run(show_progress=False)

    assert output["taxsimid"].astype(int).tolist() == [1, 2, 3, 1, 4]
    assert output["year"].astype(int).tolist() == [2022, 2022, 2021, 2021, 2023]
    # Each row carries its own record's result: AGI is the wages here.
    assert output["v10"].astype(float).tolist() == [
        10_000,
        20_000,
        30_000,
        40_000,
        50_000,
    ]
