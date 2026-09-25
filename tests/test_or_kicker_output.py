"""Oregon rebate output and comparison regressions for issue #1241."""

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.comparison.comparator import ComparisonConfig, TaxComparator
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


@pytest.mark.parametrize(
    "year,rebate,credits,raw_tax,taxsim_tax",
    [
        (2023, 4968.22, 472.0, 5779.79, 10748.0),
        (2024, 0.0, 498.0, 10625.69, 10625.69),
    ],
)
def test_or_kicker_export_and_comparison(year, rebate, credits, raw_tax, taxsim_tax):
    # Saved audit household 48901. 2023 TAXSIM before-rebate liability is
    # 10,748; the PE kicker is 44.28% of the 11,220 current-year proxy base.
    record = dict(
        taxsimid=48901,
        year=year,
        state=38,
        mstat=2,
        page=51,
        sage=52,
        pwages=86952.38095238096,
        swages=60761.90476190476,
        intrec=38.625277540563616,
        idtl=2,
    )
    batch = PolicyEngineRunner(pd.DataFrame([record])).run(show_progress=False)
    single = export_household(
        record.copy(), generate_household(record.copy()), False, False
    )
    for result in [batch.iloc[0], single]:
        assert float(result["siitax"]) == pytest.approx(raw_tax, abs=0.05)
        assert float(result["srebate"]) == pytest.approx(rebate, abs=0.05)
        assert float(result["v40"]) == pytest.approx(credits, abs=0.05)
    if year == 2023:
        text_record = dict(record, idtl=5)
        text = export_household(
            text_record, generate_household(text_record.copy()), False, False
        )
        import re

        assert re.search(r"40\. Total Credits\s+472\.0", text)
        assert re.search(r"State One-Time Rebate\s+4968\.2", text)
    tx = batch.copy()
    tx["siitax"] = taxsim_tax
    tx["srebate"] = 0.0
    assert TaxComparator(
        tx, batch, ComparisonConfig()
    ).compare().state_match_percentage == (0.0 if rebate else 100.0)
    assert (
        TaxComparator(tx, batch, ComparisonConfig(net_of_rebates=True))
        .compare()
        .state_match_percentage
        == 100.0
    )
    # Removing rebate timing must not hide an unrelated state-tax difference.
    tx["siitax"] += 100
    assert (
        TaxComparator(tx, batch, ComparisonConfig(net_of_rebates=True))
        .compare()
        .state_match_percentage
        == 0.0
    )
