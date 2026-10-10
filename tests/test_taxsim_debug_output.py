"""TAXSIM debug output is never parsed as household records.

taxsimtest builds write Fortran diagnostic lines to stdout between their CSV
rows. tests/fixtures/taxsim_stdout holds verbatim captures from real binaries
(provenance in its README); the expected values below are read off them.

Invariants of TaxsimRunner._parse_taxsim_output on CSV output:

- One row per record line, in stream order, and no row has a NaN taxsimid.
- Every non-blank stdout line is exactly one of: the header, a returned row,
  or a line in stdout_diagnostics (conservation).
- Each non-record line is filed under the taxsimid of the next record row,
  or under None when no row follows (attribution).
- The rows equal what the pre-change parser (pandas.read_csv, then
  to_numeric) returns for the same stream with the non-record lines removed
  (differential).
"""

import hashlib
import io
import logging
import platform
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

FIXTURES = Path(__file__).parent / "fixtures" / "taxsim_stdout"
REPO = Path(__file__).resolve().parents[1]
LOGGER = "policyengine_taxsim.runners.taxsim_runner"

# Diagnostic lines exactly as the binaries wrote them in the captures.
D2_UTAH_SINGLE = " d2       29126       25000         103         346"
D2_UTAH_JOINT = " d2       33009       32000          25         874"
D3_WEST_VIRGINIA = " d3       48543"
D4_WEST_VIRGINIA = " d4       48543           0"

CSV_CAPTURES = [
    "utah_elderly_idtl2",
    "utah_elderly_first_idtl0",
    "utah_elderly_consecutive_idtl2",
    "west_virginia_idtl0",
]

needs_posix = pytest.mark.skipif(
    platform.system() == "Windows", reason="the fake binary is a POSIX shell script"
)


def _parse(path):
    runner = TaxsimRunner.__new__(TaxsimRunner)
    return runner, runner._parse_taxsim_output(str(path))


def _parse_text(tmp_path, text):
    path = tmp_path / "taxsim.csv"
    path.write_text(text, encoding="utf-8")
    return _parse(path)


def _old_parse(text):
    """The pre-change CSV parse: pandas.read_csv, then to_numeric per column."""
    frame = pd.read_csv(io.StringIO(text))
    for col in frame.columns:
        if col != "state_name":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Captures from the 20260521 build (policyengine-taxsim 2.30.0) ---------------


def test_reproducer_returns_one_clean_row_per_record(caplog):
    """Six d2 lines before record 2 used to become six NaN-id rows."""
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        runner, result = _parse(FIXTURES / "utah_elderly_idtl2.stdout.txt")

    assert result.taxsimid.tolist() == [1, 2, 3]
    assert not result.isna().any().any()
    assert result.state.tolist() == [5, 45, 45]
    assert result.fiitax.tolist() == [3820.00, 585.00, 585.00]
    assert result.siitax.tolist() == [980.70, 49.88, 407.13]
    assert runner.stdout_diagnostics == {2: [D2_UTAH_SINGLE] * 6}
    assert runner.binary_build_date == "20260521"

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert "6 stdout line(s)" in message
    assert "before the rows of taxsimid 2" in message
    assert repr(D2_UTAH_SINGLE) in message


def test_lines_before_the_header_belong_to_the_first_record():
    """With the triggering record first, its lines precede the header."""
    runner, result = _parse(FIXTURES / "utah_elderly_first_idtl0.stdout.txt")

    assert list(result.columns) == [
        "taxsimid",
        "year",
        "state",
        "fiitax",
        "siitax",
        "fica",
        "frate",
        "srate",
        "ficar",
        "tfica",
        "cdate-20260521",
    ]
    assert result.taxsimid.tolist() == [2, 1, 3]
    assert result.siitax.tolist() == [49.88, 980.70, 407.13]
    assert runner.stdout_diagnostics == {2: [D2_UTAH_SINGLE] * 6}


