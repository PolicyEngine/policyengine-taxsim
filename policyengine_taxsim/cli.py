import codecs
import hashlib
import logging
import os
import sys
import tempfile

import click
import pandas as pd
from pathlib import Path
from io import StringIO

# Suppress benign Hugging Face Hub warnings (e.g., "unauthenticated requests"
# rate-limit notices) — downloads still succeed under the anonymous limit,
# and the message confuses TAXSIM users who don't have an HF account.
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

try:
    from .runners.policyengine_runner import PolicyEngineRunner
    from .runners.taxsim_runner import TaxsimRunner
    from .runners.stitched_runner import StitchedRunner
    from .comparison.comparator import TaxComparator, ComparisonConfig
    from .comparison.statistics import ComparisonStatistics
    from .core.yaml_generator import generate_pe_tests_yaml
    from .core.input_mapper import form_household_situation
    from .core.utils import get_calculation_state_code, convert_taxsim32_dependents
    from .core.io import read_input, write_output
    from .core.scorp import validate_scorp_treatment
    from .core import provenance as prov
except ImportError:
    from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner
    from policyengine_taxsim.runners.stitched_runner import StitchedRunner
    from policyengine_taxsim.comparison.comparator import (
        TaxComparator,
        ComparisonConfig,
    )
    from policyengine_taxsim.comparison.statistics import ComparisonStatistics
    from policyengine_taxsim.core.yaml_generator import generate_pe_tests_yaml
    from policyengine_taxsim.core.input_mapper import form_household_situation
    from policyengine_taxsim.core.utils import (
        get_calculation_state_code,
        convert_taxsim32_dependents,
    )
    from policyengine_taxsim.core.io import read_input, write_output
    from policyengine_taxsim.core.scorp import validate_scorp_treatment
    from policyengine_taxsim.core import provenance as prov


def _scorp_option(fn):
    return click.option(
        "--scorp-treatment",
        type=click.Choice(["passive", "active"]),
        default=None,
        help=(
            "S-corp NIIT classification in PolicyEngine (default: passive with "
            "policyengine-us 2.10.1+, otherwise active). Does not change TAXSIM "
            "or QBI eligibility."
        ),
    )(fn)


def _resolve_scorp_treatment(value):
    ctx = click.get_current_context()
    return (
        value
        or (ctx.parent.params.get("scorp_treatment") if ctx.parent else None)
        or validate_scorp_treatment(None)
    )


def _print_versions(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(prov.format_version_report(prov.collect_versions()))
    ctx.exit()


def _check_provenance_path(ctx, param, value):
    # Fail before a long run, not after it, when the sidecar can't be written.
    if value is None or ctx.resilient_parsing:  # not set, or shell completion
        return value
    if not value.strip():
        raise click.BadParameter("give a file path for the provenance JSON")
    try:
        directory = Path(value).resolve().parent
    except (OSError, RuntimeError) as e:  # e.g. a symlink loop
        raise click.BadParameter(f"cannot resolve {value}: {e}")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory):
            pass
    except OSError as e:
        raise click.BadParameter(f"cannot write to {directory}: {e.strerror or e}")
    return value


def _provenance_option(fn):
    return click.option(
        "--provenance",
        type=click.Path(dir_okay=False, writable=True),
        default=None,
        callback=_check_provenance_path,
        help=(
            "Also write a JSON file recording the policyengine-taxsim, "
            "policyengine-us and policyengine-core versions, the TAXSIM "
            "binary build, the options and SHA-256 hashes of the input and "
            "output. The TAXSIM output itself is unchanged."
        ),
    )(fn)


def _resolve_provenance(value):
    ctx = click.get_current_context()
    return value or (ctx.parent.params.get("provenance") if ctx.parent else None)


def _same_file(a, b):
    """Whether two paths name one file, through symlinks, hard links or a
    case-insensitive filesystem when both exist."""
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(
        os.path.realpath(b)
    )


