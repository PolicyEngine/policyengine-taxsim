from .utils import (
    load_variable_mappings,
    get_state_number,
    to_roundedup_number,
)
from policyengine_us import Simulation
from .yaml_generator import generate_pe_tests_yaml

disable_salt_variable = False


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


def generate_text_description_output(
    taxsim_input, mappings, year, state_name, simulation, logs
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
    GROUP_MARGIN = LEFT_MARGIN  # Groups are 2 tabs left of text_description

    lines = [""]
    sorted_groups = sorted(groups.keys(), key=lambda x: group_orders[x])
    outputs = []
    for group_name in sorted_groups:
        variables = groups[group_name]
        if variables:
            # Group headers are 2 tabs left of text_description
            lines.append(f"{' ' * GROUP_MARGIN}{group_name}:")

            state_initial = state_name.lower()

            for desc, var_name, each_item in sorted(variables, key=lambda x: x[0]):
                variable = each_item["variable"]

                if "state" in variable:
                    variable = variable.replace("state", state_initial)
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

                # Handle multi-line descriptions
                desc_lines = desc.split("\n")
                for desc_line in desc_lines:
                    indent = LEFT_MARGIN + LABEL_INDENT
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


def export_household(taxsim_input, policyengine_situation, logs, disable_salt):
    """
    Convert a PolicyEngine situation to TAXSIM output variables.

    Args:
        policyengine_situation (dict): PolicyEngine situation dictionary

    Returns:
        dict: Dictionary of TAXSIM output variables
    """
    global disable_salt_variable
    disable_salt_variable = disable_salt

    mappings = load_variable_mappings()["policyengine_to_taxsim"]

    # Extract the year and state name from the situation
    year = list(
        policyengine_situation["households"]["your household"]["state_name"].keys()
    )[0]
    state_name = policyengine_situation["households"]["your household"]["state_name"][
        year
    ]

    simulation = Simulation(situation=policyengine_situation)

    # If state and local taxes should be set to zero, set it once on the simulation instance with the required period
    if disable_salt:
        simulation.set_input(
            variable_name="state_and_local_sales_or_income_tax", value=0.0, period=year
        )

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
        output = generate_text_description_output(
            taxsim_input,
            mappings,
            year,
            state_name,
            simulation,
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
