import click
import pandas as pd
from pathlib import Path
from io import StringIO

try:
    from .runners.policyengine_runner import PolicyEngineRunner
    from .runners.taxsim_runner import TaxsimRunner
    from .comparison.comparator import TaxComparator, ComparisonConfig
    from .comparison.statistics import ComparisonStatistics
    from .core.yaml_generator import generate_pe_tests_yaml
    from .core.input_mapper import form_household_situation
    from .core.utils import get_state_code
except ImportError:
    from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner
    from policyengine_taxsim.comparison.comparator import (
        TaxComparator,
        ComparisonConfig,
    )
    from policyengine_taxsim.comparison.statistics import ComparisonStatistics
    from policyengine_taxsim.core.yaml_generator import generate_pe_tests_yaml
    from policyengine_taxsim.core.input_mapper import form_household_situation
    from policyengine_taxsim.core.utils import get_state_code


def _generate_yaml_files(input_df: pd.DataFrame, results_df: pd.DataFrame):
    """Generate YAML test files for each record when logs=True"""
    for idx, row in input_df.iterrows():
        try:
            # Create household data for this record
            year = int(row["year"])
            state = get_state_code(int(row["state"]))

            # Convert taxsim data to proper types
            taxsim_data = row.to_dict()
            for key, value in taxsim_data.items():
                if isinstance(value, float) and value.is_integer():
                    taxsim_data[key] = int(value)

            household = form_household_situation(year, state, taxsim_data)

            # Get results for this record from results_df
            result_row = results_df.iloc[idx]

            # Extract key outputs for YAML
            outputs = []
            outputs.append(
                {"variable": "income_tax", "value": float(result_row.get("fiitax", 0))}
            )
            outputs.append(
                {
                    "variable": "state_income_tax",
                    "value": float(result_row.get("siitax", 0)),
                }
            )

            # Generate YAML file
            yaml_filename = f"taxsim_record_{int(row['taxsimid'])}_{year}.yaml"
            generate_pe_tests_yaml(household, outputs, yaml_filename, logs=True)

        except Exception as e:
            print(f"Warning: Could not generate YAML for record {idx}: {e}")


@click.group()
def cli():
    """PolicyEngine-TAXSIM comparison and calculation tool"""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="output.txt",
    help="Output file path",
)
@click.option("--logs", is_flag=True, help="Generate PE YAML Tests Logs")
@click.option(
    "--disable-salt", is_flag=True, default=False, help="Set SALT Deduction to 0"
)
@click.option("--sample", type=int, help="Sample N records from input")
def policyengine(input_file, output, logs, disable_salt, sample):
    """
    Process TAXSIM input file and generate PolicyEngine-compatible output.
    """
    try:
        # Read input file
        df = pd.read_csv(input_file)

        # Apply sampling if requested
        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        # Use the PolicyEngineRunner with microsimulation
        runner = PolicyEngineRunner(df, logs=logs, disable_salt=disable_salt)
        results_df = runner.run(show_progress=True)

        # Generate YAML files if requested
        if logs:
            click.echo("Generating PolicyEngine YAML test files...")
            _generate_yaml_files(df, results_df)
            click.echo(f"Generated {len(df)} YAML test files")

        # Save results to output file
        results_df.to_csv(output, index=False)
        click.echo(f"Results saved to {output}")

    except Exception as e:
        click.echo(f"Error processing input: {str(e)}", err=True)
        raise


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="taxsim_output.csv", help="Output file path")
@click.option("--sample", type=int, help="Sample N records from input")
@click.option(
    "--taxsim-path",
    type=click.Path(exists=True),
    help="Custom path to TAXSIM executable",
)
def taxsim(input_file, output, sample, taxsim_path):
    """Run TAXSIM-35 tax calculations"""
    try:
        # Load and optionally sample data
        df = pd.read_csv(input_file)

        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        # Run TAXSIM
        runner = TaxsimRunner(df, taxsim_path=taxsim_path)
        results = runner.run()

        # Save results
        results.to_csv(output, index=False)
        click.echo(f"TAXSIM results saved to: {output}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--sample", type=int, help="Sample N records from input")