def _stream_is_file(stream, path):
    """Whether a standard stream reads from or writes to ``path``."""
    try:
        return os.path.samestat(os.fstat(stream.fileno()), os.stat(path))
    except (AttributeError, OSError, ValueError):  # no file behind it
        return False


def _refuse_data_file_as_sidecar(provenance, *paths):
    """The sidecar must never replace the run's input or output."""
    for path in paths:
        if path is not None and _same_file(provenance, path):
            raise click.BadParameter(
                f"is the run's input or output file ({path})",
                param_hint="'--provenance'",
            )


def _record_provenance(
    path, input_info, output_info, engines, taxsim_path=None, data_files=()
):
    """Write the provenance sidecar for the current command's run, unless
    ``path`` turns out to be one of ``data_files``, the files the run wrote
    or read (e.g. a case-only alias of an output that did not exist before
    the run, or a --logs YAML file)."""
    _refuse_data_file_as_sidecar(path, *data_files)
    ctx = click.get_current_context()
    options = {k: v for k, v in ctx.params.items() if k != "provenance"}
    if "scorp_treatment" in options:
        options["scorp_treatment"] = _resolve_scorp_treatment(
            options["scorp_treatment"]
        )
    record = prov.build_provenance(
        ctx.command_path, options, input_info, output_info, engines, taxsim_path
    )
    prov.write_provenance(path, record)
    click.echo(f"Provenance saved to {path}", err=True)


def _file_info(path, records):
    return {
        "path": str(Path(path).absolute()),
        "sha256": prov.sha256_file(path),
        "records": records,
    }


def _read_stdin():
    """Return stdin as text, plus the raw bytes the provenance hash covers."""
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None:
        text = sys.stdin.read()
        return text, text.encode("utf-8")
    raw = stream.read()
    text = raw.decode(sys.stdin.encoding or "utf-8", sys.stdin.errors or "strict")
    return text, raw


class _HashingStdout:
    """Stand-in for sys.stdout that passes every write through and hashes
    the bytes the real stream writes for it: Python's text stdout turns "\n"
    into the platform line separator and encodes with its own encoding."""

    def __init__(self, stream):
        self.stream = stream
        self._digest = hashlib.sha256()
        # Incremental, like the stream's own encoder: a BOM-writing encoding
        # (utf-8-sig, utf-16) writes one BOM, not one per write.
        self._encoder = codecs.getincrementalencoder(stream.encoding or "utf-8")(
            stream.errors or "strict"
        )

    def write(self, text):
        self._digest.update(self._encoder.encode(text.replace("\n", os.linesep)))
        return self.stream.write(text)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def hexdigest(self):
        return self._digest.hexdigest()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _generate_yaml_files(
    input_df: pd.DataFrame, results_df: pd.DataFrame, scorp_treatment=None
):
    """Generate YAML test files for each record when logs=True. Returns the
    paths written."""
    # Index results by taxsimid for reliable lookup (positional iloc
    # breaks when StitchedRunner reorders rows from two engines).
    results_by_id = results_df.set_index("taxsimid")
    written = []

    for idx, row in input_df.iterrows():
        try:
            # Create household data for this record
            year = int(float(row["year"]))
            state = get_calculation_state_code(row["state"])

            # Convert taxsim data to proper types
            taxsim_data = row.to_dict()
            for key, value in taxsim_data.items():
                if isinstance(value, float) and value.is_integer():
                    taxsim_data[key] = int(value)

            # Convert TAXSIM32 dependent format if present
            taxsim_data = convert_taxsim32_dependents(taxsim_data)

            from policyengine_taxsim.core.scorp import classify_scorp

            household = classify_scorp(
                form_household_situation(year, state, taxsim_data), scorp_treatment
            )

            # Get results for this record by taxsimid
            result_row = results_by_id.loc[row["taxsimid"]]

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
            # Use taxsimid from row if available, otherwise use index + 1
            taxsim_id = int(row["taxsimid"]) if "taxsimid" in row else idx + 1
            yaml_filename = f"taxsim_record_{taxsim_id}_{year}.yaml"
            generate_pe_tests_yaml(household, outputs, yaml_filename, logs=True)
            written.append(yaml_filename)

        except Exception as e:
            print(
                f"Warning: Could not generate YAML for record {idx}: {e}",
                file=sys.stderr,
            )

    return written


