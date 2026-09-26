"""
Tests for resources/taxsimtest/taxsim-docker-wrapper.sh, which runs the
bundled Linux taxsimtest binary through Docker (see
resources/taxsimtest/README.md).

The wrapper used to bind-mount a hard-coded path under one developer's home
directory (to a binary since deleted), so everywhere else Docker mounted an
empty directory and the run failed with exit 126. Its image also lacked the
gfortran runtime the Linux build links against.
"""

import csv
import io
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

TAXSIMTEST_DIR = Path(__file__).resolve().parent.parent / "resources" / "taxsimtest"
WRAPPER = TAXSIMTEST_DIR / "taxsim-docker-wrapper.sh"

# The README's canonical probe: VA 2021 with opt(30), whose $500 rebate is
# booked in-year only by current builds (expect siitax 2068.05, srebate 500).
VA21_OPT30 = (
    "taxsimid year state mstat page sage depx pwages idtl opt1 opt1v\n"
    "1 2021 47 2 45 45 0 60000 2 30 1\n"
)

TY2025 = (
    "taxsimid,year,state,mstat,page,sage,depx,age1,age2,pwages,swages,"
    "dividends,intrec,ltcg,otherprop,pensions,gssi,idtl\n"
    "1,2025,33,1,45,0,0,0,0,75000,0,0,0,0,0,0,0,2\n"
    "2,2025,5,2,40,38,2,5,10,120000,40000,3000,1500,0,0,0,0,2\n"
    "3,2025,47,2,68,66,0,0,0,0,0,2000,4000,0,0,40000,30000,2\n"
    "4,2025,0,1,40,0,0,0,0,15000,0,0,0,0,-12000,0,0,2\n"
)


def _docker_available():
    if platform.system() == "Windows":
        return False  # bash wrapper; Windows runners use Windows containers
    if shutil.which("docker") is None or shutil.which("bash") is None:
        return False
    try:
        info = subprocess.run(["docker", "info"], capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False
    return info.returncode == 0


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason="needs bash and a running Docker daemon"
)


def _run_wrapper(stdin, cwd):
    # Generous timeout: the first run builds the image (apt-get install).
    result = subprocess.run(
        ["bash", str(WRAPPER)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=900,
    )
    assert result.returncode == 0, (
        f"wrapper exited {result.returncode}\nstderr:\n{result.stderr}"
    )
    return result.stdout


def _rows(output):
    return list(csv.DictReader(io.StringIO(output)))


def test_wrapper_resolves_binary_next_to_itself():
    """No machine-specific absolute paths: the binary and Dockerfile are
    found relative to the script, and the Dockerfile they name exists."""
    text = WRAPPER.read_text()
    assert "/Users/" not in text and "/home/" not in text
    assert "$here/taxsimtest-linux.exe" in text
    assert "$here/taxsimtest-linux.Dockerfile" in text
    assert (TAXSIMTEST_DIR / "taxsimtest-linux.Dockerfile").exists()


def test_dockerfile_installs_gfortran_runtime():
    """The Linux build needs libgfortran.so.5 and libquadmath.so.0, which the
    bare ubuntu/debian images lack (exit 127)."""
    text = (TAXSIMTEST_DIR / "taxsimtest-linux.Dockerfile").read_text()
    assert "libgfortran5" in text
    assert "libquadmath0" in text


@requires_docker
def test_wrapper_runs_va21_opt30_probe(tmp_path):
    """The README's probe, run from an unrelated working directory."""
    (row,) = _rows(_run_wrapper(VA21_OPT30, cwd=tmp_path))
    assert float(row["siitax"]) == pytest.approx(2068.05)
    assert float(row["srebate"]) == pytest.approx(500.0)


@requires_docker
@pytest.mark.skipif(
    platform.system() != "Linux", reason="compares against running it natively"
)
def test_wrapper_matches_native_linux_run(tmp_path):
    """On Linux the same binary runs natively, so the containerized output
    must be byte-identical."""
    native = subprocess.run(
        [str(TAXSIMTEST_DIR / "taxsimtest-linux.exe")],
        input=TY2025,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert native.returncode == 0, native.stderr
    assert _run_wrapper(TY2025, cwd=tmp_path) == native.stdout
    assert len(_rows(native.stdout)) == 4
