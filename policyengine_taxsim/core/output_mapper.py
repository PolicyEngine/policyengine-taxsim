from .utils import (
    load_variable_mappings,
    get_state_number,
    to_roundedup_number,
)
from policyengine_us import Simulation
from policyengine_tests_generator.core.generator import PETestsYAMLGenerator


def generate_non_description_output(
    taxsim_output, mappings, year, state_name, simulation, output_type, logs
):
    outputs = []
    for key, each_item in mappings.items():
        if each_item["implemented"]:
            if key == "taxsimid":
                taxsim_output[key] = taxsim_output["taxsimid"]
            elif key == "year":
                taxsim_output[key] = int(year)
            elif key == "state":
                taxsim_output[key] = get_state_number(state_name)
            elif "variables" in each_item and len(each_item["variables"]) > 0:
                pe_variables = each_item["variables"]
                taxsim_output[key] = simulate_multiple(simulation, pe_variables, year)
            else:
                pe_variable = each_item["variable"]
                state_initial = state_name.lower()

                if "state" in pe_variable:
                    pe_variable = pe_variable.replace("state", state_initial)

                for entry in each_item["idtl"]:
                    if output_type in entry.values():

                        if "special_cases" in each_item:
                            found_state = next(
                                (
                                    each
                                    for each in each_item["special_cases"]
                                    if state_initial in each
                                ),
                                None,
                            )
                            if (
                                found_state
                                and found_state[state_initial]["implemented"]
                            ):
                                pe_variable = (
                                    found_state[state_initial]["variable"].replace(
                                        "state", state_initial
                                    )
                                    if "state" in found_state[state_initial]["variable"]
                                    else found_state[state_initial]["variable"]
                                )
                        taxsim_output[key] = simulate(simulation, pe_variable, year)
                        outputs.append(
                            {"variable": pe_variable, "value": taxsim_output[key]}
                        )

    file_name = f"{taxsim_output['taxsimid']}-{state_name}.yaml"
    generate_pe_tests_yaml(simulation.situation_input, outputs, file_name, logs)

    return taxsim_output


def generate_pe_tests_yaml(household, outputs, file_name, logs):
    if logs:
        generator = PETestsYAMLGenerator()
        yaml_data = generator.generate_yaml(
            household_data=household, name=file_name, pe_outputs=outputs
        )
        output = generator._get_yaml(yaml_data)
        with open(file_name, "w") as f:
            f.write(output)


