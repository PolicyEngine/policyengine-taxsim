"""The Modal API image replaces the base image's pip before any package install."""

import importlib.util
import sys
from unittest.mock import MagicMock

EXPECTED_PIP_BOOTSTRAP_COMMAND = (
    "printf '%s\\n' 'pip==26.2.2 --hash=sha256:"
    "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'"
    " > /tmp/pip-bootstrap.txt"
    " && python -m pip install --require-hashes --no-deps"
    " -r /tmp/pip-bootstrap.txt"
    " && rm /tmp/pip-bootstrap.txt"
)


def load_api_image_steps() -> list[tuple[str, tuple]]:
    """Import policyengine_taxsim.api against a Modal stub; list its image steps.

    The module is kept out of sys.modules, and only the ``modal`` entry is put
    back afterwards, as in the API fixture of test_deterministic_ordering.py.
    """
    modal_stub = MagicMock()
    missing = object()
    original_modal = sys.modules.get("modal", missing)
    sys.modules["modal"] = modal_stub
    try:
        spec = importlib.util.find_spec("policyengine_taxsim.api")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if original_modal is missing:
            del sys.modules["modal"]
        else:
            sys.modules["modal"] = original_modal
    return [
        (call_name.rsplit(".", 1)[-1], call_args)
        for call_name, call_args, _ in modal_stub.mock_calls
        if call_name.startswith("Image.debian_slim")
    ]


def test_api_image_replaces_pip_after_the_ca_store_upgrade():
    """The base's pip downloads only the hash-pinned pip that replaces it."""
    image_steps = load_api_image_steps()
    ca_upgrade_index = next(
        step_index
        for step_index, (step_name, step_args) in enumerate(image_steps)
        if step_name == "apt_install" and "ca-certificates" in step_args
    )
    bootstrap_index = image_steps.index(
        ("run_commands", (EXPECTED_PIP_BOOTSTRAP_COMMAND,))
    )
    package_install_indexes = [
        step_index
        for step_index, (step_name, step_args) in enumerate(image_steps)
        if step_name.startswith("pip_install")
        or (
            step_name == "run_commands"
            and step_index != bootstrap_index
            and any("pip install" in str(command) for command in step_args)
        )
    ]
    assert package_install_indexes
    assert ca_upgrade_index < bootstrap_index < min(package_install_indexes)
