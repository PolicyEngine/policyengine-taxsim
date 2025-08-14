import click
import pandas as pd
from pathlib import Path
from io import StringIO

try:
    from .runners.policyengine_runner import PolicyEngineRunner
    from .runners.taxsim_runner import TaxsimRunner
    from .comparison.comparator import TaxComparator, ComparisonConfig
    from .comparison.statistics import ComparisonStatistics
except ImportError:
    from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner
    from policyengine_taxsim.comparison.comparator import (
        TaxComparator,
        ComparisonConfig,
    )
    from policyengine_taxsim.comparison.statistics import ComparisonStatistics


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

        # Use the new PolicyEngineRunner but keep original output format
        runner = PolicyEngineRunner(df, logs=logs, disable_salt=disable_salt)
        runner.run_original_format()  # This preserves the exact original behavior

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
@click.option("--save-mismatches", is_flag=True, help="Save detailed mismatch files")
@click.option("--year", type=int, help="Tax year for output file naming")
@click.option(
    "--disable-salt",
    is_flag=True,
    default=False,
    help="Disable SALT deduction in PolicyEngine",
)
@click.option("--logs", is_flag=True, help="Generate PolicyEngine YAML logs")
def compare(input_file, sample, output_dir, save_mismatches, year, disable_salt, logs):
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

        # Save raw results
        year_suffix = f"_{year}" if year else ""
        pe_results.to_csv(
            output_path / f"policyengine_results{year_suffix}.csv", index=False
        )
        taxsim_results.to_csv(
            output_path / f"taxsim_results{year_suffix}.csv", index=False
        )

        # Save detailed report
        with open(output_path / f"comparison_report{year_suffix}.txt", "w") as f:
            f.write(stats.detailed_report())

        # Save mismatches if requested
        if save_mismatches:
            comparison_results.save_mismatches(output_path, df, year)

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
