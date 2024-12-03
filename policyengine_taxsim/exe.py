import click
import pandas as pd
from pathlib import Path
import sys
import os


# Delay imports until runtime
def get_mappers():
    from policyengine_taxsim.core.input_mapper import generate_household
    from policyengine_taxsim.core.output_mapper import export_household
    return generate_household, export_household


def get_yaml_path():
    """Get the path to YAML whether running as script or frozen executable"""
    if getattr(sys, 'frozen', False):
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
@click.option('--logs', is_flag=True, help='Generate PE YAML Tests Logs')
def main(input_file, output, logs):
    """
    Process TAXSIM input file and generate PolicyEngine-compatible output.
    """
    try:
        # Get mapper functions at runtime
        import_single_household, export_single_household = get_mappers()

        # Read input file
        df = pd.read_csv(input_file)

        # Process each row
        results = []
        for _, row in df.iterrows():
            taxsim_input = row.to_dict()
            pe_situation = import_single_household(taxsim_input)
            taxsim_output = export_single_household(taxsim_input, pe_situation, logs)
            results.append(taxsim_output)

        # Create output dataframe and save to csv
        output_df = pd.DataFrame(results)
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_df.to_csv(output_path, index=False)
        click.echo(f"Output saved to {output}")
    except Exception as e:
        click.echo(f"Error processing input: {str(e)}", err=True)
        raise


if __name__ == "__main__":
    main()