"""State code guards: every state survives conversion, and TAXSIM state 0
("no state tax") is never reported as Texas.

The eCPS comparison inputs (cps_households.csv) were built by a converter whose
FIPS table omitted Alabama and defaulted to 0, so all Alabama households were
scored without state income tax and reported under TX.
"""

import csv
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.comparison.statistics import ComparisonStatistics
from policyengine_taxsim.core.text_formatter import format_row
from policyengine_taxsim.core.utils import (
    NO_STATE_LABEL,
    SOI_TO_FIPS_MAP,
    STATE_MAPPING,
    get_calculation_fips,
    get_calculation_state_code,
    get_state_code,
    get_state_label,
    get_state_number,
    validate_state_number,
)
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

ROOT = Path(__file__).parents[1]

spec = importlib.util.spec_from_file_location(
    "convert_h5_to_taxsim", ROOT / "scripts/convert_h5_to_taxsim.py"
)
convert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(convert)

ALL_SOI = set(range(1, 52))


class _Result:
    def __init__(self, values):
        self.values = np.asarray(values)


class FakeSim:
    """One single-adult household per state, in FIPS order."""

    def __init__(self, fips_codes):
        n = len(fips_codes)
        ids = np.arange(1, n + 1)
        zeros = np.zeros(n)
        self.arrays = {
            "person_tax_unit_id": ids,
            "tax_unit_id": ids,
            "person_household_id": ids,
            "household_id": ids,
            "state_fips": np.asarray(fips_codes),
            "household_weight": np.ones(n),
            "age": np.full(n, 40),
            "is_tax_unit_head": np.ones(n, dtype=bool),
            "is_tax_unit_spouse": np.zeros(n, dtype=bool),
            "is_tax_unit_dependent": np.zeros(n, dtype=bool),
            "employment_income": np.full(n, 50_000.0),
        }
        self.zeros = zeros

    def calculate(self, variable, period):
        return _Result(self.arrays.get(variable, self.zeros))


def test_fips_table_is_inverse_of_soi_table():
    assert convert.FIPS_TO_SOI == {fips: soi for soi, fips in SOI_TO_FIPS_MAP.items()}
    assert set(convert.FIPS_TO_SOI.values()) == ALL_SOI
    assert set(SOI_TO_FIPS_MAP) == set(STATE_MAPPING) == ALL_SOI


def test_conversion_output_contains_every_state():
    fips_codes = sorted(SOI_TO_FIPS_MAP.values())
    df = convert.extract_taxsim_csv(FakeSim(fips_codes), 2024)
    assert len(df) == 51
    assert set(df["state"]) == ALL_SOI
    for fips, state in zip(fips_codes, df.sort_values("taxsimid")["state"]):
        assert SOI_TO_FIPS_MAP[state] == fips
    # Alabama is FIPS 1 and SOI 1, the entry the original converter lacked.
    assert df.loc[df["taxsimid"] == 1, "state"].item() == 1


@pytest.mark.parametrize("fips", [0, 3, 72])
def test_conversion_rejects_unknown_fips(fips):
    with pytest.raises(ValueError, match="No TAXSIM state code"):
        convert.extract_taxsim_csv(FakeSim([1, fips]), 2024)


def test_checked_in_ecps_inputs_cover_every_state():
    with (ROOT / "cps_households.csv").open(newline="") as f:
        states = [int(float(row["state"])) for row in csv.DictReader(f)]
    assert len(states) == 111_347
    assert set(states) == ALL_SOI
    assert states.count(0) == 0
    assert states.count(1) == 1_155  # Alabama, formerly mislabeled state 0


# taxsimtest build cd2026081819, idtl=2: a single filer aged 40 with $60,000
# of 2024 wages owes $5,216.00 federal tax and $0 state tax with state 0,
# and TAXSIM echoes state 0. Its idtl=5 text prints "State not specified".
TAXSIM_STATE0_FIITAX = 5216.00


def _single_filer(**overrides):
    return {
        "taxsimid": 1,
        "year": 2024,
        "state": 0,
        "mstat": 1,
        "page": 40,
        "pwages": 60000,
        "idtl": 2,
        **overrides,
    }


