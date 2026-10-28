"""``--chunk-size`` and ``chunk_size`` set the records per PolicyEngine
simulation.

PolicyEngineRunner simulates records in chunks of ``CHUNK_SIZE`` (10,000).
Python callers could change it only by setting the class attribute, which
changes it for every runner in the process, and the CLI had no way to set it.
The option lets a caller trade a worker's peak memory against CPU time.
"""

from io import StringIO

import pandas as pd
import pytest
from click.testing import CliRunner

from policyengine_taxsim.cli import cli
from policyengine_taxsim.runners import PolicyEngineRunner

CSV = (
    "taxsimid,year,state,mstat,page,sage,pwages,idtl\n"
    "1,2025,5,1,40,0,30000,2\n"
    "2,2025,44,2,45,43,80000,2\n"
    "3,2025,36,1,30,0,50000,2\n"
)


@pytest.fixture
def chunk_sizes(monkeypatch):
    """Record the size of every chunk the runner simulates."""
    sizes = []
    run_chunk = PolicyEngineRunner._run_chunk

    def tracked(self, chunk_df):
        sizes.append(len(chunk_df))
        return run_chunk(self, chunk_df)

    monkeypatch.setattr(PolicyEngineRunner, "_run_chunk", tracked)
    return sizes


def _records():
    return pd.read_csv(StringIO(CSV))


def test_chunk_size_argument_sets_records_per_chunk(chunk_sizes):
    records = _records()

    chunked = PolicyEngineRunner(records, chunk_size=2).run(show_progress=False)
    assert chunk_sizes == [2, 1]

    whole = PolicyEngineRunner(records).run(show_progress=False)
    assert chunk_sizes == [2, 1, 3]
    # Chunking changes neither the results nor their order.
    pd.testing.assert_frame_equal(chunked, whole)


def test_chunk_size_argument_leaves_the_class_default():
    runner = PolicyEngineRunner(_records(), chunk_size=2)
    assert runner.CHUNK_SIZE == 2
    assert PolicyEngineRunner.CHUNK_SIZE == 10_000
    assert PolicyEngineRunner(_records()).CHUNK_SIZE == 10_000


@pytest.mark.parametrize("bad", [0, -1, 1.5, "2", True])
def test_invalid_chunk_size_is_rejected(bad):
    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        PolicyEngineRunner(_records(), chunk_size=bad)


def test_policyengine_command_takes_chunk_size(chunk_sizes, tmp_path):
    source = tmp_path / "input.csv"
    source.write_text(CSV)
    output = tmp_path / "output.csv"

    result = CliRunner().invoke(
        cli,
        ["policyengine", str(source), "--output", str(output), "--chunk-size", "2"],
    )

    assert result.exit_code == 0, f"{result.output}\n{result.exception}"
    assert chunk_sizes == [2, 1]
    assert pd.read_csv(output)["taxsimid"].tolist() == [1, 2, 3]


def test_stdin_mode_takes_chunk_size(chunk_sizes):
    result = CliRunner().invoke(cli, ["--chunk-size", "1"], input=CSV)

    assert result.exit_code == 0, f"{result.output}\n{result.exception}"
    assert chunk_sizes == [1, 1, 1]


def test_cli_rejects_a_nonpositive_chunk_size(chunk_sizes, tmp_path):
    source = tmp_path / "input.csv"
    source.write_text(CSV)

    result = CliRunner().invoke(cli, ["policyengine", str(source), "--chunk-size", "0"])

    assert result.exit_code == 2
    assert "--chunk-size" in result.output
    assert chunk_sizes == []
