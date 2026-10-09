"""Tests for ``--version`` and the ``--provenance`` sidecar.

Federal statistical users asked how to reproduce a run, and PyPI does not
keep every policyengine-us release, so a run has to record its versions when
it runs. Invariants tested here:

- ``--provenance`` never changes what a run writes to stdout or its output
  file (byte-identical with and without the flag).
- The sidecar's input and output SHA-256 equal the hashes of the bytes the
  run read and wrote.
- Records add up: per-engine counts sum to the records written.
- ``--version`` and the sidecar report the same versions.
- The build stamp read from a TAXSIM binary without running it equals the
  build that binary prints in its output header when it runs.
"""

import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from click.testing import CliRunner
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import policyengine_taxsim
from policyengine_taxsim.cli import cli
from policyengine_taxsim.core import provenance as prov
from policyengine_taxsim.runners.stitched_runner import StitchedRunner
from policyengine_taxsim.runners.taxsim_runner import (
    TaxsimRunner,
    default_taxsim_executable,
)

# The package re-exports the ``cli`` group, which shadows the module name.
CLI_MODULE = importlib.import_module("policyengine_taxsim.cli")
REPO = Path(__file__).resolve().parent.parent
TAXSIMTEST_BINARIES = sorted((REPO / "resources" / "taxsimtest").glob("*.exe"))
HEADER = "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl"
PRE_2021_RECORD = "1,2019,5,1,40,0,0,50000,2"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def csv_bytes(rows, newline="\n"):
    return newline.join([HEADER, *rows, ""]).encode()


def version_lines(text):
    return {
        label.strip(): value.strip()
        for label, value in (line.split(":", 1) for line in text.splitlines())
    }


class FakeStitchedRunner(StitchedRunner):
    """StitchedRunner with real routing and input handling but a cheap,
    deterministic stand-in for the tax engines."""

    def run(self, show_progress=True, on_progress=None):
        df = self.input_df
        return pd.DataFrame(
            {
                "taxsimid": df["taxsimid"],
                "year": df["year"],
                "state": df["state"],
                "fiitax": df["pwages"] * 0.1,
                "siitax": df["pwages"] * 0.03,
            }
        )


@pytest.fixture
def fake_runner(monkeypatch):
    monkeypatch.setattr(CLI_MODULE, "StitchedRunner", FakeStitchedRunner)


# --version ---------------------------------------------------------------


def test_version_reports_emulator_model_and_taxsim_build():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0, result.output
    lines = version_lines(result.stdout)
    assert lines["policyengine-taxsim"] == policyengine_taxsim.__version__
    assert lines["policyengine-us"] == importlib.metadata.version("policyengine-us")
    assert lines["policyengine-core"] == importlib.metadata.version("policyengine-core")
    binary = default_taxsim_executable()
    build = prov.read_binary_build(binary)
    assert re.fullmatch(r"cd\d{10}", build), build
    assert lines["TAXSIM binary"] == f"{build} ({binary.name})"
    assert lines["Python"] == platform.python_version()


def test_version_exits_before_reading_stdin():
    result = CliRunner().invoke(cli, ["--version"], input="not,a\ntaxsim,file\n")
    assert result.exit_code == 0
    assert "policyengine-taxsim:" in result.stdout
    assert "Error" not in result.output


def test_version_matches_sidecar(tmp_path, fake_runner):
    sidecar = tmp_path / "run.json"
    version = CliRunner().invoke(cli, ["--version"])
    run = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=csv_bytes([PRE_2021_RECORD])
    )
    assert run.exit_code == 0, run.output
    record = json.loads(sidecar.read_text())
    assert version.stdout.strip() == prov.format_version_report(record)


def test_help_lists_new_options():
    result = CliRunner().invoke(cli, ["--help"])
    assert "--version" in result.output
    assert "--provenance" in result.output
    for command in ["policyengine", "taxsim", "compare"]:
        sub = CliRunner().invoke(cli, [command, "--help"])
        assert "--provenance" in sub.output, command


