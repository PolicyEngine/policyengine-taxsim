"""Opt-in real CLI/HTTP/TAXSIM checks; run on a hosted runner, not by default."""

import csv
import io
import json
import os
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SCORP_E2E") != "1", reason="Hosted end-to-end suite"
)

INPUT = """taxsimid,year,state,mstat,page,sage,depx,pwages,intrec,scorp,idtl
1,2025,0,1,45,0,0,0,0,150000,2
2,2025,0,1,45,0,0,0,0,200000,2
3,2025,0,2,45,45,0,0,0,300000,2
4,2025,0,1,45,0,0,300000,150000,-100000,2
5,2025,0,1,45,0,0,100000,0,0,2
"""


def parse(text):
    return {int(float(r["taxsimid"])): r for r in csv.DictReader(io.StringIO(text))}


@pytest.fixture(scope="module")
def comparator():
    import pandas as pd
    from policyengine_taxsim.runners.taxsim_runner import TaxsimRunner

    return parse(
        TaxsimRunner(pd.read_csv(io.StringIO(INPUT)))
        .run(show_progress=False)
        .to_csv(index=False)
    )


def verify(text, expected, mode):
    rows = parse(text)
    assert rows.keys() == expected.keys()
    for key, row in rows.items():
        # Positive scorp adds $1,900 NIIT in case 3; signed loss offsets
        # $3,800 NIIT in case 4. Other federal treatment stays the same.
        delta = {3: -1900, 4: 3800}.get(key, 0) if mode == "active" else 0
        assert float(row["niit"]) == pytest.approx(
            float(expected[key]["niit"]) + delta, abs=1
        )
        assert float(row["fiitax"]) == pytest.approx(
            float(expected[key]["fiitax"]) + delta, abs=1
        )
        for field in ("qbid", "v10"):
            assert float(row[field]) == pytest.approx(
                float(expected[key][field]), abs=1
            )
        # Keep this independent discrepancy explicit: the bundled TAXSIM
        # reports 39,118.20 FICA on $300k wages; PE reports 31,436.40.
        # The $7,681.80 gap is .062 * (300000 - 176100), consistent with
        # an uncapped employer SS component in TAXSIM. NIIT mode must not
        # be used to conceal or compensate for this payroll discrepancy.
        known_fica_gap = 7681.80 if key == 4 else 0
        assert float(row["fica"]) == pytest.approx(
            float(expected[key]["fica"]) - known_fica_gap, abs=1
        )


@pytest.mark.parametrize("mode", ["passive", "active"])
def test_real_cli(mode, comparator, tmp_path):
    input_file, output_file = tmp_path / "input.csv", tmp_path / "output.csv"
    input_file.write_text(INPUT)
    result = subprocess.run(
        [
            "policyengine-taxsim",
            "policyengine",
            str(input_file),
            "--scorp-treatment",
            mode,
            "-o",
            str(output_file),
        ],
        text=True,
        capture_output=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    verify(output_file.read_text(), comparator, mode)


def test_stdin_default_is_passive(comparator):
    result = subprocess.run(
        ["policyengine-taxsim"],
        input=INPUT,
        text=True,
        capture_output=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    verify(result.stdout, comparator, "passive")


@pytest.mark.parametrize(
    "stream,mode", [(False, "passive"), (False, "active"), (True, "active")]
)
def test_real_http(stream, mode, comparator):
    from fastapi.testclient import TestClient
    from policyengine_taxsim.api import _build_local_app

    payload = {"csv": INPUT, "idtl": 2}
    if mode == "active":
        payload["scorp_treatment"] = mode
    with TestClient(_build_local_app()) as client:
        response = client.post("/run/stream" if stream else "/run", json=payload)
        assert response.status_code == 200, response.text
        if stream:
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            assert not any(e["type"] == "error" for e in events), events
            result = next(e for e in events if e["type"] == "result")
        else:
            result = response.json()
        assert result["rows_processed"] == 5
        verify(result["csv"], comparator, mode)
        assert (
            client.post("/run", json={**payload, "scorp_treatment": "typo"}).status_code
            == 422
        )
