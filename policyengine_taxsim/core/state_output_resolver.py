from __future__ import annotations


def get_state_specific_variable_name(variable: str, state_code: str) -> str:
    if not variable.startswith("state_"):
        return variable

    return variable.replace("state_", f"{state_code.lower()}_", 1)


def has_state_variable_mapping(mapping: dict) -> bool:
    return bool(mapping.get("state_variables"))


def get_state_mapped_variables(mapping: dict, state_code: str) -> list[str]:
    state_variables = mapping.get("state_variables", {})
    mapped = state_variables.get(state_code.upper())

    if mapped is None:
        return []

    if isinstance(mapped, str):
        return [mapped]

    return [variable for variable in mapped if variable]
