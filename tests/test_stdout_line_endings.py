"""Line endings of what the stdin drop-in command writes to stdout.

Python's text-mode stdout translates each "\\n" it is given into the
platform line separator (``os.linesep``), so every line the command writes
should end in exactly one ``os.linesep``: "\\r\\n" on Windows, "\\n"
elsewhere. CI runs this on windows-latest.
"""

import io
import os
import shutil
import subprocess

import pandas as pd
import pytest

HEADER = b"taxsimid,year,state,mstat,page,sage,depx,pwages,idtl\n"
# Pre-2021 records run only the TAXSIM binary, so the CLI returns quickly.
PRE_2021_RECORD = b"1,2019,5,1,40,0,0,50000,%d\n"


def _results_block(stdout):
    """stdout after the TAXSIM progress lines that can precede the results."""
    marker = stdout.find(b"TAXSIM completed successfully")
    if marker < 0:
        return stdout
    return stdout[stdout.index(b"\n", marker) + 1 :]


@pytest.mark.parametrize("idtl", [2, 5], ids=["csv", "idtl5-text"])
def test_console_script_lines_end_in_one_line_separator(idtl):
    cli = shutil.which("policyengine-taxsim")
    assert cli is not None, "policyengine-taxsim console script not installed"

    process = subprocess.run(
        [cli],
        input=HEADER + PRE_2021_RECORD % idtl,
        capture_output=True,
        timeout=600,
    )

    assert process.returncode == 0, process.stderr.decode(errors="replace")
    stdout = process.stdout
    block = _results_block(stdout)
    separator = os.linesep.encode()
    lines = block.split(separator)
    assert b"\r\r\n" not in block, f"os.linesep={os.linesep!r} stdout={stdout!r}"
    assert lines[-1] == b"", f"output does not end in os.linesep: {stdout!r}"
    assert not any(b"\r" in line or b"\n" in line for line in lines), (
        f"a line ends in something other than os.linesep={os.linesep!r}: {stdout!r}"
    )
    if idtl == 2:
        result = pd.read_csv(io.BytesIO(block))
        assert result["taxsimid"].tolist() == [1]
        assert result["year"].tolist() == [2019]
    else:
        assert b"Input Data:" in block