def test_version_report_when_binary_missing(tmp_path):
    versions = prov.collect_versions(tmp_path / "taxsimtest-none.exe")
    assert versions["taxsimBinaryPath"] is None
    assert versions["taxsimBinaryBuild"] is None
    assert versions["taxsimBinarySha256"] is None
    report = version_lines(prov.format_version_report(versions))
    assert report["TAXSIM binary"] == "not found or unreadable (taxsimtest-none.exe)"


# Build stamps --------------------------------------------------------------


@pytest.mark.parametrize("binary", TAXSIMTEST_BINARIES, ids=lambda p: p.name)
def test_every_bundled_binary_has_one_build_stamp(binary):
    assert re.fullmatch(r"cd\d{10}", prov.read_binary_build(binary) or "")


def test_reads_pre_2026_cdate_stamp():
    # The bundled taxsim35 macOS build predates the cdYYYYMMDDHH format.
    binary = REPO / "resources" / "taxsim35" / "taxsim35-osx.exe"
    assert prov.read_binary_build(binary) == "2025Aug23"


def test_static_build_matches_build_the_binary_prints():
    """Differential: the stamp read from the file equals the one this
    platform's binary writes into its output header when it runs."""
    df = pd.read_csv(io.StringIO(f"{HEADER}\n{PRE_2021_RECORD}\n"))
    runner = TaxsimRunner(df)
    runner.run(show_progress=False)
    assert runner.binary_build_date == prov.read_binary_build(runner.taxsim_path)


@given(st.text(alphabet="0123456789", min_size=10, max_size=10))
def test_parse_new_style_stamp(digits):
    assert prov.parse_build_stamp(f"cd{digits}") == f"cd{digits}"


@given(st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1))
def test_parse_cdate_stamp(date):
    assert prov.parse_build_stamp(f"cdate-{date}") == date


@given(st.text())
def test_parse_rejects_other_header_columns(token):
    assume(not token.startswith("cdate-"))
    assume(not re.fullmatch(r"cd\d{10}", token))
    assert prov.parse_build_stamp(token) is None


# No deadline: each example writes a file, which can stall on a busy runner.
@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    prefix=st.binary(max_size=200),
    suffix=st.binary(max_size=200),
    digits=st.text(alphabet="0123456789", min_size=10, max_size=10),
    copies=st.integers(min_value=1, max_value=3),
)
def test_read_binary_build_finds_embedded_stamp(
    tmp_path, prefix, suffix, digits, copies
):
    stamp = f"cd{digits}"
    blob = prefix + (f'"{stamp}"'.encode() + b"\x00") * copies + suffix
    assume(
        {m.group(1) for m in prov._EMBEDDED_BUILD.finditer(blob)} == {stamp.encode()}
    )
    path = tmp_path / "taxsim.exe"
    path.write_bytes(blob)
    assert prov.read_binary_build(path) == stamp


def test_read_binary_build_without_one_stamp(tmp_path):
    path = tmp_path / "taxsim.exe"
    path.write_bytes(b'\x00"cd2026081819"\x00"cd2026081318"\x00')
    assert prov.read_binary_build(path) is None  # ambiguous
    path.write_bytes(b"\x00cd2026081819\x00")
    assert prov.read_binary_build(path) is None  # not a string literal
    path.write_bytes(b"no stamp here")
    assert prov.read_binary_build(path) is None
    assert prov.read_binary_build(tmp_path / "missing.exe") is None


# --provenance on the stdin drop-in command --------------------------------

records = st.lists(
    st.tuples(
        st.integers(min_value=2015, max_value=2025),  # year (both engines)
        st.integers(min_value=1, max_value=51),  # state
        st.integers(min_value=0, max_value=500_000),  # pwages
    ),
    min_size=1,
    max_size=8,
)


