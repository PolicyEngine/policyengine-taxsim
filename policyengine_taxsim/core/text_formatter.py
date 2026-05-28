"""
Format a single PE-Microsim result row in TAXSIM-35's labeled-section
text output (idtl=5). Reads values from the result DataFrame row plus
the input row; does not run a fresh Simulation. Mirrors the legacy
output from `generate_text_description_output` so the cli stdin/stdout
flow can emit idtl=5 output without falling back to per-row Simulation.
"""

from typing import Mapping

from .utils import (
    load_variable_mappings,
    get_state_code,
    get_state_number,
)


# Layout constants — match legacy generate_text_description_output for
# bit-identical output formatting.
_LEFT_MARGIN = 4
_LABEL_INDENT = 4
_LABEL_WIDTH = 45
_VALUE_WIDTH = 15
_SECOND_VALUE_WIDTH = 12
_GROUP_MARGIN = _LEFT_MARGIN


def _format_value(value):
    """Match legacy `f'{value:>8.1f}'` for numeric, str otherwise."""
    if isinstance(value, (int, float)):
        return f"{value:>8.1f}"
    return str(value)


def _format_label_line(desc: str, formatted_value: str) -> str:
    """Indent + label + right-justified value column."""
    indent = _LEFT_MARGIN + _LABEL_INDENT
    return f"{' ' * indent}{desc:<{_LABEL_WIDTH}}{formatted_value:>{_VALUE_WIDTH}}"


def _input_data_section(input_row: Mapping, state_name: str) -> list:
    """Render the 'Input Data:' section from the original TAXSIM input."""
    mappings = load_variable_mappings()["taxsim_input_definition"]
    lines = ["", "   Input Data:"]
    indent = _LEFT_MARGIN + _LABEL_INDENT

    for mapping in mappings:
        field, config = next(iter(mapping.items()))
        if field not in input_row:
            # If the field is in the mapping but not the input row, skip
            # — matches the legacy code's behavior of zero-filling only
            # for the explicit fall-through path (currently dead code).
            continue
        value = input_row[field]
        name = config["name"]
        pair = config.get("pair")
        if pair and pair in input_row:
            pair_value = input_row[pair]
            line = (
                f"{' ' * indent}{name:<{_LABEL_WIDTH}}"
                f"{float(value):>{_VALUE_WIDTH}.2f}"
                f"{float(pair_value):>{_SECOND_VALUE_WIDTH}.2f}"
            )
            lines.append(line)
        elif field == "state":
            lines.append(
                f"{' ' * indent}{name:<{_LABEL_WIDTH}}"
                f"{float(value):>{_VALUE_WIDTH}.2f} {state_name}"
            )
        else:
            try:
                fv = float(value)
                lines.append(
                    f"{' ' * indent}{name:<{_LABEL_WIDTH}}{fv:>{_VALUE_WIDTH}.2f}"
                )
            except (TypeError, ValueError):
                lines.append(
                    f"{' ' * indent}{name:<{_LABEL_WIDTH}}{str(value):>{_VALUE_WIDTH}}"
                )
    return lines


def _grouped_output_sections(result_row: Mapping, year, state_name: str) -> list:
    """Render the post-Input sections (Basic Output, Marginal Rates,
    Federal/State Tax Calc, etc.) by reading variable values straight
    from the Microsim result row using the same YAML metadata the
    legacy renderer uses."""
    pe_to_taxsim = load_variable_mappings()["policyengine_to_taxsim"]

    groups = {}
    group_orders = {}
    for var_name, var_info in pe_to_taxsim.items():
        if not (
            "full_text_group" in var_info
            and "text_description" in var_info
            and var_info.get("implemented") is True
            and any(item.get("full_text", 0) == 5 for item in var_info.get("idtl", []))
        ):
            continue
        group = var_info["full_text_group"]
        group_orders[group] = var_info.get("group_order", 999)
        groups.setdefault(group, []).append(
            (var_info["text_description"], var_name, var_info)
        )

    lines = []
    for group_name in sorted(groups, key=lambda g: group_orders[g]):
        variables = groups[group_name]
        if not variables:
            continue
        lines.append(f"{' ' * _GROUP_MARGIN}{group_name}:")
        for desc, var_name, _info in sorted(variables, key=lambda x: x[0]):
            if var_name == "taxsimid":
                value = result_row.get("taxsimid", 0)
            elif var_name == "year":
                value = year
            elif var_name == "state":
                value = (
                    f"{get_state_number(state_name)}{' ' * _LEFT_MARGIN}{state_name}"
                )
            else:
                # Result DataFrame already has all v-columns from the
                # output_mapper. NaN → 0.0.
                raw = result_row.get(var_name, 0)
                try:
                    value = float(raw) if raw is not None else 0.0
                except (TypeError, ValueError):
                    value = raw

            formatted_value = _format_value(value)
            for desc_line in desc.split("\n"):
                lines.append(_format_label_line(desc_line, formatted_value))
        lines.append("")
    return lines


def format_row(input_row: Mapping, result_row: Mapping) -> str:
    """Format a single record's full TAXSIM idtl=5 output."""
    year = int(float(input_row.get("year", result_row.get("year", 0))))
    state_code = int(float(input_row.get("state", result_row.get("state", 0))))
    state_name = get_state_code(state_code)

    lines = _input_data_section(input_row, state_name)
    lines.append("")
    lines.extend(_grouped_output_sections(result_row, year, state_name))
    return "\n".join(lines)