@pytest.mark.parametrize("number", range(52))
def test_state_numbers_round_trip(number):
    assert get_state_number(get_state_code(number)) == number


def test_state_zero_is_no_state_not_texas():
    assert get_state_code(0) is None
    assert get_state_label(0) == NO_STATE_LABEL == "State not specified"
    assert get_state_code(44) == get_state_label(44) == "TX"
    assert get_state_code(1) == "AL"
    # PolicyEngine still simulates Texas, which has no individual income tax.
    assert get_calculation_state_code(0) == "TX"
    assert get_calculation_fips(0) == 48
    assert get_calculation_fips(1) == 1


@pytest.mark.parametrize("missing", [None, float("nan"), np.nan, "", " "])
def test_missing_state_is_state_zero(missing):
    assert validate_state_number(missing) == 0


@pytest.mark.parametrize("value", [52, 99, -2, -1, 0.5, "XX"])
def test_invalid_state_numbers_raise(value):
    for convert_state in (get_state_code, get_calculation_state_code):
        with pytest.raises(ValueError):
            convert_state(value)
    with pytest.raises(ValueError):
        get_calculation_fips(value)


def test_state_numbers_accept_numeric_types():
    assert validate_state_number(5.0) == validate_state_number(np.int64(5)) == 5
    assert validate_state_number("44") == 44


def test_unknown_postal_code_raises():
    assert get_state_number("tx") == 44
    assert get_state_number(None) == 0
    with pytest.raises(ValueError):
        get_state_number("XX")


def test_state_breakdown_keeps_state_zero_out_of_texas():
    results = SimpleNamespace(federal_mismatches=[], state_mismatches=[])
    input_data = pd.DataFrame({"state": [0, 0, 0, 44, 44]})
    breakdown = ComparisonStatistics(results, input_data).state_breakdown()
    assert breakdown["TX"]["total_households"] == 2
    assert breakdown[NO_STATE_LABEL]["total_households"] == 3


def test_text_output_labels_state_zero_as_not_specified():
    text = format_row(
        _single_filer(idtl=5),
        {"taxsimid": 1, "fiitax": TAXSIM_STATE0_FIITAX, "siitax": 0.0},
    )
    state_lines = [line for line in text.splitlines() if "State" in line]
    assert any(NO_STATE_LABEL in line for line in state_lines)
    assert not any(line.rstrip().endswith("TX") for line in text.splitlines())


def test_microsim_runner_echoes_state_zero():
    records = pd.DataFrame([_single_filer(), _single_filer(taxsimid=2, state=44)])
    output = PolicyEngineRunner(records).run(show_progress=False).set_index("taxsimid")
    assert output.loc[1, "state"] == 0
    assert output.loc[2, "state"] == 44
    assert output.loc[1, "siitax"] == 0
    assert output.loc[1, "fiitax"] == pytest.approx(TAXSIM_STATE0_FIITAX, abs=1)


def test_microsim_runner_treats_missing_state_as_zero():
    record = _single_filer()
    del record["state"]
    output = PolicyEngineRunner(pd.DataFrame([record])).run(show_progress=False)
    assert output["state"].tolist() == [0]
    assert output["siitax"].tolist() == [0]


@pytest.mark.parametrize("state", [52, -1, 0.5])
def test_microsim_runner_rejects_invalid_state(state):
    # TAXSIM aborts the run; the runner used to simulate California as TX.
    with pytest.raises(ValueError, match="Record 1"):
        PolicyEngineRunner(pd.DataFrame([_single_filer(state=state)]))


def test_single_household_path_echoes_state_zero():
    taxsim = _single_filer()
    output = export_household(taxsim, generate_household(dict(taxsim)), False, False)
    assert output["state"] == 0
    assert output["siitax"] == 0
    assert output["fiitax"] == pytest.approx(TAXSIM_STATE0_FIITAX, abs=1)

    text_input = _single_filer(idtl=5)
    text = export_household(
        text_input, generate_household(dict(text_input)), False, False
    )
    assert NO_STATE_LABEL in text
    assert not any(line.rstrip().endswith("TX") for line in text.splitlines())


def test_single_household_path_rejects_invalid_state():
    with pytest.raises(ValueError, match="not a valid TAXSIM SOI state code"):
        generate_household(_single_filer(state=52))
