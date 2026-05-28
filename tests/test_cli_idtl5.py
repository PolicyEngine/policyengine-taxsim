"""
Tests for idtl=5 (human-readable full-text) output in the cli stdin/stdout
flow. The legacy `exe.py` PyInstaller entry point supported idtl=5; the
current Microsim-based cli.py used to always emit CSV. This restores the
idtl=5 path by rendering result-DataFrame rows in TAXSIM's labeled
section format (Input Data / Basic Output / Federal Tax Calculation /
State Tax Calculation).
"""

import io

import pandas as pd
import pytest
from click.testing import CliRunner

from policyengine_taxsim.cli import cli


def _run_cli(input_csv: str):
    runner = CliRunner()
    result = runner.invoke(cli, [], input=input_csv)
    return result


def _record(idtl=5):
    return (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
        f"1,2024,5,1,40,0,0,50000,{idtl}\n"
    )


class TestIdtl5Format:
    def test_idtl5_input_emits_full_text(self):
        """idtl=5 input should produce labeled-section output, not CSV."""
        result = _run_cli(_record(idtl=5))
        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
        assert "Input Data:" in result.output
        assert "Basic Output:" in result.output
        assert "Federal Tax Calculation:" in result.output
        assert "State Tax Calculation:" in result.output

    def test_idtl5_does_not_emit_csv_header(self):
        """idtl=5 should not include a `taxsimid,year,state,fiitax,...`
        CSV header — that's the idtl=0/2 format."""
        result = _run_cli(_record(idtl=5))
        assert result.exit_code == 0
        # First non-empty line of CSV output would be the header. Check
        # that we don't see the recognizable "taxsimid,year,state,fiitax"
        # prefix in the labeled-section output.
        assert "taxsimid,year,state,fiitax" not in result.output

    def test_idtl2_input_still_emits_csv(self):
        """idtl=2 should retain the CSV format (regression guard)."""
        result = _run_cli(_record(idtl=2))
        assert result.exit_code == 0
        # CSV header present
        assert "taxsimid" in result.output
        assert "fiitax" in result.output
        # No labeled-section markers
        assert "Input Data:" not in result.output

    def test_idtl5_shows_federal_tax(self):
        """idtl=5 output should include the federal tax liability value."""
        result = _run_cli(_record(idtl=5))
        assert result.exit_code == 0
        # Should contain something like "Federal IIT Liability" or similar
        # label from variable_mappings.yaml's full_text_group definitions
        text = result.output.lower()
        assert "federal" in text and ("iit" in text or "income tax" in text)