@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(rows=records, newline=st.sampled_from(["\n", "\r\n"]))
def test_provenance_leaves_stdout_unchanged(tmp_path, fake_runner, rows, newline):
    input_bytes = csv_bytes(
        [
            f"{i},{year},{state},1,40,0,0,{wages},2"
            for i, (year, state, wages) in enumerate(rows, start=1)
        ],
        newline,
    )
    sidecar = tmp_path / "run.json"
    plain = CliRunner().invoke(cli, [], input=input_bytes)
    recorded = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=input_bytes
    )
    assert plain.exit_code == 0, plain.output
    assert recorded.exit_code == 0, recorded.output
    assert recorded.stdout_bytes == plain.stdout_bytes

    record = json.loads(sidecar.read_text())
    assert record["input"] == {
        "path": "<stdin>",
        "sha256": sha256(input_bytes),
        "records": len(rows),
    }
    assert record["output"] == {
        "path": "<stdout>",
        "sha256": sha256(recorded.stdout_bytes),
        "records": len(rows),
    }
    pre_2021 = sum(year < 2021 for year, _, _ in rows)
    assert record["engines"] == {
        "policyengine": len(rows) - pre_2021,
        "taxsim": pre_2021,
    }


def test_sidecar_contents(tmp_path, fake_runner):
    sidecar = tmp_path / "run.json"
    result = CliRunner().invoke(
        cli,
        ["--disable-salt", "--provenance", str(sidecar)],
        input=csv_bytes([PRE_2021_RECORD]),
    )
    assert result.exit_code == 0, result.output
    record = json.loads(sidecar.read_text())
    assert record["schemaVersion"] == prov.PROVENANCE_SCHEMA_VERSION
    assert record["policyengineTaxsimVersion"] == policyengine_taxsim.__version__
    assert record["policyengineUsVersion"] == importlib.metadata.version(
        "policyengine-us"
    )
    assert record["policyengineCoreVersion"] == importlib.metadata.version(
        "policyengine-core"
    )
    binary = default_taxsim_executable()
    assert record["taxsimBinary"] == binary.name
    assert record["taxsimBinaryPath"] == str(binary.resolve())
    assert record["taxsimBinarySha256"] == sha256(binary.read_bytes())
    assert record["taxsimBinaryBuild"] == prov.read_binary_build(binary)
    assert record["pythonVersion"] == platform.python_version()
    assert record["options"]["disable_salt"] is True
    assert record["options"]["scorp_treatment"] in {"active", "passive"}
    assert "provenance" not in record["options"]
    assert (
        record["installedPackages"]["policyengine-us"]
        == record["policyengineUsVersion"]
    )
    assert "Provenance saved to" in result.stderr
    assert "Provenance saved to" not in result.stdout


def test_sidecar_is_deterministic_apart_from_timestamp(tmp_path, fake_runner):
    sidecars = []
    for name in ["a.json", "b.json"]:
        path = tmp_path / name
        CliRunner().invoke(
            cli, ["--provenance", str(path)], input=csv_bytes([PRE_2021_RECORD])
        )
        record = json.loads(path.read_text())
        record.pop("generatedAt")
        sidecars.append(record)
    assert sidecars[0] == sidecars[1]