def _emit_results(input_df, results_df, out_stream):
    """Write results to ``out_stream``. CSV by default; for any rows
    with ``idtl=5``, emit TAXSIM-35's labeled-section full-text instead.
    Mixed-idtl inputs interleave records in original input order."""
    try:
        from .core.text_formatter import format_row
    except ImportError:
        from policyengine_taxsim.core.text_formatter import format_row

    # Default: no idtl=5 anywhere → write CSV as before.
    if "idtl" not in input_df.columns or not (input_df["idtl"] == 5).any():
        results_df.to_csv(out_stream, index=False)
        return

    # idtl=5 path. Build a per-taxsimid lookup that keeps the original
    # results_df column order — avoid set_index here so the eventual
    # CSV emission preserves the default schema (`taxsimid,year,...`).
    result_columns = list(results_df.columns)
    results_rows = {
        row["taxsimid"]: row for row in results_df.to_dict(orient="records")
    }

    text_chunks = []
    csv_indices = []
    for _, in_row in input_df.iterrows():
        idtl = int(float(in_row.get("idtl", 0)))
        taxsimid = in_row["taxsimid"]
        result_dict = results_rows.get(taxsimid)
        if result_dict is None:
            continue
        if idtl == 5:
            text_chunks.append(format_row(in_row.to_dict(), result_dict))
        else:
            csv_indices.append(taxsimid)

    # Emit text rows first, then a single CSV block for the rest. Per-row
    # interleaving isn't useful because CSV needs a header — and each
    # record is identifiable by taxsimid in either format.
    for chunk in text_chunks:
        out_stream.write(chunk + "\n")

    if csv_indices:
        csv_df = results_df[results_df["taxsimid"].isin(csv_indices)][result_columns]
        csv_df.to_csv(out_stream, index=False)