def generate_text_description_output(
    taxsim_input, mappings, year, state_name, simulation, simulation_1dollar_more, logs
):
    groups = {}
    group_orders = {}

    for var_name, var_info in mappings.items():
        if (
            "full_text_group" in var_info
            and "text_description" in var_info
            and "implemented" in var_info
            and var_info["implemented"] is True
            and any(item.get("full_text", 0) == 5 for item in var_info["idtl"])
        ):
            group = var_info["full_text_group"]
            group_order = var_info["group_order"]

            if group not in groups:
                groups[group] = []
                group_orders[group] = group_order

            groups[group].append((var_info["text_description"], var_name, var_info))

    # Configuration for formatting
    LEFT_MARGIN = 4
    LABEL_INDENT = 4
    LABEL_WIDTH = 45
    VALUE_WIDTH = 15
    SECOND_VALUE_WIDTH = 12
    GROUP_MARGIN = LEFT_MARGIN  # Groups are 2 tabs left of text_description

    lines = [""]
    sorted_groups = sorted(groups.keys(), key=lambda x: group_orders[x])
    outputs = []
    for group_name in sorted_groups:
        variables = groups[group_name]
        if variables:
            # Check if this group has any variables with group_column = 2
            has_second_column = any(
                var_info.get("group_column", 1) == 2 for _, _, var_info in variables
            )

            if has_second_column:
                # Group headers are 2 tabs left of text_description
                line = f"{' ' * GROUP_MARGIN}{group_name}:"
                padding = " " * (
                    LABEL_WIDTH + LABEL_INDENT - len(group_name) - 1
                )  # -1 for the colon
                base_text = f"{'Base':>8}"
                plus_one_text = f"{'':>8}"
                lines.append(
                    f"{line}{padding}{base_text:>{VALUE_WIDTH}}{plus_one_text:>{SECOND_VALUE_WIDTH}}"
                )
            else:
                # Group headers are 2 tabs left of text_description
                lines.append(f"{' ' * GROUP_MARGIN}{group_name}:")

            state_initial = state_name.lower()

            for desc, var_name, each_item in sorted(variables, key=lambda x: x[0]):
                variable = each_item["variable"]
                has_second_column = each_item.get("group_column", 1) == 2

                if "state" in variable:
                    variable = variable.replace("state", state_name).lower()
                if var_name == "taxsimid":
                    value = taxsim_input["taxsimid"]
                elif var_name == "year":
                    value = year
                elif var_name == "state":
                    value = (
                        f"{get_state_number(state_name)}{' ' * LEFT_MARGIN}{state_name}"
                    )
                elif "variables" in each_item and len(each_item["variables"]) > 0:
                    value = simulate_multiple(simulation, each_item["variables"], year)
                else:
                    if "special_cases" in each_item:
                        found_state = next(
                            (
                                each
                                for each in each_item["special_cases"]
                                if state_initial in each
                            ),
                            None,
                        )
                        if found_state and found_state[state_initial]["implemented"]:
                            variable = (
                                found_state[state_initial]["variable"].replace(
                                    "state", state_initial
                                )
                                if "state" in found_state[state_initial]["variable"]
                                else found_state[state_initial]["variable"]
                            )
                    value = simulate(simulation, variable, year)
                    outputs.append({"variable": variable, "value": value})

                # Format the base value
                if isinstance(value, (int, float)):
                    formatted_value = f"{value:>8.1f}"
                else:
                    formatted_value = str(value)

                # Format second column value if needed
                if has_second_column:
                    if "variables" in each_item and len(each_item["variables"]) > 0:
                        second_value = simulate_multiple(
                            simulation_1dollar_more, each_item["variables"], year
                        )
                    else:
                        if "special_cases" in each_item:
                            found_state = next(
                                (
                                    each
                                    for each in each_item["special_cases"]
                                    if state_initial in each
                                ),
                                None,
                            )
                            if (
                                found_state
                                and found_state[state_initial]["implemented"]
                            ):
                                variable = (
                                    found_state[state_initial]["variable"].replace(
                                        "state", state_initial
                                    )
                                    if "state" in found_state[state_initial]["variable"]
                                    else found_state[state_initial]["variable"]
                                )
                        second_value = simulate(simulation_1dollar_more, variable, year)

                    if isinstance(second_value, (int, float)):
                        formatted_second_value = f"{second_value:>8.1f}"
                    else:
                        formatted_second_value = str(second_value)

                # Handle multi-line descriptions
                desc_lines = desc.split("\n")
                for desc_line_index, desc_line in enumerate(desc_lines):
                    indent = LEFT_MARGIN + LABEL_INDENT
                    if has_second_column:
                        line = f"{' ' * indent}{desc_line:<{LABEL_WIDTH}}{formatted_value:>{VALUE_WIDTH}}"
                        if desc_line_index == 0:  # Only add second value on first line
                            line += f"{formatted_second_value:>{SECOND_VALUE_WIDTH}}"
                    else:
                        line = f"{' ' * indent}{desc_line:<{LABEL_WIDTH}}{formatted_value:>{VALUE_WIDTH}}"
                    lines.append(line)

            lines.append("")

    file_name = f"{taxsim_input['taxsimid']}-{state_name}.yaml"
    generate_pe_tests_yaml(simulation.situation_input, outputs, file_name, logs)

    return "\n".join(lines)


