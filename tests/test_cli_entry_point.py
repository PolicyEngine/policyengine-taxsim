"""
Regression test for issue #702: CLI entry point must resolve to a callable.

The Aug 2025 click group refactor renamed `main` to `cli` in cli.py but
forgot to update pyproject.toml, breaking every `policyengine-taxsim`
command for new installs.  This test ensures the entry point stays valid.
"""

from importlib.metadata import distribution


def test_cli_entry_point_resolves():
    """The console script entry point must import and be callable."""
    dist = distribution("policyengine-taxsim")
    console_scripts = [
        ep for ep in dist.entry_points if ep.group == "console_scripts"
    ]
    assert len(console_scripts) == 1, "Expected exactly one console script"
    ep = console_scripts[0]
    assert ep.name == "policyengine-taxsim"

    # This is the line that would have caught #702 — it raises ImportError
    # if pyproject.toml points to a function that doesn't exist.
    func = ep.load()
    assert callable(func)