@click.group(invoke_without_command=True)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_print_versions,
    help=(
        "Show the policyengine-taxsim, policyengine-us and policyengine-core "
        "versions and the bundled TAXSIM binary's build, then exit."
    ),
)
@click.option("--logs", is_flag=True, help="Generate PE YAML Tests Logs")
@click.option(
    "--disable-salt", is_flag=True, default=False, help="Set SALT Deduction to 0"
)
@click.option("--sample", type=int, help="Sample N records from input")
@_scorp_option
@_provenance_option
@click.pass_context
def cli(ctx, logs, disable_salt, sample, scorp_treatment, provenance):
    """PolicyEngine-TAXSIM: drop-in replacement for TAXSIM-35.

    Reads CSV from stdin and writes results to stdout, just like taxsim35:

        policyengine-taxsim < input.csv > output.csv

    Or use subcommands for additional features (compare, taxsim, sample-data).
    """
    if ctx.invoked_subcommand is not None:
        subcommand = ctx.command.get_command(ctx, ctx.invoked_subcommand)
        if provenance and "provenance" not in {p.name for p in subcommand.params}:
            raise click.UsageError(
                f"--provenance does not apply to {ctx.invoked_subcommand}"
            )
        # Store options for potential use by subcommands
        ctx.ensure_object(dict)
        ctx.obj["logs"] = logs
        ctx.obj["disable_salt"] = disable_salt
        ctx.obj["sample"] = sample
        return

    # Default behavior: read stdin, write stdout (like taxsim35)
    if sys.stdin.isatty():
        click.echo(ctx.get_help())
        return

    if provenance and (
        _stream_is_file(sys.stdout, provenance)
        or _stream_is_file(sys.stdin, provenance)
    ):
        raise click.BadParameter(
            "is the file stdin is read from or stdout is written to",
            param_hint="'--provenance'",
        )

    hashing_stdout = None
    try:
        if provenance:
            text, raw_input = _read_stdin()
            df = pd.read_csv(StringIO(text))
            # Hash every byte the run writes to stdout, whatever writes it.
            hashing_stdout = sys.stdout = _HashingStdout(sys.stdout)
        else:
            df = pd.read_csv(sys.stdin)
        df.columns = [c.strip() for c in df.columns]
        input_records = len(df)

        # Apply sampling if requested
        if sample and sample < len(df):
            click.echo(
                f"Sampling {sample} records from {len(df)} total records",
                err=True,
            )
            df = df.sample(n=sample, random_state=42)

        # Use StitchedRunner: routes to PE (2021+) or TAXSIM (pre-2021)
        scorp_treatment = _resolve_scorp_treatment(scorp_treatment)
        runner = StitchedRunner(
            df, logs=logs, disable_salt=disable_salt, scorp_treatment=scorp_treatment
        )
        results_df = runner.run(show_progress=True)

        # Use the runner's input_df which has taxsimid (auto-assigned if needed)
        df_with_ids = runner.input_df

        # Generate YAML files if requested
        yaml_files = []
        if logs:
            click.echo("Generating PolicyEngine YAML test files...", err=True)
            yaml_files = _generate_yaml_files(
                df_with_ids, results_df, _resolve_scorp_treatment(scorp_treatment)
            )
            click.echo(f"Generated {len(df_with_ids)} YAML test files", err=True)

        _emit_results(df_with_ids, results_df, sys.stdout)

        if provenance:
            sys.stdout.flush()
            _record_provenance(
                provenance,
                {
                    "path": "<stdin>",
                    "sha256": prov.sha256_bytes(raw_input),
                    "records": input_records,
                },
                {
                    "path": "<stdout>",
                    "sha256": hashing_stdout.hexdigest(),
                    "records": len(results_df),
                },
                runner.engine_counts(),
                data_files=yaml_files,
            )

    except Exception as e:
        click.echo(f"Error processing input: {str(e)}", err=True)
        raise
    finally:
        if hashing_stdout is not None:
            sys.stdout = hashing_stdout.stream


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
@click.option(
    "--assume-w2-wages",
    is_flag=True,
    default=False,
    help="Assume large W-2 wages for QBID (aligns with TAXSIM S-Corp handling)",
)
@click.option("--sample", type=int, help="Sample N records from input")
@_scorp_option
@_provenance_option
def policyengine(
    input_file,
    output,
    logs,
    disable_salt,
    assume_w2_wages,
    sample,
    scorp_treatment,
    provenance,
):
    """
    Process TAXSIM input file and generate PolicyEngine-compatible output.

    This is the file-based interface. For stdin/stdout like taxsim35, omit the
    subcommand: policyengine-taxsim < input.csv > output.csv
    """
    provenance = _resolve_provenance(provenance)
    if provenance:
        _refuse_data_file_as_sidecar(provenance, input_file, output)
    try:
        # Read input file
        df = read_input(input_file)
        # Hash the input as read: an -o naming the input overwrites it.
        input_info = _file_info(input_file, len(df)) if provenance else None

        # Apply sampling if requested
        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        # Use StitchedRunner: routes to PE (2021+) or TAXSIM (pre-2021)
        runner = StitchedRunner(
            df,
            logs=logs,
            disable_salt=disable_salt,
            assume_w2_wages=assume_w2_wages,
            scorp_treatment=_resolve_scorp_treatment(scorp_treatment),
        )
        results_df = runner.run(show_progress=True)

        # Use the runner's input_df which has taxsimid (auto-assigned if needed)
        df_with_ids = runner.input_df

        # Generate YAML files if requested
        yaml_files = []
        if logs:
            click.echo("Generating PolicyEngine YAML test files...", err=True)
            yaml_files = _generate_yaml_files(
                df_with_ids, results_df, _resolve_scorp_treatment(scorp_treatment)
            )
            click.echo(f"Generated {len(df_with_ids)} YAML test files", err=True)

        # Save results to output file
        write_output(results_df, output)
        click.echo(f"Results saved to {output}", err=True)

        if provenance:
            _record_provenance(
                provenance,
                input_info,
                _file_info(output, len(results_df)),
                runner.engine_counts(),
                data_files=(input_file, output, *yaml_files),
            )

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
@_provenance_option
def taxsim(input_file, output, sample, taxsim_path, provenance):
    """Run TAXSIM-35 tax calculations"""
    provenance = _resolve_provenance(provenance)
    if provenance:
        _refuse_data_file_as_sidecar(provenance, input_file, output)
    try:
        # Load and optionally sample data
        df = read_input(input_file)
        # Hash the input as read: an -o naming the input overwrites it.
        input_info = _file_info(input_file, len(df)) if provenance else None

        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        # Run TAXSIM
        runner = TaxsimRunner(df, taxsim_path=taxsim_path)
        results = runner.run()

        # Save results
        write_output(results, output)
        click.echo(f"TAXSIM results saved to: {output}")

        if provenance:
            _record_provenance(
                provenance,
                input_info,
                _file_info(output, len(results)),
                {"policyengine": 0, "taxsim": len(df)},
                taxsim_path=runner.taxsim_path,
                data_files=(input_file, output),
            )

    except click.ClickException:
        raise
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
@click.option(
    "--assume-w2-wages",
    is_flag=True,
    default=False,
    help="Assume large W-2 wages for QBID (aligns with TAXSIM S-Corp handling)",
)
@click.option(
    "--rel-tolerance",
    type=float,
    default=0.0,
    help=(
        "Income-scaled match tolerance as a fraction of |AGI| (e.g. 0.001 = "
        "0.1%). A record matches if the tax difference is within "
        "max($15, rel-tolerance * |AGI|), avoiding false mismatches on "
        "extreme-magnitude records (e.g. large S-corp income/losses). "
        "Default 0 uses the flat $15 absolute tolerance."
    ),
)
@click.option(
    "--net-of-rebates",
    is_flag=True,
    default=False,
    help=(
        "Score state tax net of one-time rebates: compare siitax + srebate "
        "on both sides. Removes the timing-convention difference between "
        "TAXSIM (rebates in the payout year) and PolicyEngine (rebates in "
        "the liability year) without changing either engine. Federal "
        "comparison is unaffected."
    ),
)
@click.option(
    "--taxsim-opt30",
    is_flag=True,
    default=False,
    help=(
        "Run the TAXSIM binary in its PSL-conformance test mode by setting "
        "global option 30=1 (which sets opt 27/88/91: rebates booked in the "
        "eligible year like PolicyEngine, no smoothing, no federal-state "
        "iteration, plus per-state concessions such as the MI heating "
        "credit). This is the mode NBER uses when testing PolicyEngine "
        "records; without it the binary runs in default production mode. "
        "See https://taxsim.nber.org/taxsimtest/options.html"
    ),
)
@_scorp_option
@_provenance_option
def compare(
    input_file,
    sample,
    output_dir,
    year,
    disable_salt,
    logs,
    assume_w2_wages,
    rel_tolerance,
    net_of_rebates,
    taxsim_opt30,
    scorp_treatment,
    provenance,
):
    """Compare PolicyEngine and TAXSIM results"""
    provenance = _resolve_provenance(provenance)
    if provenance:
        _refuse_data_file_as_sidecar(provenance, input_file)
    try:
        # Load and optionally sample data
        df = read_input(input_file)
        input_info = _file_info(input_file, len(df)) if provenance else None

        # Override year column if specified
        if year is not None and "year" in df.columns:
            original_year = df["year"].iloc[0] if len(df) > 0 else "unknown"
            df["year"] = year
            click.echo(
                f"Overriding year from {original_year} to {year} for all records"
            )
        elif year is None and "year" in df.columns:
            # Use year from the data
            year = int(float(df["year"].iloc[0])) if len(df) > 0 else 2021
            click.echo(f"Using year {year} from input data")
        elif year is None:
            # Default year if no year column exists
            year = 2021
            df["year"] = year
            click.echo(f"No year specified or found in data, defaulting to {year}")

        # The consolidated results file is named after the year.
        consolidated = Path(output_dir) / f"comparison_results_{year}.csv"
        if provenance:
            _refuse_data_file_as_sidecar(provenance, consolidated)

        if sample and sample < len(df):
            click.echo(f"Sampling {sample} records from {len(df)} total records")
            df = df.sample(n=sample, random_state=42)

        click.echo(f"Processing {len(df)} records for comparison")

        # Run PolicyEngine
        click.echo("Running PolicyEngine...")
        pe_runner = PolicyEngineRunner(
            df,
            logs=logs,
            disable_salt=disable_salt,
            assume_w2_wages=assume_w2_wages,
            scorp_treatment=_resolve_scorp_treatment(scorp_treatment),
        )
        pe_results = pe_runner.run()

        # Use the runner's input_df which has taxsimid (auto-assigned if needed)
        df_with_ids = pe_runner.input_df

        # Generate YAML files if requested
        yaml_files = []
        if logs:
            click.echo("Generating PolicyEngine YAML test files...")
            yaml_files = _generate_yaml_files(
                df_with_ids, pe_results, _resolve_scorp_treatment(scorp_treatment)
            )
            click.echo(f"Generated {len(df_with_ids)} YAML test files")

        # Run TAXSIM with original input (not PE-modified df which adds
        # defaults like sage=40 for single filers that TAXSIM rejects).
        # Sync taxsimid from PE runner in case it was auto-assigned.
        click.echo("Running TAXSIM...")
        taxsim_input = df.copy()
        taxsim_input["taxsimid"] = df_with_ids["taxsimid"].values
        if taxsim_opt30:
            # TAXSIM options are global: setting opt(30)=1 on the records
            # switches the whole run into PSL-conformance mode. Only add the
            # columns when the input doesn't already carry option columns.
            if "opt1" not in taxsim_input.columns:
                taxsim_input["opt1"] = 30
                taxsim_input["opt1v"] = 1
            click.echo("Running TAXSIM with opt(30)=1 (PSL-conformance test mode)")
        taxsim_runner = TaxsimRunner(taxsim_input)
        taxsim_results = taxsim_runner.run()

        # Compare results
        click.echo("Comparing results...")
        config = ComparisonConfig(
            federal_tolerance=15.0,
            state_tolerance=15.0,
            relative_tolerance=rel_tolerance,
            net_of_rebates=net_of_rebates,
        )
        if rel_tolerance > 0:
            click.echo(
                f"Using income-scaled tolerance: max($15, {rel_tolerance:.3%} of |AGI|)"
            )
        if net_of_rebates:
            click.echo(
                "Scoring state tax net of one-time rebates (siitax + srebate "
                "on both sides)"
            )

        comparator = TaxComparator(taxsim_results, pe_results, config)
        comparison_results = comparator.compare()

        # Generate statistics
        stats = ComparisonStatistics(comparison_results, df_with_ids)
        stats.print_summary()

        # Save outputs
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Save consolidated results (includes all matches and mismatches)
        comparison_results.save_consolidated_results(output_path, df_with_ids, year)

        click.echo(f"\nComparison results saved to: {output_path}")

        if provenance:
            # Two rows per household (TAXSIM and PolicyEngine).
            _record_provenance(
                provenance,
                input_info,
                _file_info(consolidated, len(pd.read_csv(consolidated))),
                {"policyengine": len(df), "taxsim": len(df)},
                taxsim_path=taxsim_runner.taxsim_path,
                data_files=(input_file, consolidated, *yaml_files),
            )

    except click.ClickException:
        raise
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
        df = read_input(input_file)

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
        write_output(sampled_df, output)
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
