import click
import pandas as pd
from pathlib import Path
import sys
import os
from io import StringIO


# Delay imports until runtime
def get_mappers():
    from policyengine_taxsim.core.input_mapper import generate_household
    from policyengine_taxsim.core.output_mapper import export_household

    return generate_household, export_household


def get_yaml_path():
    """Get the path to YAML whether running as script or frozen executable"""
    if getattr(sys, "frozen", False):
        # Running in a bundle
        return os.path.join(sys._MEIPASS, "config", "variable_mappings.yaml")
    else:
        # Running in normal Python
        return os.path.join(Path(__file__).parent, "config", "variable_mappings.yaml")


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="output.csv",
    help="Output file path",
)
@click.option("--logs", is_flag=True, help="Generate PE YAML Tests Logs")
@click.option(
    "--disable-salt",
    is_flag=True,
    default=False,
    help="Set State and Local Sales or Income Taxes used for the SALT deduction to 0",
)
def main(input_file, output, logs, disable_salt):
    """
    Process TAXSIM input file and generate PolicyEngine-compatible output.
    """
    try:
        # Get mapper functions at runtime
        generate_household, export_household = get_mappers()

        # Read input file
        df = pd.read_csv(input_file)

        # Process each row
        idtl_0_results = []
        idtl_2_results = []
        idtl_5_results = ""

        for _, row in df.iterrows():
            taxsim_input = row.to_dict()
            pe_situation = generate_household(taxsim_input)

            taxsim_output = export_household(
                taxsim_input, pe_situation, logs, disable_salt
            )

            idtl = taxsim_input["idtl"]
            if idtl == 0:
                idtl_0_results.append(taxsim_output)
            elif idtl == 2:
                idtl_2_results.append(taxsim_output)
            else:
                idtl_5_results += taxsim_output

        idtl_0_output = to_csv_str(idtl_0_results)
        idtl_2_output = to_csv_str(idtl_2_results)

        output_str = ""
        if idtl_0_output:
            output_str += idtl_0_output
        if idtl_2_output:
            output_str += f"\n{idtl_2_output}"
        if idtl_5_results:
            output_str += f"\n{idtl_5_results}"

        print(output_str)
    except Exception as e:
        click.echo(f"Error processing input: {str(e)}", err=True)
        raise


def to_csv_str(results):
    if len(results) == 0 or results is None:
        return ""

    df = pd.DataFrame(results)
    content = df.to_csv(index=False, float_format="%.1f", lineterminator="\n")
    cleaned_df = pd.read_csv(StringIO(content))
    return cleaned_df.to_csv(index=False, lineterminator="\n")


if __name__ == "__main__":
    main()
