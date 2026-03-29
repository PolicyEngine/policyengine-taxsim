from __future__ import annotations

import numpy as np


COMPONENT_ADAPTERS = {
    "adapter:ar_agi",
    "adapter:de_agi",
    "adapter:mn_child_tax_credit_component",
    "adapter:mt_agi",
    "adapter:mt_taxable_income",
    "adapter:ok_child_care_credit_component",
    "adapter:ok_child_tax_credit_component",
}
MISSING_VARIABLE_MESSAGES = ("does not exist", "was not found")


def get_state_specific_variable_name(variable: str, state_code: str) -> str:
    if not variable or not variable.startswith("state_"):
        return variable

    return variable.replace("state_", f"{state_code.lower()}_", 1)


def has_state_variable_mapping(mapping: dict) -> bool:
    return bool(mapping.get("state_variables"))


def get_state_mapped_variables(mapping: dict, state_code: str) -> list[str]:
    mapped = mapping.get("state_variables", {}).get(state_code.upper())
    return _normalize_mapping_value(mapped)


def calculate_scalar_state_mapped_output(
    mapping: dict,
    state_code: str,
    calculate,
    parameter_values,
) -> float:
    total = 0.0

    for variable in get_state_mapped_variables(mapping, state_code):
        total += calculate_scalar_named_output(
            variable,
            state_code,
            calculate,
            parameter_values,
        )

    return float(total)


def calculate_scalar_named_output(
    variable: str,
    state_code: str,
    calculate,
    parameter_values,
) -> float:
    if variable in COMPONENT_ADAPTERS:
        return _calculate_scalar_component_adapter(
            variable,
            state_code.upper(),
            calculate,
            parameter_values,
        )

    resolved = get_state_specific_variable_name(variable, state_code)
    value = _try_calculate_scalar(resolved, calculate)
    return 0.0 if value is None else value


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

    result = _try_calculate_variable(variable, normalized_state_codes, calculate)
    if result is None:
        return np.zeros(len(normalized_state_codes), dtype=float)

    return result


def is_missing_variable_error(error: Exception) -> bool:
    return any(message in str(error) for message in MISSING_VARIABLE_MESSAGES)


def _calculate_scalar_component_adapter(
    variable: str,
    state_code: str,
    calculate,
    parameter_values,
) -> float:
    if variable == "adapter:ar_agi":
        return max(
            calculate_scalar_named_output(
                "ar_agi_indiv", state_code, calculate, parameter_values
            ),
            calculate_scalar_named_output(
                "ar_agi_joint", state_code, calculate, parameter_values
            ),
        )

    if variable == "adapter:de_agi":
        return max(
            calculate_scalar_named_output(
                "de_agi_indiv", state_code, calculate, parameter_values
            ),
            calculate_scalar_named_output(
                "de_agi_joint", state_code, calculate, parameter_values
            ),
        )

    if variable == "adapter:mt_agi":
        value = _try_calculate_scalar("state_agi", calculate)
        return 0.0 if value is None else value

    if variable == "adapter:mt_taxable_income":
        return max(
            calculate_scalar_named_output(
                "mt_taxable_income_indiv", state_code, calculate, parameter_values
            ),
            calculate_scalar_named_output(
                "mt_taxable_income_joint", state_code, calculate, parameter_values
            ),
        )

    if variable in {
        "adapter:ok_child_care_credit_component",
        "adapter:ok_child_tax_credit_component",
    }:
        child_care_credit, child_tax_credit = (
            _calculate_ok_child_credit_components_scalar(
                state_code,
                calculate,
                parameter_values,
            )
        )
        if variable == "adapter:ok_child_care_credit_component":
            return child_care_credit
        return child_tax_credit

    if variable == "adapter:mn_child_tax_credit_component":
        combined_credit = calculate_scalar_named_output(
            "mn_child_and_working_families_credits",
            state_code,
            calculate,
            parameter_values,
        )
        working_family_credit = calculate_scalar_named_output(
            "mn_wfc", state_code, calculate, parameter_values
        )
        return max(0.0, combined_credit - working_family_credit)

    raise KeyError(f"Unsupported component adapter: {variable}")


def _calculate_component_adapter(
    variable: str,
    state_codes: np.ndarray,
    calculate,
    parameter_values,
) -> np.ndarray:
    if variable == "adapter:ar_agi":
        return np.maximum(
            calculate_named_output(
                "ar_agi_indiv",
                state_codes,
                calculate,
                parameter_values,
            ),
            calculate_named_output(
                "ar_agi_joint",
                state_codes,
                calculate,
                parameter_values,
            ),
        )

    if variable == "adapter:de_agi":
        return np.maximum(
            calculate_named_output(
                "de_agi_indiv",
                state_codes,
                calculate,
                parameter_values,
            ),
            calculate_named_output(
                "de_agi_joint",
                state_codes,
                calculate,
                parameter_values,
            ),
        )

    if variable == "adapter:mt_agi":
        result = _try_calculate_variable("state_agi", state_codes, calculate)
        if result is None:
            return np.zeros(len(state_codes), dtype=float)
        return result

    if variable == "adapter:mt_taxable_income":
        return np.maximum(
            calculate_named_output(
                "mt_taxable_income_indiv",
                state_codes,
                calculate,
                parameter_values,
            ),
            calculate_named_output(
                "mt_taxable_income_joint",
                state_codes,
                calculate,
                parameter_values,
            ),
        )

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


def _calculate_ok_child_credit_components_scalar(
    state_code: str,
    calculate,
    parameter_values,
) -> tuple[float, float]:
    ok_parameters = parameter_values.gov.states.ok.tax.income.credits.child
    adjusted_gross_income = calculate_scalar_named_output(
        "adjusted_gross_income", state_code, calculate, parameter_values
    )
    ok_agi = calculate_scalar_named_output(
        "ok_agi", state_code, calculate, parameter_values
    )
    cdcc_potential = calculate_scalar_named_output(
        "cdcc_potential", state_code, calculate, parameter_values
    )
    ctc_value = calculate_scalar_named_output(
        "ctc_value", state_code, calculate, parameter_values
    )

    agi_ratio = 0.0
    if adjusted_gross_income != 0:
        agi_ratio = ok_agi / adjusted_gross_income
    prorate = min(1.0, max(0.0, agi_ratio))
    agi_eligible = adjusted_gross_income <= ok_parameters.agi_limit

    child_care_credit = (
        agi_eligible * prorate * cdcc_potential * ok_parameters.cdcc_fraction
    )
    child_tax_credit = agi_eligible * prorate * ctc_value * ok_parameters.ctc_fraction

    return (
        child_care_credit if child_care_credit >= child_tax_credit else 0.0,
        child_tax_credit if child_tax_credit > child_care_credit else 0.0,
    )


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


def _try_calculate_scalar(variable: str, calculate) -> float | None:
    if not variable:
        return None

    try:
        return float(calculate(variable))
    except Exception as error:
        if is_missing_variable_error(error):
            return None
        raise


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
        if is_missing_variable_error(error):
            return None
        raise

    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return np.full(len(state_codes), float(array), dtype=float)
    return array.astype(float, copy=False)