def test_sidecar_directory_is_created(tmp_path, fake_runner):
    sidecar = tmp_path / "runs" / "2026-10-08" / "run.json"
    result = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=csv_bytes([PRE_2021_RECORD])
    )
    assert result.exit_code == 0, result.output
    assert json.loads(sidecar.read_text())["output"]["records"] == 1


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
    reason="needs POSIX directory permissions enforced for this user",
)
def test_unwritable_sidecar_directory_fails_before_running(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the run should not start")

    monkeypatch.setattr(CLI_MODULE, "StitchedRunner", fail)
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        result = CliRunner().invoke(
            cli,
            ["--provenance", str(locked / "run.json")],
            input=csv_bytes([PRE_2021_RECORD]),
        )
    finally:
        locked.chmod(0o755)
    assert result.exit_code == 2, result.output
    assert "cannot write to" in result.output
    assert result.stdout == ""


def test_hash_covers_everything_written_to_stdout(tmp_path, monkeypatch):
    """The output hash covers stray writes to stdout during the run too, so
    it always equals the bytes a redirect would capture."""

    class NoisyRunner(FakeStitchedRunner):
        def run(self, show_progress=True, on_progress=None):
            print("stray line from an engine")
            sys.stdout.writelines(["two\n", "more\n"])
            return super().run(show_progress, on_progress)

    monkeypatch.setattr(CLI_MODULE, "StitchedRunner", NoisyRunner)
    sidecar = tmp_path / "run.json"
    result = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=csv_bytes([PRE_2021_RECORD])
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("stray line from an engine")
    record = json.loads(sidecar.read_text())
    assert record["output"]["sha256"] == sha256(result.stdout_bytes)


def test_logs_warnings_stay_off_stdout(tmp_path):
    """--logs diagnostics go to stderr: with a reused taxsimid the YAML step
    warns, and stdout still holds only the CSV (real TAXSIM binary)."""
    sidecar = tmp_path / "run.json"
    result = CliRunner().invoke(
        cli,
        ["--logs", "--provenance", str(sidecar)],
        input=csv_bytes([PRE_2021_RECORD, "1,2018,5,1,40,0,0,60000,2"]),
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("taxsimid,"), result.stdout
    assert "Could not generate YAML" in result.stderr
    assert json.loads(sidecar.read_text())["output"]["sha256"] == sha256(
        result.stdout_bytes
    )


def test_sidecar_path_must_not_be_empty(fake_runner):
    result = CliRunner().invoke(
        cli, ["--provenance", ""], input=csv_bytes([PRE_2021_RECORD])
    )
    assert result.exit_code == 2
    assert "give a file path" in result.output


def test_shell_completion_does_not_create_directories(tmp_path):
    target = tmp_path / "completion" / "run.json"
    ctx = SimpleNamespace(resilient_parsing=True)
    assert CLI_MODULE._check_provenance_path(ctx, None, str(target)) == str(target)
    assert not target.parent.exists()


def test_sample_data_rejects_group_provenance(tmp_path):
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD]))
    result = CliRunner().invoke(
        cli,
        ["--provenance", str(tmp_path / "run.json"), "sample-data", str(input_file)],
    )
    assert result.exit_code == 2
    assert "does not apply to sample-data" in result.output


