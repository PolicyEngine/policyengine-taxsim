"""Massachusetts v36 (taxable income) in both emulator execution paths.

TAXSIM reports Massachusetts v36 as the sum of Part A, Part B and Part C
taxable income after deductions and exemptions; the emulator used to report 0
(taxsim #1382).

Expected values are external:
- Rows 1-3: TAXSIM-35 output, identical in the October 8 and October 19, 2026
  executables (single 60,000 wages: 60,000 - 2,000 FICA deduction - 4,400
  exemption = 53,600).
- Row 6: Dan Feenberg's TaxAct 2024 Form 1 for taxsim #1382 row 6
  (http://taxsim.nber.org/out2psl/1382): line 19 "5.0% income after
  exemptions" 1,381,200 and line 28 total tax 82,158.
"""

import pandas as pd
import pytest

from policyengine_taxsim import export_household, generate_household
from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner

MA = 22

CASES = [
    # (input, expected v36, expected siitax)
    (
        {
            "taxsimid": 1,
            "year": 2024,
            "state": MA,
            "mstat": 1,
            "page": 40,
            "pwages": 60_000.0,
        },
        53_600.0,
        2_680.0,
    ),
    (
        {
            "taxsimid": 2,
            "year": 2024,
            "state": MA,
            "mstat": 2,
            "page": 40,
            "sage": 40,
            "pwages": 60_000.0,
            "swages": 40_000.0,
        },
        87_200.0,
        4_360.0,
    ),
    (
        {
            "taxsimid": 3,
            "year": 2024,
            "state": MA,
            "mstat": 1,
            "page": 40,
            "pwages": 60_000.0,
            "dividends": 5_000.0,
            "ltcg": 20_000.0,
            "stcg": 3_000.0,
        },
        81_600.0,
        4_185.0,
    ),
    (
        {
            "taxsimid": 6,
            "year": 2024,
            "state": MA,
            "mstat": 2,
            "page": 50,
            "sage": 50,
            "intrec": 2_000_000.0,
            "scorp": -1_000_000.0,
        },
        1_381_200.0,
        82_158.0,
    ),
]


def _row(taxsim_input):
    return {**taxsim_input, "idtl": 2, "opt1": 30, "opt1v": 1}


@pytest.fixture(scope="module")
def runner_output():
    df = pd.DataFrame([_row(case) for case, _, _ in CASES])
    result = PolicyEngineRunner(df, logs=False, disable_salt=False).run(
        show_progress=False
    )
    return result.set_index(result.taxsimid.astype(int))


@pytest.mark.parametrize(("taxsim_input", "v36", "siitax"), CASES)
def test_ma_v36_batch_path(runner_output, taxsim_input, v36, siitax):
    row = runner_output.loc[taxsim_input["taxsimid"]]
    assert float(row["v36"]) == pytest.approx(v36, abs=0.01)
    assert float(row["siitax"]) == pytest.approx(siitax, abs=0.01)


@pytest.mark.parametrize(("taxsim_input", "v36", "siitax"), CASES)
def test_ma_v36_single_household_path(taxsim_input, v36, siitax):
    taxsim_input = _row(taxsim_input)
    situation = generate_household(dict(taxsim_input))
    result = export_household(taxsim_input, situation, False, False)
    assert float(result["v36"]) == pytest.approx(v36, abs=0.01)
    assert float(result["siitax"]) == pytest.approx(siitax, abs=0.01)
