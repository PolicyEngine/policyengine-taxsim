from types import SimpleNamespace

import numpy as np

from policyengine_taxsim.core.output_mapper import calculate_single_variable_output
from policyengine_taxsim.core.state_output_resolver import (
    calculate_state_mapped_output,
    get_state_specific_variable_name,
)


def _fake_parameters():
    return SimpleNamespace(
        gov=SimpleNamespace(
            states=SimpleNamespace(
                ok=SimpleNamespace(
                    tax=SimpleNamespace(
                        income=SimpleNamespace(
                            credits=SimpleNamespace(
                                child=SimpleNamespace(
                                    agi_limit=100_000,
                                    cdcc_fraction=0.2,
                                    ctc_fraction=0.05,
                                )
                            )
                        )
                    )
                )
            )
        )
    )


class FakeTaxBenefitSystem:
    def parameters(self, year):
        return _fake_parameters()


class FakeSimulation:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.tax_benefit_system = FakeTaxBenefitSystem()

    def calculate(self, variable, period):
        self.calls.append(variable)
        if variable not in self.responses:
            raise ValueError(f"Variable {variable} does not exist")
        value = self.responses[variable]
        if isinstance(value, Exception):
            raise value
        return value


def test_get_state_specific_variable_name_only_replaces_prefix():
    assert get_state_specific_variable_name("state_agi", "PA") == "pa_agi"
    assert (
        get_state_specific_variable_name("taxsim_v32_state_agi", "PA")
        == "taxsim_v32_state_agi"
    )


def test_calculate_single_variable_output_prefers_pe_us_taxsim_var():
    mapping = {
        "variable": "taxsim_v32_state_agi",
        "state_variables": {"PA": "pa_eligibility_income"},
    }
    simulation = FakeSimulation({"taxsim_v32_state_agi": 81_000.0})

    value = calculate_single_variable_output(simulation, mapping, "2023", "PA")

    assert value == 81_000.0
    assert simulation.calls == ["taxsim_v32_state_agi"]


def test_calculate_single_variable_output_falls_back_to_state_mapping():
    mapping = {
        "variable": "taxsim_v36_taxable_income",
        "state_variables": {"PA": "pa_adjusted_taxable_income"},
    }
    simulation = FakeSimulation(
        {
            "taxsim_v36_taxable_income": ValueError(
                "Variable taxsim_v36_taxable_income does not exist"
            ),
            "state_taxable_income": ValueError(
                "Variable state_taxable_income does not exist"
            ),
            "pa_adjusted_taxable_income": 76_000.0,
        }
    )

    value = calculate_single_variable_output(simulation, mapping, "2023", "PA")

    assert value == 76_000.0
    assert simulation.calls == [
        "taxsim_v36_taxable_income",
        "state_taxable_income",
        "pa_adjusted_taxable_income",
    ]


def test_calculate_single_variable_output_prefers_legacy_unified_fallback():
    mapping = {
        "variable": "taxsim_v32_state_agi",
        "state_variables": {"PA": "pa_eligibility_income"},
    }
    simulation = FakeSimulation(
        {
            "taxsim_v32_state_agi": ValueError(
                "Variable taxsim_v32_state_agi does not exist"
            ),
            "state_agi": 81_000.0,
        }
    )

    value = calculate_single_variable_output(simulation, mapping, "2023", "PA")

    assert value == 81_000.0
    assert simulation.calls == [
        "taxsim_v32_state_agi",
        "state_agi",
    ]


def test_calculate_single_variable_output_uses_component_adapter_fallback():
    mapping = {
        "variable": "taxsim_v38_cdcc",
        "state_variables": {"OK": "adapter:ok_child_care_credit_component"},
    }
    simulation = FakeSimulation(
        {
            "taxsim_v38_cdcc": ValueError("Variable taxsim_v38_cdcc does not exist"),
            "adjusted_gross_income": 40_000.0,
            "ok_agi": 20_000.0,
            "cdcc_potential": 1_000.0,
            "ctc_value": 3_000.0,
        }
    )

    value = calculate_single_variable_output(simulation, mapping, "2023", "OK")

    assert value == 100.0


def test_calculate_state_mapped_output_uses_vector_fallback_components():
    mapping = {
        "state_variables": {
            "OK": "adapter:ok_child_care_credit_component",
            "PA": "pa_cdcc",
        }
    }
    state_codes = np.array(["ok", "pa"])
    responses = {
        "adjusted_gross_income": np.array([40_000.0, 50_000.0]),
        "ok_agi": np.array([20_000.0, 0.0]),
        "cdcc_potential": np.array([1_000.0, 0.0]),
        "ctc_value": np.array([3_000.0, 0.0]),
        "pa_cdcc": np.array([0.0, 55.0]),
    }

    result = calculate_state_mapped_output(
        mapping,
        state_codes,
        lambda variable: responses[variable],
        _fake_parameters(),
    )

    assert np.allclose(result, np.array([100.0, 55.0]))