@settings(max_examples=50, deadline=None)
@given(
    chunks=st.lists(st.text(max_size=30), max_size=8),
    encoding=st.sampled_from(["utf-8", "utf-8-sig", "utf-16", "latin-1"]),
)
def test_hashing_stdout_matches_bytes_written(chunks, encoding):
    """Differential: the digest equals the SHA-256 of what a real text stream
    (newline translation and an incremental, BOM-aware encoder) writes."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=encoding, errors="replace")
    tee = CLI_MODULE._HashingStdout(stream)
    for chunk in chunks:
        tee.write(chunk)
    tee.writelines(["a\n", "b\n"])
    stream.flush()
    assert tee.hexdigest() == sha256(buffer.getvalue())


def test_unsupported_operating_system(tmp_path, fake_runner, monkeypatch):
    """No bundled binary for the OS: --version still reports the packages,
    and a --provenance run still succeeds."""
    monkeypatch.setattr(platform, "system", lambda: "FreeBSD")
    version = CliRunner().invoke(cli, ["--version"])
    assert version.exit_code == 0, version.output
    lines = version_lines(version.stdout)
    assert lines["TAXSIM binary"] == "none bundled for this operating system"
    assert lines["policyengine-taxsim"] == policyengine_taxsim.__version__
    sidecar = tmp_path / "run.json"
    run = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=csv_bytes(["1,2022,5,1,40,0,0,1,2"])
    )
    assert run.exit_code == 0, run.output
    record = json.loads(sidecar.read_text())
    assert record["taxsimBinary"] is None
    assert record["taxsimBinarySha256"] is None


def test_pre_2021_stdin_output_is_clean_csv(tmp_path):
    """TAXSIM's progress lines go to stderr, so stdout holds only the CSV
    (the real binary, no PolicyEngine run)."""
    sidecar = tmp_path / "run.json"
    result = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=csv_bytes([PRE_2021_RECORD])
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("taxsimid,"), result.stdout
    assert "TAXSIM completed successfully" in result.stderr
    record = json.loads(sidecar.read_text())
    assert record["output"]["sha256"] == sha256(result.stdout_bytes)
    assert record["engines"] == {"policyengine": 0, "taxsim": 1}


def test_end_to_end_both_engines(tmp_path):
    """Real PolicyEngine and TAXSIM run: --provenance leaves stdout
    byte-identical and records what ran."""
    input_bytes = csv_bytes(["1,2021,5,1,40,0,0,50000,2", "2,2019,5,1,40,0,0,50000,2"])
    sidecar = tmp_path / "run.json"
    plain = CliRunner().invoke(cli, [], input=input_bytes)
    recorded = CliRunner().invoke(
        cli, ["--provenance", str(sidecar)], input=input_bytes
    )
    assert plain.exit_code == 0, plain.output
    assert recorded.exit_code == 0, recorded.output
    assert recorded.stdout_bytes == plain.stdout_bytes
    record = json.loads(sidecar.read_text())
    assert record["engines"] == {"policyengine": 1, "taxsim": 1}
    assert record["output"]["sha256"] == sha256(recorded.stdout_bytes)
    assert record["output"]["records"] == 2


# --provenance on the subcommands ---------------------------------------------


@pytest.mark.parametrize("flag_first", [False, True], ids=["after", "before"])
def test_policyengine_subcommand(tmp_path, fake_runner, flag_first):
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD, "2,2022,5,1,40,0,0,1,2"]))
    plain_out, out, sidecar = (
        tmp_path / "plain.csv",
        tmp_path / "out.csv",
        tmp_path / "run.json",
    )
    CliRunner().invoke(cli, ["policyengine", str(input_file), "-o", str(plain_out)])
    flag = ["--provenance", str(sidecar)]
    command = ["policyengine", str(input_file), "-o", str(out)]
    result = CliRunner().invoke(cli, flag + command if flag_first else command + flag)
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == plain_out.read_bytes()
    record = json.loads(sidecar.read_text())
    assert record["input"] == {
        "path": str(input_file),
        "sha256": sha256(input_file.read_bytes()),
        "records": 2,
    }
    assert record["output"] == {
        "path": str(out),
        "sha256": sha256(out.read_bytes()),
        "records": 2,
    }
    assert record["engines"] == {"policyengine": 1, "taxsim": 1}
    assert record["command"].endswith("policyengine")
    assert record["options"]["output"] == str(out)


def test_taxsim_subcommand_records_binary_it_ran(tmp_path):
    """--taxsim-path runs a different file; the sidecar describes that file,
    not the default binary. The copy has trailing bytes appended, so its
    SHA-256 differs from the bundled one but it runs the same."""
    default = default_taxsim_executable()
    custom = tmp_path / "custom" / default.name
    custom.parent.mkdir()
    custom.write_bytes(default.read_bytes() + b"\0" * 16)
    custom.chmod(0o755)
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD]))
    out, default_out, sidecar = (
        tmp_path / "out.csv",
        tmp_path / "default.csv",
        tmp_path / "run.json",
    )
    result = CliRunner().invoke(
        cli,
        ["taxsim", str(input_file), "-o", str(out), "--taxsim-path", str(custom)]
        + ["--provenance", str(sidecar)],
    )
    assert result.exit_code == 0, result.output
    CliRunner().invoke(cli, ["taxsim", str(input_file), "-o", str(default_out)])
    assert out.read_bytes() == default_out.read_bytes()
    record = json.loads(sidecar.read_text())
    assert record["taxsimBinaryPath"] == str(custom.resolve())
    assert record["taxsimBinarySha256"] == sha256(custom.read_bytes())
    assert record["taxsimBinarySha256"] != sha256(default.read_bytes())
    assert record["taxsimBinaryBuild"] == prov.read_binary_build(default)
    assert record["options"]["taxsim_path"] == str(custom)
    assert record["output"]["sha256"] == sha256(out.read_bytes())
    assert record["engines"] == {"policyengine": 0, "taxsim": 1}


def test_relative_taxsim_path(tmp_path, monkeypatch):
    """A binary named relative to the working directory runs from there,
    not from a PATH lookup of its bare name."""
    default = default_taxsim_executable().resolve()
    monkeypatch.chdir(tmp_path)
    Path(default.name).write_bytes(default.read_bytes())
    Path(default.name).chmod(0o755)
    Path("in.csv").write_bytes(csv_bytes([PRE_2021_RECORD]))
    result = CliRunner().invoke(
        cli,
        ["taxsim", "in.csv", "-o", "out.csv", "--taxsim-path", f"./{default.name}"]
        + ["--provenance", "run.json"],
    )
    assert result.exit_code == 0, result.output
    record = json.loads(Path("run.json").read_text())
    assert record["taxsimBinaryPath"] == str((tmp_path / default.name).resolve())
    assert Path(record["input"]["path"]).resolve() == (tmp_path / "in.csv").resolve()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell quoting")
def test_taxsim_path_in_directory_with_shell_metacharacters(tmp_path, monkeypatch):
    """The shell command quotes paths, so a working directory whose name
    holds $ or a backtick neither breaks the run nor runs a command."""
    workdir = tmp_path / "dollar$HOME `touch injected` dir"
    (workdir / "sub").mkdir(parents=True)
    default = default_taxsim_executable().resolve()
    binary = workdir / "sub" / default.name
    binary.write_bytes(default.read_bytes())
    binary.chmod(0o755)
    monkeypatch.chdir(workdir)
    Path("in.csv").write_bytes(csv_bytes([PRE_2021_RECORD]))
    result = CliRunner().invoke(
        cli,
        ["taxsim", "in.csv", "-o", "out.csv", "--taxsim-path", f"sub/{default.name}"],
    )
    assert result.exit_code == 0, result.output
    assert len(pd.read_csv("out.csv")) == 1
    assert not (workdir / "injected").exists()
    assert not (tmp_path / "injected").exists()


def test_executable_binary_is_not_chmodded(tmp_path, monkeypatch):
    """A binary that is already executable is used as is, so one the user
    doesn't own (e.g. a shared TAXSIM-35 install) still runs."""
    default = default_taxsim_executable()
    copy = tmp_path / default.name
    copy.write_bytes(default.read_bytes())
    copy.chmod(0o755)

    def refuse(*args, **kwargs):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr("policyengine_taxsim.runners.taxsim_runner.os.chmod", refuse)
    df = pd.read_csv(io.StringIO(f"{HEADER}\n{PRE_2021_RECORD}\n"))
    assert TaxsimRunner(df, taxsim_path=str(copy)).taxsim_path == copy