def test_consecutive_records_each_keep_their_own_lines():
    """Lines between two affected rows go to the later row, not the earlier."""
    runner, result = _parse(FIXTURES / "utah_elderly_consecutive_idtl2.stdout.txt")

    assert result.taxsimid.tolist() == [4, 5, 6]
    assert result.fiitax.tolist() == [585.00, 585.00, 0.00]
    assert result.siitax.tolist() == [49.88, 49.88, 0.00]
    assert runner.stdout_diagnostics == {
        4: [D2_UTAH_SINGLE] * 6,
        5: [D2_UTAH_SINGLE] * 6,
        6: [D2_UTAH_JOINT] * 6,
    }


def test_verbose_output_still_parses():
    """idtl=5 output has no CSV header, so the verbose parser reads it."""
    runner, result = _parse(FIXTURES / "utah_elderly_idtl5.stdout.txt")

    assert result.taxsimid.tolist() == [2]
    assert result.fiitax.tolist() == [585.00]
    assert result.siitax.tolist() == [49.88]
    assert result.fica.tolist() == [4590.00]
    assert runner.stdout_diagnostics == {}


# Capture from the August 2026 build (bundled since #1150) --------------------


def test_august_build_counters_are_kept_for_the_west_virginia_record():
    runner, result = _parse(FIXTURES / "west_virginia_idtl0.stdout.txt")

    assert result.taxsimid.tolist() == [1, 2]
    assert result.siitax.tolist() == [980.70, 1502.38]
    assert runner.stdout_diagnostics == {2: [D3_WEST_VIRGINIA, D4_WEST_VIRGINIA] * 12}
    assert runner.binary_build_date == "cd2026081819"


# Invariants on every CSV capture --------------------------------------------


@pytest.mark.parametrize("name", CSV_CAPTURES)
def test_capture_rows_match_the_old_parser_on_clean_output(name):
    """Conservation and differential checks against the raw capture.

    In these captures every record row starts "<id>.,"; the expected split
    comes from that, not from the parser under test.
    """
    path = FIXTURES / f"{name}.stdout.txt"
    lines = [line for line in path.read_text().split("\n") if line.strip()]
    header = [line for line in lines if line.startswith("taxsimid,")]
    rows = [line for line in lines if line.split(",")[0][:-1].isdigit()]
    others = [line for line in lines if line not in header + rows]

    runner, result = _parse(path)
    kept = [line for group in runner.stdout_diagnostics.values() for line in group]

    assert len(header) == 1
    assert len(lines) == 1 + len(result) + len(kept)
    assert sorted(kept) == sorted(others)
    pd.testing.assert_frame_equal(result, _old_parse("\n".join(header + rows)))


# Synthetic streams ----------------------------------------------------------


def test_known_debug_lines_are_removed(tmp_path):
    runner, result = _parse_text(
        tmp_path,
        "taxsimid,fiitax,siitax,cdate-test\n1,100,20,0\n d3        1257\n"
        " d4        1257           0\n2,200,40,0\n",
    )
    assert result.taxsimid.tolist() == [1, 2]
    assert result.fiitax.tolist() == [100, 200]
    assert runner.binary_build_date == "test"
    assert runner.stdout_diagnostics == {
        2: [" d3        1257", " d4        1257           0"]
    }


def test_modern_build_stamp_is_reported(tmp_path):
    """Builds since August 2026 stamp "cd2026081819" instead of "cdate-..."."""
    runner, _ = _parse_text(
        tmp_path, 'taxsimid,fiitax,siitax,"cd2026081819"\n1,100,20,0\n'
    )
    assert runner.binary_build_date == "cd2026081819"


