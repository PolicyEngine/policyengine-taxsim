"""``--chunk-size`` and ``chunk_size`` set the records per PolicyEngine
simulation.

PolicyEngineRunner simulates records in chunks of ``CHUNK_SIZE`` (10,000).
Python callers could set it per runner only through an undocumented,
unvalidated ``runner.CHUNK_SIZE = N``, which ``sample()`` and ``filter_by_*()``
dropped, and the CLI had no way to set it.
The option lets a caller trade a worker's peak memory against CPU time.
"""

from io import StringIO

import pandas as pd
import pytest
from click.testing import CliRunner

from policyengine_taxsim.cli import cli
from policyengine_taxsim.runners import (
    PolicyEngineRunner,
    StitchedRunner,
    policyengine_runner,
)

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


@pytest.mark.parametrize(
    "chunk_size, expected",
    [
        (1, ["collect", "collect", "release"]),
        (2, ["collect", "release"]),
        (3, ["release"]),
    ],
)
def test_chunk_size_argument_sets_when_the_runner_collects(
    monkeypatch, chunk_size, expected
):
    """The runner collects garbage after every chunk but the last, so it
    counts chunks at the runner's own chunk size, the size it cuts them at."""
    calls = []
    monkeypatch.setattr(
        PolicyEngineRunner,
        "_run_chunk",
        lambda self, chunk_df: chunk_df[["taxsimid"]].reset_index(drop=True),
    )
    monkeypatch.setattr(
        policyengine_runner,
        "_free_finished_simulations",
        lambda: calls.append("collect"),
    )
    monkeypatch.setattr(
        policyengine_runner,
        "_release_finished_simulations",
        lambda: calls.append("release"),
    )

    runner = PolicyEngineRunner(_records(), chunk_size=chunk_size)
    output = runner.run(show_progress=False)

    assert calls == expected
    assert output["taxsimid"].tolist() == [1, 2, 3]


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


@pytest.mark.parametrize(
    "args",
    [
        ["--chunk-size", "2", "policyengine", "{source}", "--output", "{output}"],
        # The subcommand's own value wins over the one before it.
        [
            "--chunk-size",
            "1",
            "policyengine",
            "{source}",
            "--output",
            "{output}",
            "--chunk-size",
            "2",
        ],
    ],
    ids=["before-subcommand", "subcommand-overrides"],
)
def test_policyengine_command_takes_chunk_size_before_it(chunk_sizes, tmp_path, args):
    source = tmp_path / "input.csv"
    source.write_text(CSV)
    output = tmp_path / "output.csv"

    result = CliRunner().invoke(
        cli, [a.format(source=source, output=output) for a in args]
    )

    assert result.exit_code == 0, f"{result.output}\n{result.exception}"
    assert chunk_sizes == [2, 1]


@pytest.mark.parametrize(
    "args, expected",
    [
        (["compare", "{source}", "--chunk-size", "2"], 2),
        (["--chunk-size", "2", "compare", "{source}"], 2),
        (["--chunk-size", "1", "compare", "{source}", "--chunk-size", "2"], 2),
        (["compare", "{source}"], PolicyEngineRunner.CHUNK_SIZE),
    ],
    ids=["after", "before", "subcommand-overrides", "default"],
)
def test_compare_command_takes_chunk_size(monkeypatch, tmp_path, args, expected):
    """compare hands the chunk size to its PolicyEngine runner. The run is
    stopped there, before TAXSIM, which these tests don't need."""
    source = tmp_path / "input.csv"
    source.write_text(CSV)
    seen = []

    def stop(self, *args, **kwargs):
        seen.append(self.CHUNK_SIZE)
        raise RuntimeError("stopped before simulating")

    monkeypatch.setattr(PolicyEngineRunner, "run", stop)
    CliRunner().invoke(cli, [a.format(source=source) for a in args])

    assert seen == [expected]


@pytest.mark.parametrize(
    "derive",
    [
        lambda runner: runner.sample(2),
        lambda runner: runner.sample(10),  # n >= records: returns all records
        lambda runner: runner.filter_by_year(2025),
        lambda runner: runner.filter_by_state(44),
    ],
    ids=["sample", "sample-all", "filter_by_year", "filter_by_state"],
)
def test_derived_runners_keep_the_settings(derive):
    runner = PolicyEngineRunner(
        _records(), chunk_size=1, disable_salt=True, scorp_treatment="active"
    )

    derived = derive(runner)

    assert derived.CHUNK_SIZE == 1
    assert derived.disable_salt is True
    assert derived.scorp_treatment == "active"
    # Without a per-runner chunk size, a derived runner follows the class
    # default.
    assert "CHUNK_SIZE" not in vars(derive(PolicyEngineRunner(_records())))


def test_derived_stitched_runner_keeps_the_chunk_size():
    runner = StitchedRunner(_records(), chunk_size=1, disable_salt=True)

    derived = runner.filter_by_year(2025)

    assert derived._pe_kwargs["chunk_size"] == 1
    assert derived._pe_kwargs["disable_salt"] is True