class TaxsimAsPolicyEngine:
    """Stand-in PolicyEngineRunner for compare tests: returns TAXSIM's results."""

    def __init__(self, df, **kwargs):
        self._runner = TaxsimRunner(df)
        self.input_df = self._runner.input_df

    def run(self, *args, **kwargs):
        return self._runner.run(show_progress=False)


def test_compare_subcommand(tmp_path, monkeypatch):
    monkeypatch.setattr(CLI_MODULE, "PolicyEngineRunner", TaxsimAsPolicyEngine)
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD]))
    plain_dir = tmp_path / "plain"
    CliRunner().invoke(
        cli, ["compare", str(input_file), "--output-dir", str(plain_dir)]
    )
    # The sidecar lives inside an --output-dir that compare creates.
    out_dir = tmp_path / "cmp"
    sidecar = out_dir / "run.json"
    result = CliRunner().invoke(
        cli,
        [
            "compare",
            str(input_file),
            "--output-dir",
            str(out_dir),
            "--provenance",
            str(sidecar),
        ],
    )
    assert result.exit_code == 0, result.output
    record = json.loads(sidecar.read_text())
    consolidated = out_dir / "comparison_results_2019.csv"
    assert (
        consolidated.read_bytes()
        == (plain_dir / "comparison_results_2019.csv").read_bytes()
    )
    assert record["output"] == {
        "path": str(consolidated),
        "sha256": sha256(consolidated.read_bytes()),
        "records": len(pd.read_csv(consolidated)),
    }
    assert record["engines"] == {"policyengine": 1, "taxsim": 1}
    # Options are recorded as passed: no --year, so each record kept its own
    # year (the output file is named after the first record's).
    assert record["options"]["year"] is None