def test_malformed_record_is_reported_not_returned_as_a_nan_row(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        runner, result = _parse_text(
            tmp_path, "taxsimid,fiitax,siitax\n1,100,20\nbroken,200,40\n"
        )
    assert result.taxsimid.tolist() == [1]
    assert runner.stdout_diagnostics == {None: ["broken,200,40"]}
    assert "1 after the last row" in caplog.text
    assert "'broken,200,40'" in caplog.text


@pytest.mark.parametrize(
    "line",
    [
        "nan,200,40",
        "inf,200,40",
        "-inf,200,40",
        "1e400,200,40",
        "1_000,200,40",  # float() accepts it; pandas does not
        "١,200,40",  # Arabic-Indic one: float() accepts it; pandas does not
        "0x10,200,40",
        ",200,40",
        '"",200,40',
        "2,200",
        "2,200,40,0",
        "taxsimid,fiitax,siitax",
        " d2       29126       25000         103         346",
    ],
)
def test_non_record_lines_never_become_rows(tmp_path, line):
    runner, result = _parse_text(
        tmp_path, f"taxsimid,fiitax,siitax\n{line}\n3,300,60\n"
    )
    assert result.taxsimid.tolist() == [3]
    assert runner.stdout_diagnostics == {3: [line]}


@pytest.mark.parametrize(
    "spelling, taxsimid",
    [
        ("7.", 7),
        ("7", 7),
        (" 7. ", 7),
        ("+7", 7),
        ("7e0", 7),
        ("7.5", 7.5),
        (".5", 0.5),
    ],
)
def test_numeric_id_spellings_are_records(tmp_path, spelling, taxsimid):
    runner, result = _parse_text(
        tmp_path, f"taxsimid,fiitax\n d2 1 2\n{spelling},100\n"
    )
    assert result.taxsimid.tolist() == [taxsimid]
    assert runner.stdout_diagnostics == {taxsimid: [" d2 1 2"]}


def test_blank_lines_are_not_diagnostics(tmp_path):
    runner, result = _parse_text(tmp_path, "\ntaxsimid,fiitax\n\n1,100\n   \n2,200\n\n")
    assert result.taxsimid.tolist() == [1, 2]
    assert runner.stdout_diagnostics == {}


def test_repeated_taxsimid_keeps_every_line_in_order(tmp_path):
    runner, result = _parse_text(
        tmp_path, "taxsimid,fiitax\n d2 1\n1,100\n d2 2\n1,200\n"
    )
    assert result.taxsimid.tolist() == [1, 1]
    assert runner.stdout_diagnostics == {1: [" d2 1", " d2 2"]}


def test_header_only_output_is_an_empty_frame(tmp_path):
    runner, result = _parse_text(tmp_path, "taxsimid,fiitax\n")
    assert list(result.columns) == ["taxsimid", "fiitax"]
    assert result.empty
    assert runner.stdout_diagnostics == {}


def test_crlf_output_parses_like_lf(tmp_path):
    """The Windows build may end lines with CRLF."""
    lf = FIXTURES / "utah_elderly_idtl2.stdout.txt"
    crlf = tmp_path / "crlf.txt"
    crlf.write_bytes(lf.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    lf_runner, lf_result = _parse(lf)
    crlf_runner, crlf_result = _parse(crlf)
    pd.testing.assert_frame_equal(crlf_result, lf_result)
    assert crlf_runner.stdout_diagnostics == lf_runner.stdout_diagnostics


def test_undecodable_bytes_stay_visible_in_diagnostics(tmp_path):
    path = tmp_path / "taxsim.csv"
    path.write_bytes(b"taxsimid,fiitax\n d2 \xff\xfe\n1,100\n")
    runner, result = _parse(path)
    assert result.taxsimid.tolist() == [1]
    assert runner.stdout_diagnostics == {1: [" d2 \\xff\\xfe"]}


def test_byte_order_mark_is_ignored(tmp_path):
    """pandas.read_csv skipped a leading BOM; the parser still does."""
    path = tmp_path / "taxsim.csv"
    path.write_bytes(b"\xef\xbb\xbftaxsimid,fiitax\n1,100\n")
    runner, result = _parse(path)
    assert result.taxsimid.tolist() == [1]
    assert runner.stdout_diagnostics == {}


def test_output_without_a_header_or_verbose_sections_raises(tmp_path):
    with pytest.raises(Exception, match="both CSV and verbose"):
        _parse_text(tmp_path, " d2 1 2\n1,100\n")


def test_diagnostics_are_reset_on_each_parse(tmp_path):
    runner = TaxsimRunner.__new__(TaxsimRunner)
    runner._parse_taxsim_output(str(FIXTURES / "utah_elderly_idtl2.stdout.txt"))
    assert runner.stdout_diagnostics
    clean = tmp_path / "clean.csv"
    clean.write_text("taxsimid,fiitax\n1,100\n")
    runner._parse_taxsim_output(str(clean))
    assert runner.stdout_diagnostics == {}


def test_clean_output_logs_nothing(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        _parse_text(tmp_path, "taxsimid,fiitax\n1,100\n2,200\n")
    assert caplog.records == []


# Property-based: random streams with interleaved non-record lines ------------

_COLUMN = st.from_regex(r"[a-z][a-z0-9]{0,5}", fullmatch=True)
_VALUE = st.tuples(
    st.floats(min_value=-1e7, max_value=1e7, allow_nan=False), st.booleans()
).map(
    lambda pair: f"{pair[0]:.2f}".replace("0.", ".", 1) if pair[1] else f"{pair[0]:.2f}"
)
_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\n"),
    max_size=30,
)


def _non_record_lines(width):
    """Lines that cannot be a record of a header ``width`` fields wide."""
    fortran = st.tuples(
        st.integers(0, 9), st.lists(st.integers(-(10**7), 10**7), max_size=4)
    ).map(lambda t: f" d{t[0]}" + "".join(f"{n:12d}" for n in t[1]))
    # A first field starting with a letter is never numeric (or "taxsimid").
    lettered = _TEXT.map(lambda text: "x" + text)
    wrong_width = st.tuples(
        st.integers(0, 10**6), st.integers(0, 8).filter(lambda n: n + 1 != width)
    ).map(lambda t: f"{t[0]}." + ",0" * t[1])
    return st.one_of(fortran, lettered, wrong_width)


@st.composite
def _taxsim_streams(draw):
    header = ["taxsimid", *draw(st.lists(_COLUMN, unique=True, max_size=5))]
    width = len(header)
    noise = _non_record_lines(width)
    records = []
    for _ in range(draw(st.integers(0, 8))):
        taxsimid = draw(st.integers(0, 10**6))
        spelling = draw(st.sampled_from(["{}.", "{}"])).format(taxsimid)
        row = ",".join([spelling, *(draw(_VALUE) for _ in header[1:])])
        records.append((taxsimid, row, draw(st.lists(noise, max_size=4))))
    trailing = draw(st.lists(noise, max_size=3))

    header_line = ",".join(header)
    lines = []
    if records and draw(st.booleans()):
        # The binary writes the header with the first row, after that
        # record's diagnostics.
        lines += records[0][2]
        lines.append(header_line)
        lines.append(records[0][1])
        rest = records[1:]
    else:
        lines.append(header_line)
        rest = records
    for _, row, before in rest:
        lines += before
        lines.append(row)
    lines += trailing
    for position in draw(st.lists(st.integers(0, len(lines)), max_size=3)):
        lines.insert(position, draw(st.sampled_from(["", "   "])))

    expected = {}
    for taxsimid, _, before in records:
        if before:
            expected.setdefault(taxsimid, []).extend(before)
    if trailing:
        expected.setdefault(None, []).extend(trailing)
    clean = "\n".join([header_line, *(row for _, row, _ in records)])
    return "\n".join(lines) + "\n", records, expected, clean


@settings(max_examples=300, deadline=None)
@given(_taxsim_streams())
def test_parser_invariants_hold_for_any_interleaving(stream):
    text, records, expected, clean = stream
    runner = TaxsimRunner.__new__(TaxsimRunner)
    result = runner._parse_csv_taxsim_output(text)

    # One row per record, in order, never a NaN id.
    assert result.taxsimid.tolist() == [taxsimid for taxsimid, _, _ in records]
    assert not result.taxsimid.isna().any()
    # Attribution: each line under the next record's id, trailing under None.
    assert runner.stdout_diagnostics == expected
    # Conservation: header + rows + diagnostics = non-blank lines.
    nonblank = [line for line in text.split("\n") if line.strip()]
    kept = sum(len(group) for group in runner.stdout_diagnostics.values())
    assert len(nonblank) == 1 + len(result) + kept
    # Differential: same frame as the old parser on the clean stream.
    pd.testing.assert_frame_equal(result, _old_parse(clean))


# Through TaxsimRunner.run ----------------------------------------------------


def _fake_binary(tmp_path, stdout_path):
    """A stand-in executable that ignores stdin and prints a capture."""
    script = tmp_path / "fake-taxsimtest.sh"
    script.write_text(f"#!/bin/sh\ncat > /dev/null\ncat '{stdout_path}'\n")
    script.chmod(0o755)
    return script


@needs_posix
def test_run_returns_clean_ids_and_keeps_diagnostics(tmp_path):
    df = pd.read_csv(FIXTURES / "utah_elderly_idtl2.input.csv")
    binary = _fake_binary(tmp_path, FIXTURES / "utah_elderly_idtl2.stdout.txt")
    # A str path, as the CLI's --taxsim-path passes it.
    runner = TaxsimRunner(df, taxsim_path=str(binary))

    result = runner.run(show_progress=False)

    assert result.taxsimid.tolist() == [1, 2, 3]
    assert runner.stdout_diagnostics == {2: [D2_UTAH_SINGLE] * 6}


@needs_posix
def test_run_names_submitted_records_left_without_a_row(tmp_path, caplog):
    stdout = tmp_path / "stdout.txt"
    stdout.write_text("taxsimid,fiitax\n1.,100.00\n2.,200.00,extra\n")
    df = pd.DataFrame({"taxsimid": [1, 2], "year": [2026, 2026], "idtl": [2, 2]})
    runner = TaxsimRunner(df, taxsim_path=str(_fake_binary(tmp_path, stdout)))

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        result = runner.run(show_progress=False)

    assert result.taxsimid.tolist() == [1]
    assert runner.stdout_diagnostics == {None: ["2.,200.00,extra"]}
    assert "no result row for 1 submitted record(s): taxsimid 2." in caplog.text


@needs_posix
def test_cli_taxsim_path_option_runs_a_custom_binary(tmp_path):
    from click.testing import CliRunner

    from policyengine_taxsim.cli import cli

    binary = _fake_binary(tmp_path, FIXTURES / "utah_elderly_idtl2.stdout.txt")
    output = tmp_path / "out.csv"
    result = CliRunner().invoke(
        cli,
        [
            "taxsim",
            str(FIXTURES / "utah_elderly_idtl2.input.csv"),
            "--output",
            str(output),
            "--taxsim-path",
            str(binary),
        ],
    )

    assert result.exit_code == 0, result.output
    assert pd.read_csv(output).taxsimid.tolist() == [1, 2, 3]


def test_bundled_binary_returns_exactly_the_submitted_records():
    """Whatever the bundled build writes to stdout, ids come back clean.

    Record 4 is the West Virginia profile that the August builds write
    d3/d4 lines for.
    """
    df = pd.read_csv(FIXTURES / "utah_elderly_idtl2.input.csv")
    west_virginia = pd.read_csv(FIXTURES / "west_virginia_idtl0.input.csv").iloc[[1]]
    df = pd.concat([df, west_virginia.assign(taxsimid=4, idtl=2)], ignore_index=True)
    runner = TaxsimRunner(df)

    result = runner.run(show_progress=False)

    assert result.taxsimid.tolist() == [1, 2, 3, 4]
    assert set(runner.stdout_diagnostics) <= {1, 2, 3, 4}


# The captures are verbatim: re-run the real binaries where available ---------

_BINARY_20260521_BLOB = "9e91184e205744a4e2049b2bcdd95a1c7fb0e56c"
_BINARY_20260521_SHA256 = (
    "0d9e43a983055d44eec9e5de7edfc933fa061b2a336716d760fe98abf4336319"
)
_BUNDLED_AUGUST_SHA256 = {
    "Darwin": (
        "taxsimtest-osx.exe",
        "4a17af9c2adbea27b1e6cce240610aede264e008bcdf64b131e0c81220f62b8c",
    ),
    "Linux": (
        "taxsimtest-linux.exe",
        "00a321d2467ba011992f8b83c6e485a9b710c48fca4262a23fec1de26942a89b",
    ),
}


def _run_binary(binary, input_path):
    with open(input_path, "rb") as stdin:
        return subprocess.run(
            [str(binary)], stdin=stdin, capture_output=True, check=False
        )


@pytest.fixture(scope="module")
def binary_20260521(tmp_path_factory):
    """The 20260521 macOS build, extracted from this repository's history."""
    if platform.system() != "Darwin":
        pytest.skip("the 20260521 capture binary is the macOS build")
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    blob = subprocess.run(
        [git, "-C", str(REPO), "cat-file", "blob", _BINARY_20260521_BLOB],
        capture_output=True,
        check=False,
    )
    if blob.returncode != 0:
        pytest.skip("git history lacks the 20260521 binary (shallow clone)")
    binary = tmp_path_factory.mktemp("taxsimtest") / "taxsimtest-osx-20260521.exe"
    binary.write_bytes(blob.stdout)
    binary.chmod(0o755)
    assert _sha256(binary) == _BINARY_20260521_SHA256
    return binary


@pytest.mark.parametrize(
    "name",
    [
        "utah_elderly_idtl2",
        "utah_elderly_first_idtl0",
        "utah_elderly_consecutive_idtl2",
        "utah_elderly_idtl5",
    ],
)
def test_capture_matches_the_20260521_build(binary_20260521, name):
    run = _run_binary(binary_20260521, FIXTURES / f"{name}.input.csv")
    assert run.returncode == 0
    assert run.stderr == b""
    assert run.stdout == (FIXTURES / f"{name}.stdout.txt").read_bytes()


def test_runner_on_the_20260521_build_returns_no_nan_ids(binary_20260521):
    """End to end: the runner's own input file through the 2.30.0 binary."""
    df = pd.read_csv(FIXTURES / "utah_elderly_idtl2.input.csv")
    runner = TaxsimRunner(df, taxsim_path=binary_20260521)

    result = runner.run(show_progress=False)

    assert result.taxsimid.tolist() == [1, 2, 3]
    assert not result.taxsimid.isna().any()
    assert result.siitax.tolist() == [980.70, 49.88, 407.13]
    assert runner.stdout_diagnostics == {2: [D2_UTAH_SINGLE] * 6}


def test_west_virginia_capture_matches_the_bundled_august_build():
    entry = _BUNDLED_AUGUST_SHA256.get(platform.system())
    if entry is None:
        pytest.skip("no August build capture for this platform")
    binary = REPO / "resources" / "taxsimtest" / entry[0]
    if not binary.exists() or _sha256(binary) != entry[1]:
        pytest.skip("the bundled binary is no longer the August 2026 build")
    binary.chmod(0o755)

    run = _run_binary(binary, FIXTURES / "west_virginia_idtl0.input.csv")

    assert run.returncode == 0
    assert run.stderr == b""
    assert run.stdout == (FIXTURES / "west_virginia_idtl0.stdout.txt").read_bytes()
