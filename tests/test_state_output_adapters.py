import re

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.core.state_output_resolver import (
    _try_calculate_variable,
    get_state_specific_variable_name,
)
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
    (
        "v38",
        {
            "year": 2023,
            "state": 37,  # OK
            "pwages": 40_000.0,
            "childcare": 2_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 9,
            "idtl": 2,
            "mstat": 1,
        },
        ["adapter:ok_child_care_credit_component"],
    ),
    (
        "v39",
        {
            "year": 2023,
            "state": 24,  # MN
            "pwages": 20_050.0,
            "depx": 2,
            "age1": 9,
            "age2": 7,
            "taxsimid": 10,
            "idtl": 2,
            "mstat": 4,
        },
        ["mn_wfc"],
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
    (
        "staxbc",
        "Tax before credits",
        {
            "year": 2023,
            "state": 37,  # OK
            "pwages": 40_000.0,
            "childcare": 2_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 11,
            "idtl": 5,
            "mstat": 1,
        },
        ["ok_income_tax_before_credits"],
    ),
    (
        "sctc",
        "Child Tax Credit",
        {
            "year": 2023,
            "state": 37,  # OK
            "pwages": 40_000.0,
            "childcare": 2_000.0,
            "depx": 1,
            "age1": 5,
            "taxsimid": 12,
            "idtl": 5,
            "mstat": 1,
        },
        ["adapter:ok_child_tax_credit_component"],
    ),
    (
        "sctc",
        "Child Tax Credit",
        {
            "year": 2023,
            "state": 24,  # MN
            "pwages": 20_050.0,
            "depx": 2,
            "age1": 9,
            "age2": 7,
            "taxsimid": 13,
            "idtl": 5,
            "mstat": 4,
        },
        ["adapter:mn_child_tax_credit_component"],
    ),
]


def _expected_value(taxsim_input, variables):
    situation = generate_household(dict(taxsim_input))
    simulation = Simulation(situation=situation)
    total = 0.0
    parameter_values = simulation.tax_benefit_system.parameters(
        str(taxsim_input["year"])
    )

    for variable in variables:
        if variable == "adapter:ok_child_care_credit_component":
            adjusted_gross_income = simulation.calculate(
                "adjusted_gross_income",
                period=str(taxsim_input["year"]),
            ).item()
            ok_agi = simulation.calculate(
                "ok_agi",
                period=str(taxsim_input["year"]),
            ).item()
            cdcc_potential = simulation.calculate(
                "cdcc_potential",
                period=str(taxsim_input["year"]),
            ).item()
            ctc_value = simulation.calculate(
                "ctc_value",
                period=str(taxsim_input["year"]),
            ).item()
            agi_ratio = (
                max(0.0, min(1.0, ok_agi / adjusted_gross_income))
                if adjusted_gross_income
                else 0.0
            )
            child_care_credit = (
                (
                    adjusted_gross_income
                    <= parameter_values.gov.states.ok.tax.income.credits.child.agi_limit
                )
                * agi_ratio
                * cdcc_potential
                * float(
                    parameter_values.gov.states.ok.tax.income.credits.child.cdcc_fraction
                )
            )
            child_tax_credit = (
                (
                    adjusted_gross_income
                    <= parameter_values.gov.states.ok.tax.income.credits.child.agi_limit
                )
                * agi_ratio
                * ctc_value
                * float(
                    parameter_values.gov.states.ok.tax.income.credits.child.ctc_fraction
                )
            )
            total += child_care_credit if child_care_credit >= child_tax_credit else 0.0
            continue

        if variable == "adapter:ok_child_tax_credit_component":
            adjusted_gross_income = simulation.calculate(
                "adjusted_gross_income",
                period=str(taxsim_input["year"]),
            ).item()
            ok_agi = simulation.calculate(
                "ok_agi",
                period=str(taxsim_input["year"]),
            ).item()
            cdcc_potential = simulation.calculate(
                "cdcc_potential",
                period=str(taxsim_input["year"]),
            ).item()
            ctc_value = simulation.calculate(
                "ctc_value",
                period=str(taxsim_input["year"]),
            ).item()
            agi_ratio = (
                max(0.0, min(1.0, ok_agi / adjusted_gross_income))
                if adjusted_gross_income
                else 0.0
            )
            child_care_credit = (
                (
                    adjusted_gross_income
                    <= parameter_values.gov.states.ok.tax.income.credits.child.agi_limit
                )
                * agi_ratio
                * cdcc_potential
                * float(
                    parameter_values.gov.states.ok.tax.income.credits.child.cdcc_fraction
                )
            )
            child_tax_credit = (
                (
                    adjusted_gross_income
                    <= parameter_values.gov.states.ok.tax.income.credits.child.agi_limit
                )
                * agi_ratio
                * ctc_value
                * float(
                    parameter_values.gov.states.ok.tax.income.credits.child.ctc_fraction
                )
            )
            total += child_tax_credit if child_tax_credit > child_care_credit else 0.0
            continue

        if variable == "adapter:mn_child_tax_credit_component":
            combined_credit = simulation.calculate(
                "mn_child_and_working_families_credits",
                period=str(taxsim_input["year"]),
            ).item()
            working_family_credit = simulation.calculate(
                "mn_wfc",
                period=str(taxsim_input["year"]),
            ).item()
            total += max(0.0, combined_credit - working_family_credit)
            continue

        total += float(
            simulation.calculate(variable, period=str(taxsim_input["year"])).item()
        )

    return total, situation