# The sidecar never replaces the run's data -------------------------------------


@pytest.mark.parametrize("target", ["output", "input"])
def test_sidecar_path_must_not_be_a_data_file(tmp_path, target):
    input_file = tmp_path / "in.csv"
    original = csv_bytes([PRE_2021_RECORD])
    input_file.write_bytes(original)
    out = tmp_path / "out.csv"
    sidecar = out if target == "output" else input_file
    result = CliRunner().invoke(
        cli, ["taxsim", str(input_file), "-o", str(out), "--provenance", str(sidecar)]
    )
    assert result.exit_code == 2, result.output
    assert "is the run's input or output file" in result.output
    assert not out.exists()  # refused before the run
    assert input_file.read_bytes() == original


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges")
def test_sidecar_symlinked_to_input_is_refused(tmp_path, fake_runner):
    input_file = tmp_path / "in.csv"
    original = csv_bytes([PRE_2021_RECORD])
    input_file.write_bytes(original)
    alias = tmp_path / "alias.json"
    alias.symlink_to(input_file)
    result = CliRunner().invoke(
        cli,
        ["policyengine", str(input_file), "-o", str(tmp_path / "out.csv")]
        + ["--provenance", str(alias)],
    )
    assert result.exit_code == 2, result.output
    assert input_file.read_bytes() == original


def test_sidecar_case_alias_of_new_output_is_refused(tmp_path, fake_runner):
    """On a case-insensitive filesystem OUT.CSV is out.csv; the output does
    not exist before the run, so the check before writing catches it."""
    probe = tmp_path / "probe"
    probe.write_text("")
    if not (tmp_path / "PROBE").exists():
        pytest.skip("case-sensitive filesystem")
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD]))
    out = tmp_path / "out.csv"
    result = CliRunner().invoke(
        cli,
        ["policyengine", str(input_file), "-o", str(out)]
        + ["--provenance", str(tmp_path / "OUT.CSV")],
    )
    assert result.exit_code == 2, result.output
    assert out.read_bytes().startswith(b"taxsimid,")  # still the CSV


def test_compare_sidecar_must_not_be_the_results_file(tmp_path, monkeypatch):
    monkeypatch.setattr(CLI_MODULE, "PolicyEngineRunner", TaxsimAsPolicyEngine)
    input_file = tmp_path / "in.csv"
    input_file.write_bytes(csv_bytes([PRE_2021_RECORD]))
    out_dir = tmp_path / "cmp"
    result = CliRunner().invoke(
        cli,
        ["compare", str(input_file), "--output-dir", str(out_dir)]
        + ["--provenance", str(out_dir / "comparison_results_2019.csv")],
    )
    assert result.exit_code == 2, result.output
    assert not (out_dir / "comparison_results_2019.csv").exists()


