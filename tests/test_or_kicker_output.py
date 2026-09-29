"""Oregon kicker and rebate-free credit output regressions for issue #1241."""

import re

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.comparison.comparator import ComparisonConfig, TaxComparator
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

# Saved audit household 48901 (Oregon, joint, no dependents).
OR_RECORD = dict(
    taxsimid=48901,
    state=38,
    mstat=2,
    page=51,
    sage=52,
    pwages=86952.38095238096,
    swages=60761.90476190476,
    intrec=38.625277540563616,
    idtl=2,
)

# TAXSIM output for the same record (opt30=1), identical in every taxsimtest
# build from cd2026081819 to cd2026092717, so it does not depend on the
# September 2026 changes (taxsim #1248). TAXSIM's 2024 output differs across
# those builds (tax before credits 11,079.94 before cd2026092410 and 11,123.69
# after; older builds also add the kicker to v40), so 2024 checks PE only.
# PE credits the kicker on the return year from prior-year tax before credits,
# which TAXSIM inputs do not carry; PE 1.x defaults it to zero and PE 2.x
# imputes current-year tax, so each case sets it explicitly.
OR_TAXSIM = {
    2023: dict(siitax=10748.00, srebate=0.0),
    2025: dict(siitax=10552.13, srebate=0.0),
}


@pytest.mark.parametrize(
    "year,prior_year_tax,kicker,v40,tolerance",
    [
        # 44.28% x 11,342.50, TAXSIM's 2022 staxbc in every build above.
        (2023, 11342.50, 5022.46, 472.0, 1.0),
        # No kicker on even-year returns; v40 is two $249 exemption credits
        # (TAXSIM 2025Aug23, cd2026092410 and cd2026092717 report 498).
        (2024, 11123.69, 0.0, 498.0, None),
        # 9.863%, the rate every build above applies to its 2024 base
        # (1,092.81 / 11,079.94 and 1,097.13 / 11,123.69). PE's 2025 tax
        # before credits is $4.37 above TAXSIM's for reasons unrelated to the
        # kicker, so this case uses the comparator's $15 state tolerance.
        (2025, 11123.69, 1097.13, 512.0, 15.0),
    ],
)
def test_or_kicker_export_and_comparison(
    year, prior_year_tax, kicker, v40, tolerance, monkeypatch
):
    build_sim = PolicyEngineRunner._build_configured_sim

    def with_prior_year_tax(self, *args, **kwargs):
        sim = build_sim(self, *args, **kwargs)
        sim.set_input(
            "or_tax_before_credits_in_prior_year", str(year), [prior_year_tax]
        )
        return sim

    monkeypatch.setattr(
        PolicyEngineRunner, "_build_configured_sim", with_prior_year_tax
    )

    def situation_for(record):
        situation = generate_household(record.copy())
        tax_unit = next(iter(situation["tax_units"].values()))
        tax_unit["or_tax_before_credits_in_prior_year"] = {str(year): prior_year_tax}
        return situation

    record = dict(OR_RECORD, year=year)
    batch = PolicyEngineRunner(pd.DataFrame([record])).run(show_progress=False)
    single = export_household(record.copy(), situation_for(record), False, False)
    for result in [batch.iloc[0], single]:
        assert float(result["srebate"]) == pytest.approx(kicker, abs=0.05)
        assert float(result["v40"]) == pytest.approx(v40, abs=0.05)
    if year == 2023:
        text_record = dict(record, idtl=5)
        text = export_household(text_record, situation_for(text_record), False, False)
        assert re.search(r"40\. Total Credits\s+472\.0", text)
        assert re.search(r"State One-Time Rebate\s+5022\.5", text)
    if year not in OR_TAXSIM:
        return

    taxsim = OR_TAXSIM[year]
    for result in [batch.iloc[0], single]:
        # Liability before rebates matches TAXSIM; only rebate timing differs.
        assert float(result["siitax"]) + float(result["srebate"]) == pytest.approx(
            taxsim["siitax"] + taxsim["srebate"], abs=tolerance
        )
    tx = batch.copy()
    tx["siitax"] = taxsim["siitax"]
    tx["srebate"] = taxsim["srebate"]
    # PE's kicker makes raw state tax differ; the rebate-neutral comparison
    # removes it.
    assert (
        TaxComparator(tx, batch, ComparisonConfig()).compare().state_match_percentage
        == 0.0
    )
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


def test_single_household_rebates_for_multi_person_households():
    # Saved audit household 305 (Maine 2021, joint, one child). TAXSIM reports
    # the $850-per-person relief payment in srebate and keeps it out of v40:
    # siitax -2,110.92, srebate 1,700.00, v40 729.84 in every taxsimtest build
    # from cd2026081819 to cd2026092717. Both emulator paths must agree; the
    # single-household path used to report
    # srebate 0 for households with more than one person and to leave the
    # rebate inside v40.
    record = dict(
        taxsimid=305,
        year=2021,
        state=20,
        mstat=2,
        page=38,
        sage=34,
        depx=1,
        age1=12,
        psemp=-5843.503230437904,
        swages=45041.333333333336,
        intrec=0.7287788215200682,
        idtl=2,
    )
    batch = PolicyEngineRunner(pd.DataFrame([record])).run(show_progress=False)
    single = export_household(
        dict(record), generate_household(dict(record)), False, False
    )
    for result in [batch.iloc[0], single]:
        assert float(result["siitax"]) == pytest.approx(-2110.92, abs=1.0)
        assert float(result["srebate"]) == pytest.approx(1700.0, abs=0.05)
        assert float(result["v40"]) == pytest.approx(729.84, abs=1.0)
