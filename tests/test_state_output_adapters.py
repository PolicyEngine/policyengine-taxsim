import re

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
from policyengine_us import Simulation


DICT_OUTPUT_CASES = [
    (
        "v32",
        {
            "year": 2023,
            "state": 6,  # CO
            "pwages": 81_000.0,
            "taxsimid": 1,
            "idtl": 2,
            "mstat": 1,
        },
        ["adjusted_gross_income"],
    ),
    (
        "v36",
        {
            "year": 2023,
            "state": 39,  # PA
            "pwages": 81_000.0,
            "taxsimid": 2,
            "idtl": 2,
            "mstat": 1,
        },
        ["pa_adjusted_taxable_income"],
    ),
    (
        "v36",
        {
            "year": 2023,
            "state": 30,  # NH
            "intrec": 10_000.0,
            "taxsimid": 3,
            "idtl": 2,
            "mstat": 1,
        },
        ["nh_taxable_income"],
    ),
    (
        "v37",
        {
            "year": 2023,
            "state": 20,  # ME
            "page": 70,
            "pwages": 10_000.0,
            "rentpaid": 12_000.0,
            "taxsimid": 4,
            "idtl": 2,
            "mstat": 1,
        },
        ["me_property_tax_fairness_credit"],
    ),
    (
        "v38",
        {
            "year": 2023,
            "state": 9,  # DC
            "pwages": 25_000.0,
            "childcare": 2_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 5,
            "idtl": 2,
            "mstat": 1,
        },
        ["dc_cdcc", "dc_kccatc"],
    ),
    (
        "v39",
        {
            "year": 2023,
            "state": 48,  # WA
            "pwages": 15_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 6,
            "idtl": 2,
            "mstat": 1,
        },
        ["wa_working_families_tax_credit"],
    ),
]

TEXT_OUTPUT_CASES = [
    (
        "staxbc",
        "Tax before credits",
        {
            "year": 2023,
            "state": 39,  # PA
            "pwages": 81_000.0,
            "taxsimid": 7,
            "idtl": 5,
            "mstat": 1,
        },
        ["state_income_tax_before_refundable_credits"],
    ),
    (
        "sctc",
        "Child Tax Credit",
        {
            "year": 2023,
            "state": 31,  # NJ
            "pwages": 25_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 8,
            "idtl": 5,
            "mstat": 1,
        },
        ["nj_ctc"],
    ),
]


def _expected_value(taxsim_input, variables):
    situation = generate_household(dict(taxsim_input))
    simulation = Simulation(situation=situation)
    total = 0.0

    for variable in variables:
        total += float(
            simulation.calculate(variable, period=str(taxsim_input["year"])).item()
        )

    return total, situation


def _extract_text_value(text, label, group_name="State Tax Calculation"):
    group_header = f"    {group_name}:"
    try:
        group_text = text.split(group_header, 1)[1].split("\n\n", 1)[0]
    except IndexError as error:
        raise AssertionError(f"Could not find '{group_name}' in text output:\n{text}") from error

    pattern = re.compile(rf"{re.escape(label)}\s+(-?\d+(?:\.\d+)?)")
    match = pattern.search(group_text)
    if not match:
        raise AssertionError(
            f"Could not find '{label}' in '{group_name}' output:\n{group_text}"
        )
    return float(match.group(1))


@pytest.mark.parametrize(("taxsim_var", "taxsim_input", "variables"), DICT_OUTPUT_CASES)
def test_export_household_dict_outputs_use_explicit_state_mappings(
    taxsim_var, taxsim_input, variables
):
    expected, situation = _expected_value(taxsim_input, variables)

    result = export_household(taxsim_input, situation, False, False)

    assert float(result[taxsim_var]) == pytest.approx(expected, abs=0.01)
    assert float(result[taxsim_var]) > 0


@pytest.mark.parametrize(
    ("taxsim_var", "label", "taxsim_input", "variables"), TEXT_OUTPUT_CASES
)
def test_export_household_text_outputs_use_explicit_state_mappings(
    taxsim_var, label, taxsim_input, variables
):
    expected, situation = _expected_value(taxsim_input, variables)

    text = export_household(taxsim_input, situation, False, False)

    assert _extract_text_value(text, label) == pytest.approx(expected, abs=0.01)
    assert expected > 0


@pytest.mark.parametrize(
    ("taxsim_var", "taxsim_input", "variables"),
    DICT_OUTPUT_CASES + [(code, payload, variables) for code, _, payload, variables in TEXT_OUTPUT_CASES],
)
def test_policyengine_runner_state_outputs_use_clean_adapter_mappings(
    taxsim_var, taxsim_input, variables
):
    expected, _ = _expected_value(taxsim_input, variables)

    result = PolicyEngineRunner(
        pd.DataFrame([taxsim_input]), logs=False, disable_salt=False
    ).run(show_progress=False)

    assert float(result[taxsim_var].iloc[0]) == pytest.approx(expected, abs=0.01)
    assert expected > 0