def _extract_text_value(text, label, group_name="State Tax Calculation"):
    group_header = f"    {group_name}:"
    try:
        group_text = text.split(group_header, 1)[1].split("\n\n", 1)[0]
    except IndexError as error:
        raise AssertionError(
            f"Could not find '{group_name}' in text output:\n{text}"
        ) from error

    pattern = re.compile(rf"{re.escape(label)}\s+(-?\d+(?:\.\d+)?)")
    match = pattern.search(group_text)
    if not match:
        raise AssertionError(
            f"Could not find '{label}' in '{group_name}' output:\n{group_text}"
        )
    return float(match.group(1))


def test_state_specific_variable_name_only_rewrites_state_prefix():
    assert get_state_specific_variable_name("state_income_tax", "PA") == "pa_income_tax"
    assert (
        get_state_specific_variable_name("reinstate_credit", "DC") == "reinstate_credit"
    )


@pytest.mark.parametrize(("taxsim_var", "taxsim_input", "variables"), DICT_OUTPUT_CASES)
def test_export_household_dict_outputs_use_explicit_state_mappings(
    taxsim_var, taxsim_input, variables
):
    expected, situation = _expected_value(taxsim_input, variables)

    result = export_household(taxsim_input, situation, False, False)

    assert float(result[taxsim_var]) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    ("taxsim_var", "label", "taxsim_input", "variables"), TEXT_OUTPUT_CASES
)
def test_export_household_text_outputs_use_explicit_state_mappings(
    taxsim_var, label, taxsim_input, variables
):
    expected, situation = _expected_value(taxsim_input, variables)

    text = export_household(taxsim_input, situation, False, False)

    assert _extract_text_value(text, label) == pytest.approx(round(expected, 1))


@pytest.mark.parametrize(
    ("taxsim_var", "taxsim_input", "variables"),
    DICT_OUTPUT_CASES
    + [(code, payload, variables) for code, _, payload, variables in TEXT_OUTPUT_CASES],
)
def test_policyengine_runner_state_outputs_use_clean_adapter_mappings(
    taxsim_var, taxsim_input, variables
):
    expected, _ = _expected_value(taxsim_input, variables)

    result = PolicyEngineRunner(
        pd.DataFrame([taxsim_input]), logs=False, disable_salt=False
    ).run(show_progress=False)

    assert float(result[taxsim_var].iloc[0]) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize(
    ("taxsim_input", "component_var", "taxsim_vars"),
    [
        (
            {
                "year": 2023,
                "state": 37,  # OK
                "pwages": 40_000.0,
                "childcare": 2_000.0,
                "depx": 1,
                "age1": 5,
                "taxsimid": 14,
                "idtl": 5,
                "mstat": 1,
            },
            "ok_child_care_child_tax_credit",
            ("v38", "sctc"),
        ),
        (
            {
                "year": 2023,
                "state": 24,  # MN
                "pwages": 20_050.0,
                "depx": 2,
                "age1": 9,
                "age2": 7,
                "taxsimid": 15,
                "idtl": 5,
                "mstat": 4,
            },
            "mn_child_and_working_families_credits",
            ("v39", "sctc"),
        ),
    ],
)
def test_combined_state_credit_outputs_do_not_double_count(
    taxsim_input, component_var, taxsim_vars
):
    expected_total, _ = _expected_value(taxsim_input, [component_var])

    result = PolicyEngineRunner(
        pd.DataFrame([taxsim_input]), logs=False, disable_salt=False
    ).run(show_progress=False)

    total = sum(float(result[var].iloc[0]) for var in taxsim_vars)
    assert total == pytest.approx(expected_total, abs=0.01)


