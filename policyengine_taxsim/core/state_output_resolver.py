from __future__ import annotations

import numpy as np

OUTPUT_ADAPTER_BASE_VARIABLES = {
    "taxsim_v32_state_agi": "state_agi",
    "taxsim_v38_cdcc": "state_cdcc",
    "taxsim_v39_eitc": "state_eitc",
    "taxsim_sctc": "state_ctc",
}
DIRECT_STATE_MAPPING_ADAPTERS = {
    "taxsim_staxbc",
    "taxsim_v36_taxable_income",
    "taxsim_v37_property_tax_credit",
}
OUTPUT_ADAPTER_OVERRIDES = {
    "taxsim_v38_cdcc": {"OK": ["adapter:ok_child_care_credit_component"]},
    "taxsim_v39_eitc": {"MN": ["mn_wfc"]},
    "taxsim_sctc": {
        "MN": ["adapter:mn_child_tax_credit_component"],
        "OK": ["adapter:ok_child_tax_credit_component"],
    },
}
COMPONENT_ADAPTERS = {
    "adapter:mn_child_tax_credit_component",
    "adapter:ok_child_care_credit_component",
    "adapter:ok_child_tax_credit_component",
}
OUTPUT_ADAPTERS = set(OUTPUT_ADAPTER_BASE_VARIABLES) | DIRECT_STATE_MAPPING_ADAPTERS
MISSING_VARIABLE_MESSAGES = ("does not exist", "was not found")


def get_state_specific_variable_name(variable: str, state_code: str) -> str:
    if not variable.startswith("state_"):
        return variable

    return variable.replace("state_", f"{state_code.lower()}_", 1)


def has_state_variable_mapping(mapping: dict) -> bool:
    return bool(mapping.get("state_variables"))


def get_state_mapped_variables(mapping: dict, state_code: str) -> list[str]:
    state_variables = mapping.get("state_variables", {})
    mapped = state_variables.get(state_code.upper())
    return _normalize_mapping_value(mapped)


def is_output_adapter(variable: str) -> bool:
    return variable in OUTPUT_ADAPTERS


def calculate_output_adapter(
    mapping: dict,
    state_codes,
    calculate,
    parameter_values,
) -> np.ndarray:
    adapter_name = mapping.get("variable")
    normalized_state_codes = _normalize_state_codes(state_codes)

    if adapter_name in DIRECT_STATE_MAPPING_ADAPTERS:
        return calculate_state_mapped_output(
            mapping,
            normalized_state_codes,
            calculate,
            parameter_values,
        )

    if adapter_name not in OUTPUT_ADAPTER_BASE_VARIABLES:
        raise KeyError(f"Unsupported TAXSIM output adapter: {adapter_name}")

    base_variable = OUTPUT_ADAPTER_BASE_VARIABLES[adapter_name]
    result = _try_calculate_variable(
        base_variable,
        normalized_state_codes,
        calculate,
    )
    if result is None:
        return calculate_state_mapped_output(
            mapping,
            normalized_state_codes,
            calculate,
            parameter_values,
        )

    result = result.copy()
    for state_code, override_variables in OUTPUT_ADAPTER_OVERRIDES.get(
        adapter_name, {}
    ).items():
        state_mask = normalized_state_codes == state_code
        if not state_mask.any():
            continue

        override_value = np.zeros(len(normalized_state_codes), dtype=float)
        for variable in override_variables:
            override_value += calculate_named_output(
                variable,
                normalized_state_codes,
                calculate,
                parameter_values,
            )

        result[state_mask] = override_value[state_mask]

    return result


def calculate_state_mapped_output(
    mapping: dict,
    state_codes,
    calculate,
    parameter_values,
) -> np.ndarray:
    normalized_state_codes = _normalize_state_codes(state_codes)
    result = np.zeros(len(normalized_state_codes), dtype=float)
    cache = {}

    for state_code, mapped in mapping.get("state_variables", {}).items():
        variables = _normalize_mapping_value(mapped)
        if not variables:
            continue

        state_mask = normalized_state_codes == state_code.upper()
        if not state_mask.any():
            continue

        state_value = np.zeros(len(normalized_state_codes), dtype=float)
        for variable in variables:
            if variable not in cache:
                cache[variable] = calculate_named_output(
                    variable,
                    normalized_state_codes,
                    calculate,
                    parameter_values,
                )
            state_value += cache[variable]

        result[state_mask] = state_value[state_mask]

    return result