def taxsim_input_definition(data_dict, year, state_name):
    """Process a dictionary of data according to the configuration."""
    output_lines = []
    mappings = load_variable_mappings()["taxsim_input_definition"]

    # Header lines using year from input data
    current_year = data_dict.get("year", year)

    output_lines.extend(["   Input Data:"])

    # Configuration for formatting
    LEFT_MARGIN = 4
    LABEL_INDENT = 4
    LABEL_WIDTH = 45
    VALUE_WIDTH = 15
    SECOND_VALUE_WIDTH = 12

    # Process each field from mappings in order
    for mapping in mappings:
        field, config = next(iter(mapping.items()))

        # Check if field exists in data_dict
        if field in data_dict:
            value = data_dict[field]
            name = config["name"]
            # Handle paired fields
            if "pair" in config and config["pair"] in data_dict:
                pair_field = config["pair"]
                pair_value = data_dict[pair_field]

                indent = LEFT_MARGIN + LABEL_INDENT
                line = f"{' ' * indent}{name:<{LABEL_WIDTH}}{float(value):>{VALUE_WIDTH}.2f}"
                line += f"{float(pair_value):>{SECOND_VALUE_WIDTH}.2f}"
                output_lines.append(line)
            else:
                # Format and append the line
                indent = LEFT_MARGIN + LABEL_INDENT

                if field == "mstat" and "type" in config:
                    try:
                        if isinstance(value, str):
                            if value.lower() == "single":
                                output_lines.append(
                                    f"{' ' * indent}{name:<{LABEL_WIDTH}}{1:>{VALUE_WIDTH}.2f} {value.lower()}"
                                )
                                value = 1
                            elif value.lower() == "joint":
                                output_lines.append(
                                    f"{' ' * indent}{name:<{LABEL_WIDTH}}{2:>{VALUE_WIDTH}.2f} {value.lower()}"
                                )
                                value = 2
                    except (ValueError, AttributeError) as e:
                        print(e)

                if field == "state":
                    output_lines.append(
                        f"{' ' * indent}{name:<{LABEL_WIDTH}}{value:>{VALUE_WIDTH}.2f} {state_name}"
                    )
                else:
                    try:
                        float_value = float(value)
                        output_lines.append(
                            f"{' ' * indent}{name:<{LABEL_WIDTH}}{float_value:>{VALUE_WIDTH}.2f}"
                        )
                    except (ValueError, TypeError):
                        output_lines.append(
                            f"{' ' * indent}{name:<{LABEL_WIDTH}}{str(value):>{VALUE_WIDTH}}"
                        )
        else:
            # If field doesn't exist in data_dict, output zero
            name = config["name"]
            indent = LEFT_MARGIN + LABEL_INDENT
            # Handle paired fields that don't exist
            if "pair" in config:
                line = f"{' ' * indent}{name:<{LABEL_WIDTH}}{0:>{VALUE_WIDTH}.2f}"
                line += f"{0:>{SECOND_VALUE_WIDTH}.2f}"
                output_lines.append(line)
            else:
                output_lines.append(
                    f"{' ' * indent}{name:<{LABEL_WIDTH}}{0:>{VALUE_WIDTH}.2f}"
                )

    return "\n".join(output_lines)


def add_a_dollar(data):
    """
    Recursively traverse through JSON data and add $1 to all employment_income values.

    Args:
        data: Dict or list containing the JSON data

    Returns:
        Updated data structure with modified employment_income values
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "employment_income" and isinstance(value, dict):
                for year in value:
                    value[year] += 1
            elif isinstance(value, (dict, list)):
                add_a_dollar(value)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                add_a_dollar(item)

    return data


def export_household(taxsim_input, policyengine_situation, logs):
    """
    Convert a PolicyEngine situation to TAXSIM output variables.

    Args:
        policyengine_situation (dict): PolicyEngine situation dictionary

    Returns:
        dict: Dictionary of TAXSIM output variables
    """
    mappings = load_variable_mappings()["policyengine_to_taxsim"]

    simulation = Simulation(situation=policyengine_situation)

    year = list(
        policyengine_situation["households"]["your household"]["state_name"].keys()
    )[0]

    state_name = policyengine_situation["households"]["your household"]["state_name"][
        year
    ]

    taxsim_output = {}
    taxsim_output["taxsimid"] = policyengine_situation.get(
        "taxsimid", taxsim_input["taxsimid"]
    )
    output_type = taxsim_input["idtl"]

    if int(output_type) in [0, 2]:
        return generate_non_description_output(
            taxsim_output, mappings, year, state_name, simulation, output_type, logs
        )
    else:
        input_definitions_lines = taxsim_input_definition(
            taxsim_input, year, state_name
        )
        a_dollar_more_situation = add_a_dollar(policyengine_situation)
        simulation_a_dollar_more = Simulation(situation=a_dollar_more_situation)
        output = generate_text_description_output(
            taxsim_input,
            mappings,
            year,
            state_name,
            simulation,
            simulation_a_dollar_more,
            logs,
        )
        return f"{input_definitions_lines}\n{output}\n"


def simulate(simulation, variable, year):
    try:
        return to_roundedup_number(simulation.calculate(variable, period=year))
    except Exception as error:
        return 0.00


def simulate_multiple(simulation, variables, year):
    try:
        total = sum(
            to_roundedup_number(simulation.calculate(variable, period=year))
            for variable in variables
        )
    except Exception as error:
        total = 0.00
    return to_roundedup_number(total)