# ---------------------------------------------------------------------------
# Person-level variable aggregation (issue #814)
# ---------------------------------------------------------------------------


class TestTryCalculateVariableAggregation:
    """Unit tests for _try_calculate_variable handling of Person-level arrays."""

    def test_tax_unit_level_array_returned_unchanged(self):
        state_codes = np.array(["MT"])
        result = _try_calculate_variable(
            "some_var", state_codes, lambda v: np.array([500.0])
        )
        assert result is not None
        assert len(result) == 1
        assert result[0] == pytest.approx(500.0)

    def test_person_level_array_summed_to_tax_unit(self):
        state_codes = np.array(["MT"])
        # Simulates a head-only Person variable: [credit, 0, 0]
        result = _try_calculate_variable(
            "some_var", state_codes, lambda v: np.array([800.0, 0.0, 0.0])
        )
        assert result is not None
        assert len(result) == 1
        assert result[0] == pytest.approx(800.0)

    def test_person_level_per_person_values_summed(self):
        state_codes = np.array(["CO"])
        # Simulates a per-person credit: each person gets a different amount
        result = _try_calculate_variable(
            "some_var", state_codes, lambda v: np.array([300.0, 200.0, 50.0])
        )
        assert result is not None
        assert len(result) == 1
        assert result[0] == pytest.approx(550.0)

    def test_scalar_broadcasts_to_state_codes_length(self):
        state_codes = np.array(["CA"])
        result = _try_calculate_variable(
            "some_var", state_codes, lambda v: 42.0
        )
        assert result is not None
        assert len(result) == 1
        assert result[0] == pytest.approx(42.0)

    def test_missing_variable_returns_none(self):
        state_codes = np.array(["MT"])
        result = _try_calculate_variable(
            "some_var",
            state_codes,
            lambda v: (_ for _ in ()).throw(
                ValueError("Variable 'x' does not exist")
            ),
        )
        assert result is None


# Joint-filer integration tests for states with Person-level variables.
# These would crash with a broadcasting ValueError before the fix.
PERSON_LEVEL_JOINT_CASES = [
    (
        "v39",
        {
            "year": 2024,
            "state": 27,  # MT
            "mstat": 2,
            "page": 40,
            "sage": 38,
            "depx": 1,
            "age1": 5,
            "pwages": 30_000.0,
            "swages": 0.0,
            "taxsimid": 100,
            "idtl": 2,
        },
        "mt_eitc",
    ),
    (
        "v37",
        {
            "year": 2024,
            "state": 27,  # MT
            "mstat": 2,
            "page": 70,
            "sage": 68,
            "pwages": 10_000.0,
            "rentpaid": 6_000.0,
            "taxsimid": 101,
            "idtl": 2,
        },
        "mt_elderly_homeowner_or_renter_credit",
    ),
    (
        "v39",
        {
            "year": 2024,
            "state": 26,  # MO
            "mstat": 2,
            "page": 40,
            "sage": 38,
            "depx": 1,
            "age1": 5,
            "pwages": 30_000.0,
            "swages": 0.0,
            "taxsimid": 102,
            "idtl": 2,
        },
        "mo_wftc",
    ),
]


@pytest.mark.parametrize(
    ("taxsim_var", "taxsim_input", "pe_variable"), PERSON_LEVEL_JOINT_CASES
)
def test_joint_filer_person_level_variables_do_not_crash(
    taxsim_var, taxsim_input, pe_variable
):
    """Regression test for issue #814: Person-level variables must not cause
    a broadcasting error for joint filers (multiple persons in one tax unit)."""
    situation = generate_household(dict(taxsim_input))
    simulation = Simulation(situation=situation)
    year = str(taxsim_input["year"])

    # Compute expected by summing the person-level array
    raw = simulation.calculate(pe_variable, period=year)
    expected = float(np.asarray(raw, dtype=float).sum())

    result = export_household(taxsim_input, situation, False, False)

    assert float(result[taxsim_var]) == pytest.approx(expected, abs=0.01)
