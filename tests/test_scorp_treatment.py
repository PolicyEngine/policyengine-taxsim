"""NIIT classification must not change AGI, QBI or SECA."""

import importlib
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner
from policyengine_us import Simulation

from policyengine_taxsim import generate_household, export_household
from policyengine_taxsim.cli import cli
from policyengine_taxsim.core.scorp_reform import scorp_tax_benefit_system
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def record(scorp=300000, mstat=1, wages=0, interest=0, **extra):
    return dict(
        taxsimid=1,
        year=2025,
        state=0,
        mstat=mstat,
        page=45,
        sage=45 if mstat == 2 else 0,
        depx=0,
        pwages=wages,
        scorp=scorp,
        intrec=interest,
        idtl=2,
        **extra,
    )


CASES = [
    record(0),
    record(150000),
    record(200000),
    record(300000),
    record(250000, mstat=2),
    record(300000, mstat=2),
    record(100000, wages=250000),
    record(-100000, wages=300000),
    record(-100000, wages=300000, interest=150000),
]


@pytest.fixture(scope="module")
def results():
    df = pd.DataFrame(CASES)
    df["taxsimid"] = np.arange(1, len(df) + 1)
    return {
        (mode, w2): PolicyEngineRunner(
            df.copy(), scorp_treatment=mode, assume_w2_wages=w2
        ).run(show_progress=False)
        for w2 in (False, True)
        for mode in ("active", "passive")
    }


def test_batch_thresholds_and_losses(results):
    active, passive = results["active", True], results["passive", True]
    assert passive.niit.to_numpy() == pytest.approx(
        [0, 0, 0, 3800, 0, 1900, 3800, 0, 1900], abs=1
    )
    assert active.niit.to_numpy() == pytest.approx([0] * 8 + [5700], abs=1)
    # All federal change comes from NIIT, including the signed-loss case.
    assert (passive.fiitax - active.fiitax).to_numpy() == pytest.approx(
        (passive.niit - active.niit).to_numpy(), abs=1
    )


def test_qbi_and_w2_are_independent(results):
    for w2 in (False, True):
        active, passive = results["active", w2], results["passive", w2]
        for column in ("v10", "qbid", "fica"):
            assert passive[column].to_numpy() == pytest.approx(
                active[column].to_numpy(), abs=1
            )
    assert (
        results["passive", True].qbid.iloc[3] > results["passive", False].qbid.iloc[3]
    )


@pytest.mark.parametrize("mode", ["passive", "active"])
def test_single_household_and_spouse_allocation(mode, results):
    row = record(300000, mstat=2)
    situation = generate_household(row.copy(), scorp_treatment=mode)
    expected = 150000 if mode == "passive" else 0
    for name in ("you", "your partner"):
        assert situation["people"][name]["partnership_s_corp_income"]["2025"] == 150000
        assert (
            situation["people"][name]["passive_partnership_s_corp_income"]["2025"]
            == expected
        )
    output = export_household(row, situation, False, False)
    assert float(output["niit"]) == pytest.approx(
        results[mode, False].niit.iloc[5], abs=1
    )
    assert float(output["fiitax"]) == pytest.approx(
        results[mode, False].fiitax.iloc[5], abs=1
    )


def test_default_and_validation():
    assert (
        generate_household(record())["people"]["you"][
            "passive_partnership_s_corp_income"
        ]["2025"]
        == 300000
    )
    assert PolicyEngineRunner(pd.DataFrame([record()])).scorp_treatment == "passive"
    with pytest.raises(ValueError, match="scorp_treatment"):
        generate_household(record(), scorp_treatment="typo")
    with pytest.raises(ValueError, match="scorp_treatment"):
        PolicyEngineRunner(pd.DataFrame([record()]), scorp_treatment="typo")


def test_compatibility_reform_does_not_double_count():
    situation = generate_household(record())
    sim = Simulation(situation=situation, tax_benefit_system=scorp_tax_benefit_system())
    assert sim.calculate("adjusted_gross_income", "2025")[0] == pytest.approx(300000)
    assert sim.calculate("net_investment_income", "2025")[0] == pytest.approx(300000)
    assert sim.calculate("net_investment_income_tax", "2025")[0] == pytest.approx(3800)


@pytest.mark.parametrize("command", ["stdin", "policyengine", "compare"])
def test_cli_forwards_switch(command, tmp_path):
    path = tmp_path / "input.csv"
    csv = pd.DataFrame([record()]).to_csv(index=False)
    path.write_text(csv)
    module = importlib.import_module("policyengine_taxsim.cli")
    target = "PolicyEngineRunner" if command == "compare" else "StitchedRunner"
    args = (
        ["--scorp-treatment", "active"]
        if command == "stdin"
        else [command, str(path), "--scorp-treatment", "active"]
    )
    # Stop before model work; verify the selected mode reaches the actual runner.
    with patch.object(module, target, side_effect=RuntimeError("stop")) as runner:
        CliRunner().invoke(cli, args, input=csv)
    assert runner.call_args.kwargs["scorp_treatment"] == "active"