def test_in_place_run_hashes_the_input_as_read(tmp_path, fake_runner):
    """-o naming the input overwrites it; the sidecar still records the
    input's original bytes."""
    data = tmp_path / "data.csv"
    original = csv_bytes([PRE_2021_RECORD, "2,2022,5,1,40,0,0,1,2"])
    data.write_bytes(original)
    sidecar = tmp_path / "run.json"
    result = CliRunner().invoke(
        cli, ["policyengine", str(data), "-o", str(data), "--provenance", str(sidecar)]
    )
    assert result.exit_code == 0, result.output
    record = json.loads(sidecar.read_text())
    assert record["input"]["sha256"] == sha256(original)
    assert record["output"]["sha256"] == sha256(data.read_bytes())
    assert record["input"]["sha256"] != record["output"]["sha256"]


def test_stream_is_file(tmp_path):
    path = tmp_path / "in.csv"
    path.write_bytes(b"x")
    with open(path, "rb") as stream:
        assert CLI_MODULE._stream_is_file(stream, str(path))
        assert not CLI_MODULE._stream_is_file(stream, str(tmp_path / "other"))
    assert not CLI_MODULE._stream_is_file(io.StringIO(), str(path))


def test_sidecar_cannot_be_redirected_stdout(tmp_path):
    """`--provenance out.csv > out.csv` is refused (a real process, since
    the check reads the file behind stdout)."""
    executable = shutil.which("policyengine-taxsim")
    if executable is None:
        pytest.skip("policyengine-taxsim console script not on PATH")
    out = tmp_path / "out.csv"
    with open(out, "wb") as stdout:
        process = subprocess.run(
            [executable, "--provenance", str(out)],
            input=csv_bytes([PRE_2021_RECORD]),
            stdout=stdout,
            stderr=subprocess.PIPE,
            timeout=600,
        )
    assert process.returncode == 2, process.stderr.decode()
    assert b"stdout is written to" in process.stderr
    assert out.read_bytes() == b""


# Package sources --------------------------------------------------------------


class FakeDist:
    def __init__(self, direct_url):
        self._direct_url = direct_url

    def read_text(self, name):
        assert name == "direct_url.json"
        return self._direct_url


@pytest.mark.parametrize(
    "direct_url, expected",
    [
        (None, None),
        ("not json", None),
        ("[]", None),
        (
            '{"url": "https://github.com/PolicyEngine/policyengine-us", '
            '"vcs_info": {"vcs": "git", "commit_id": "abc123"}}',
            {
                "url": "https://github.com/PolicyEngine/policyengine-us",
                "commit": "abc123",
            },
        ),
        (
            '{"url": "file:///src/policyengine-taxsim", "dir_info": {"editable": true}}',
            {"url": "file:///src/policyengine-taxsim", "editable": True},
        ),
    ],
)
def test_package_source(direct_url, expected):
    assert prov._package_source(FakeDist(direct_url)) == expected


def test_installed_packages_report_running_emulator_version(monkeypatch):
    """An editable install's metadata keeps its install-time version; the
    sidecar reports the running code's version in both places."""
    monkeypatch.setattr(policyengine_taxsim, "__version__", "99.0.0")
    record = prov.build_provenance("cli", {}, {}, {}, {})
    assert record["policyengineTaxsimVersion"] == "99.0.0"
    assert record["installedPackages"]["policyengine-taxsim"] == "99.0.0"


def test_installed_packages_agree_with_importlib():
    packages, _ = prov.installed_packages()
    for name in ["policyengine-us", "policyengine-core", "pandas", "numpy"]:
        assert packages[name] == importlib.metadata.version(name)
    assert list(packages) == sorted(packages, key=str.lower)
