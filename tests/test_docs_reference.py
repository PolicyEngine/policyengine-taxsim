"""The reference blocks in docs/ match the code.

scripts/generate_docs_reference.py rebuilds every block between
``<!-- BEGIN GENERATED: name -->`` markers in docs/input-guide.md,
docs/design.md and docs/security-and-deployment.md from the code: input
handling by running the emulator's input path on probe records, outputs from
variable_mappings.yaml, executables from resources/, dependencies from
pyproject.toml and the snapshot in docs/dependencies/. These tests fail when a
committed block no longer matches, or when the hand-written input metadata
and the columns the code reads disagree.

Fix a failure by running ``python scripts/generate_docs_reference.py`` and
committing the result (after adding any new column to
docs/reference/input_variables.yaml).
"""

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "generate_docs_reference", REPO / "scripts" / "generate_docs_reference.py"
)
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

REGENERATE = "Run: python scripts/generate_docs_reference.py"


@pytest.mark.parametrize("document", sorted(generator.GENERATED))
def test_generated_blocks_are_current(document):
    text = (REPO / "docs" / document).read_text(encoding="utf-8")
    assert generator.render(document, text) == text, (
        f"docs/{document} no longer matches the code. {REGENERATE}"
    )


def test_input_metadata_lists_exactly_the_columns_the_code_reads():
    documented = set(generator.load_input_metadata())
    read = generator.read_columns()
    assert documented == read, (
        f"Add to docs/reference/input_variables.yaml: {sorted(read - documented)}; "
        f"remove: {sorted(documented - read)}. Then {REGENERATE.lower()}"
    )


def test_input_metadata_entries_are_complete():
    for name, entry in generator.load_input_metadata().items():
        assert set(entry) == {"group", "meaning", "type", "valid"}, name
        assert entry["group"] in generator.GROUP_ORDER, name


def test_web_runner_knows_the_documented_columns():
    """The web runner warns about columns outside api.KNOWN_COLUMNS. api.py
    imports modal at import time, so the set is read from its source."""
    tree = ast.parse(
        (REPO / "policyengine_taxsim" / "api.py").read_text(encoding="utf-8")
    )
    known = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            getattr(target, "id", None) == "KNOWN_COLUMNS" for target in node.targets
        )
    )
    documented = set(generator.load_input_metadata())
    assert known <= documented
    # The TAXSIM-35 option columns reach pre-2021 rows but draw the warning.
    assert documented - known == {"opt1", "opt1v"}


def test_every_run_time_pin_is_in_the_design_doc():
    """docs/design.md's "Adjustments at run time" table names every variable
    PolicyEngineRunner holds fixed on the Microsimulation."""
    design = (REPO / "docs" / "design.md").read_text(encoding="utf-8")
    section = design.split("## Adjustments at run time")[1].split("\n## ")[0]
    named = set(re.findall(r"`(\w+)`", section))
    missing = [name for name in generator.run_time_pins() if name not in named]
    assert not missing, f"Add to the table in docs/design.md: {missing}"


@pytest.mark.parametrize("python", generator.SNAPSHOT_PYTHONS)
def test_dependency_snapshot_satisfies_pyproject(python):
    """Each direct dependency in pyproject.toml is in the snapshot at a version
    pyproject allows, so changing a requirement forces a refresh
    (python scripts/generate_docs_reference.py --refresh-dependencies TIME)."""
    resolved = generator.parse_requirements(
        REPO / "docs" / "dependencies" / f"requirements-py{python}.txt"
    )
    for text in generator._pyproject()["project"]["dependencies"]:
        requirement = Requirement(text)
        if requirement.marker and not requirement.marker.evaluate(
            {"python_version": python, "python_full_version": f"{python}.0"}
        ):
            continue
        name = canonicalize_name(requirement.name)
        assert name in resolved, f"{name} missing from the Python {python} snapshot"
        assert requirement.specifier.contains(resolved[name][0], prereleases=True), (
            f"Python {python} snapshot has {name}=={resolved[name][0]}, "
            f"outside {requirement.specifier}"
        )


def test_snapshot_files_are_the_resolutions_snapshot_json_records():
    snapshot = json.loads(
        (REPO / "docs" / "dependencies" / "snapshot.json").read_text(encoding="utf-8")
    )
    for python in generator.SNAPSHOT_PYTHONS:
        resolved = generator.parse_requirements(
            REPO / "docs" / "dependencies" / f"requirements-py{python}.txt"
        )
        versions = {name: entry[0] for name, entry in resolved.items()}
        assert versions == snapshot["linux"][python], python