def calculate_named_output(
    variable: str,
    state_codes,
    calculate,
    parameter_values,
) -> np.ndarray:
    normalized_state_codes = _normalize_state_codes(state_codes)

    if variable in COMPONENT_ADAPTERS:
        return _calculate_component_adapter(
            variable,
            normalized_state_codes,
            calculate,
            parameter_values,
        )

    result = _try_calculate_variable(
        variable,
        normalized_state_codes,
        calculate,
    )
    if result is None:
        return np.zeros(len(normalized_state_codes), dtype=float)

    return result


def _calculate_component_adapter(
    variable: str,
    state_codes: np.ndarray,
    calculate,
    parameter_values,
) -> np.ndarray:
    if variable in {
        "adapter:ok_child_care_credit_component",
        "adapter:ok_child_tax_credit_component",
    }:
        child_care_credit, child_tax_credit = _calculate_ok_child_credit_components(
            state_codes,
            calculate,
            parameter_values,
        )
        if variable == "adapter:ok_child_care_credit_component":
            return child_care_credit
        return child_tax_credit

    if variable == "adapter:mn_child_tax_credit_component":
        combined_credit = calculate_named_output(
            "mn_child_and_working_families_credits",
            state_codes,
            calculate,
            parameter_values,
        )
        working_family_credit = calculate_named_output(
            "mn_wfc",
            state_codes,
            calculate,
            parameter_values,
        )
        return np.maximum(0, combined_credit - working_family_credit)

    raise KeyError(f"Unsupported component adapter: {variable}")


def _calculate_ok_child_credit_components(
    state_codes: np.ndarray,
    calculate,
    parameter_values,
) -> tuple[np.ndarray, np.ndarray]:
    ok_parameters = parameter_values.gov.states.ok.tax.income.credits.child
    adjusted_gross_income = calculate_named_output(
        "adjusted_gross_income",
        state_codes,
        calculate,
        parameter_values,
    )
    ok_agi = calculate_named_output(
        "ok_agi",
        state_codes,
        calculate,
        parameter_values,
    )
    cdcc_potential = calculate_named_output(
        "cdcc_potential",
        state_codes,
        calculate,
        parameter_values,
    )
    ctc_value = calculate_named_output(
        "ctc_value",
        state_codes,
        calculate,
        parameter_values,
    )

    agi_ratio = np.divide(
        ok_agi,
        adjusted_gross_income,
        out=np.zeros(len(state_codes), dtype=float),
        where=adjusted_gross_income != 0,
    )
    prorate = np.clip(agi_ratio, 0, 1)
    agi_eligible = adjusted_gross_income <= ok_parameters.agi_limit

    child_care_credit = (
        agi_eligible * prorate * cdcc_potential * ok_parameters.cdcc_fraction
    )
    child_tax_credit = agi_eligible * prorate * ctc_value * ok_parameters.ctc_fraction

    return (
        np.where(child_care_credit >= child_tax_credit, child_care_credit, 0),
        np.where(child_tax_credit > child_care_credit, child_tax_credit, 0),
    )


def _normalize_mapping_value(mapped) -> list[str]:
    if mapped is None:
        return []

    if isinstance(mapped, str):
        return [mapped]

    return [variable for variable in mapped if variable]


def _normalize_state_codes(state_codes) -> np.ndarray:
    if isinstance(state_codes, str):
        return np.array([state_codes.upper()])

    return np.asarray(state_codes, dtype=str)


def _try_calculate_variable(
    variable: str,
    state_codes: np.ndarray,
    calculate,
) -> np.ndarray | None:
    if not variable:
        return None

    try:
        value = calculate(variable)
    except Exception as error:
        if _is_missing_variable_error(error):
            return None
        raise

    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return np.full(len(state_codes), float(array), dtype=float)

    expected_len = len(state_codes)
    if len(array) > expected_len:
        # Person-level variable: sum to tax-unit level.
        # Each household is processed with a single tax unit,
        # so all person values belong to that one unit.
        return np.array([float(array.sum())])

    return array.astype(float, copy=False)


def _is_missing_variable_error(error: Exception) -> bool:
    return any(message in str(error) for message in MISSING_VARIABLE_MESSAGES)
