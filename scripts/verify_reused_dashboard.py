"""Verify completed dashboard artifacts without loading CSVs into memory."""

import json
from pathlib import Path
import sys

from refresh_dashboard import ROOT, EXPECTED_RECORDS, digest


def verify(year, directory):
    if year not in (2021, 2022, 2023):
        raise ValueError("Only unaffected 2021–2023 results can be reused")
    full = directory / "full"
    provenance = json.loads((full / f"provenance_{year}.json").read_text())
    summary = json.loads((directory / f"site/{year}/summary_{year}.json").read_text())
    expected = {
        "year": year,
        "sourceSha256": digest(ROOT / "cps_households.csv"),
        "requirementsSha256": digest(
            ROOT / "scripts/dashboard-refresh-requirements.txt"
        ),
        "taxsimBinarySha256": digest(
            ROOT / "resources/taxsimtest/taxsimtest-linux.exe"
        ),
        "emulatorCommit": "c245a3eb92e412bc2beb5b0ffaf909ecc36d7a18",
        "policyengineUsVersion": "2.6.17",
        "assumeW2Wages": True,
        "disableSalt": False,
        "policyengineOutputDetail": 5,
        "limit": 0,
    }
    for key, value in expected.items():
        if provenance.get(key) != value or summary["metadata"].get(key) != value:
            raise ValueError(f"Incompatible reused provenance: {key}")
    if (
        provenance.get("records") != EXPECTED_RECORDS
        or summary["totalRecords"] != EXPECTED_RECORDS
    ):
        raise ValueError("Incomplete reused population")
    if (
        len(summary["stateBreakdown"]) != 51
        or sum(s["households"] for s in summary["stateBreakdown"]) != EXPECTED_RECORDS
    ):
        raise ValueError("Incomplete state coverage")
    if digest(full / f"comparison_results_{year}.csv") != provenance["outputSha256"]:
        raise ValueError("Reused CSV checksum mismatch")
    print(
        f"Verified {year}: {EXPECTED_RECORDS} households; original artifacts and provenance preserved"
    )


if __name__ == "__main__":
    verify(int(sys.argv[1]), Path(sys.argv[2]))
