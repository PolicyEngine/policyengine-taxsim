"""Pin the public surfaces documented as stable (Future Plans docs).

Downstream pipelines call these directly, so their names and shapes are a
compatibility contract: the CLI reading TAXSIM-format CSV on stdin and
writing TAXSIM-format CSV to stdout, the runners import path, the
PolicyEngineRunner class, its constructor taking a TAXSIM-format DataFrame,
and the documented zero-argument run() returning a TAXSIM-format DataFrame.
Changing any of them is a breaking change that needs a deprecation path.
The entry point's resolvability has its own pin in test_cli_entry_point.py.
The README and documentation site cite these test files as the CI pins, so
the last test fails if either doc names a test file that doesn't exist.
"""

import inspect
import io
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_CITING_CONTRACT_TESTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "dashboard" / "src" / "components" / "DocumentationContent.jsx",
)
CONTRACT_TESTS = {"tests/test_public_contract.py", "tests/test_cli_entry_point.py"}

TAXSIM_INPUT = pd.DataFrame(
    [
        {
            "taxsimid": 1,
            "year": 2023,
            "state": 6,
            "mstat": 1,
            "page": 40,
            "pwages": 50_000,
        }
    ]
)


def test_runner_import_path_and_class():
    from policyengine_taxsim.runners import PolicyEngineRunner

    assert inspect.isclass(PolicyEngineRunner)


def test_runner_accepts_and_returns_taxsim_format_dataframe():
    from policyengine_taxsim.runners import PolicyEngineRunner

    result = PolicyEngineRunner(TAXSIM_INPUT.copy()).run()

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    for column in ("taxsimid", "year", "fiitax"):
        assert column in result.columns


def test_cli_reads_taxsim_csv_stdin_and_writes_taxsim_csv_stdout():
    cli = shutil.which("policyengine-taxsim")
    assert cli is not None, "policyengine-taxsim console script not installed"

    process = subprocess.run(
        [cli],
        input=TAXSIM_INPUT.to_csv(index=False),
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert process.returncode == 0, process.stderr
    result = pd.read_csv(io.StringIO(process.stdout))
    assert len(result) == 1
    for column in ("taxsimid", "year", "fiitax"):
        assert column in result.columns


def test_docs_cite_only_contract_tests_that_exist():
    for doc in DOCS_CITING_CONTRACT_TESTS:
        cited = set(re.findall(r"tests/test_\w+\.py", doc.read_text(encoding="utf-8")))
        assert CONTRACT_TESTS <= cited, (
            f"{doc.name} no longer cites {CONTRACT_TESTS - cited}"
        )
        for path in cited:
            assert (REPO_ROOT / path).is_file(), f"{doc.name} cites missing {path}"