@click.option(
    "--output-dir",
    default="comparison_output",
    help="Directory to save comparison results",
)
@click.option("--year", type=int, help="Tax year for output file naming")
@click.option(
    "--disable-salt",
    is_flag=True,
    default=False,
    help="Disable SALT deduction in PolicyEngine",
)
@click.option("--logs", is_flag=True, help="Generate PolicyEngine YAML logs")
def compare(input_file, sample, output_dir, year, disable_salt, logs):
    """Compare PolicyEngine and TAXSIM results"""
    try:
        # Load and optionally sample data
        df = pd.read_csv(input_file)

        # Override year column if specified
        if year is not None and "year" in df.columns:
            original_year = df["year"].iloc[0] if len(df) > 0 else "unknown"
            df["year"] = year
            click.echo(
                f"Overriding year from {original_year} to {year} for all records"
            )
        elif year is None and "year" in df.columns:
            # Use year from the data
            year = int(df["year"].iloc[0]) if len(df) > 0 else 2021
            click.echo(f"Using year {year} from input data")
        elif year is None:
            # Default year if no year column exists
            year = 2021
            df["year"] = year
            click.echo(f"No year specified or found in data, defaulting to {year}")

        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        click.echo(f"Processing {len(df)} records for comparison")

        # Run PolicyEngine
        click.echo("Running PolicyEngine...")
        pe_runner = PolicyEngineRunner(df, logs=logs, disable_salt=disable_salt)
        pe_results = pe_runner.run()
        
        # Generate YAML files if requested  
        if logs:
            click.echo("Generating PolicyEngine YAML test files...")
            _generate_yaml_files(df, pe_results)
            click.echo(f"Generated {len(df)} YAML test files")

        # Run TAXSIM
        click.echo("Running TAXSIM...")
        taxsim_runner = TaxsimRunner(df)
        taxsim_results = taxsim_runner.run()

        # Compare results
        click.echo("Comparing results...")
        config = ComparisonConfig(federal_tolerance=15.0, state_tolerance=15.0)

        comparator = TaxComparator(taxsim_results, pe_results, config)
        comparison_results = comparator.compare()

        # Generate statistics
        stats = ComparisonStatistics(comparison_results, df)
        stats.print_summary()

        # Save outputs
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Save consolidated results (includes all matches and mismatches)
        comparison_results.save_consolidated_results(output_path, df, year)

        click.echo(f"\nComparison results saved to: {output_path}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--sample", type=int, help="Sample N records and save to new file")
@click.option(
    "--output",
    "-o",
    help="Output file for sampled data (auto-generated if not specified)",
)
def sample_data(input_file, sample, output):
    """Sample records from a large dataset"""
    try:
        df = pd.read_csv(input_file)

        if not sample:
            click.echo(
                f"File contains {len(df)} records. Use --sample N to extract N records."
            )
            return

        if sample >= len(df):
            click.echo(f"Sample size ({sample}) is larger than file size ({len(df)})")
            return

        # Sample data
        sampled_df = df.sample(n=sample, random_state=42)

        # Generate output filename if not provided
        if not output:
            input_path = Path(input_file)
            output = (
                input_path.parent
                / f"{input_path.stem}_sample_{sample}{input_path.suffix}"
            )

        # Save sampled data
        sampled_df.to_csv(output, index=False)
        click.echo(f"Sampled {sample} records from {len(df)} total records")
        click.echo(f"Sampled data saved to: {output}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


def to_csv_str(results):
    if len(results) == 0 or results is None:
        return ""

    df = pd.DataFrame(results)
    content = df.to_csv(index=False, float_format="%.1f", lineterminator="\n")
    cleaned_df = pd.read_csv(StringIO(content))
    return cleaned_df.to_csv(index=False, lineterminator="\n")


if __name__ == "__main__":
    cli()
