"""Oregon rebate output and comparison regressions for issue #1241."""

import re

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
def test_or_kicker_export_and_comparison(
    year, rebate, credits, raw_tax, taxsim_tax, monkeypatch
):
    # Saved audit household 48901. 2023 TAXSIM before-rebate liability is
    # 10,748; the kicker is 44.28% of an explicit 11,220 prior-year tax.
    # PE 1.x defaults that input to zero, while newer PE imputes it from
    # current-year tax. Test output mapping independently of that default.
    build_sim = PolicyEngineRunner._build_configured_sim

    def with_prior_year_tax(self, dataset, chunk_df):
        sim = build_sim(self, dataset, chunk_df)
        sim.set_input("or_tax_before_credits_in_prior_year", str(year), [11220.0])
        return sim

    monkeypatch.setattr(
        PolicyEngineRunner, "_build_configured_sim", with_prior_year_tax
    )

    def situation_for(record):
        situation = generate_household(record.copy())
        tax_unit = next(iter(situation["tax_units"].values()))
        tax_unit["or_tax_before_credits_in_prior_year"] = {str(year): 11220.0}
        return situation

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
    single = export_household(record.copy(), situation_for(record), False, False)
    for result in [batch.iloc[0], single]:
        assert float(result["siitax"]) == pytest.approx(raw_tax, abs=0.05)
        assert float(result["srebate"]) == pytest.approx(rebate, abs=0.05)
        assert float(result["v40"]) == pytest.approx(credits, abs=0.05)
    if year == 2023:
        text_record = dict(record, idtl=5)
        text = export_household(text_record, situation_for(text_record), False, False)
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
