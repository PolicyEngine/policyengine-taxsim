"""Delaware combined-separate `staxbc` follows the elected filing path.

Delaware lets a married couple file "combined separate" (Filing Status 4),
taxing each spouse's income in its own column. PolicyEngine elects that path
when it is cheaper after credits. The variable `staxbc` maps to for DE,
``de_income_tax_before_non_refundable_credits_unit``, always reflects the
joint single-column computation (it must, to cap non-refundable credits and
drive the election without a circular dependency). Before this fix the
reported "tax before credits" therefore showed the joint figure even when the
combined-separate election was used. It should instead be the sum of the two
per-column liabilities. See taxsim #1146.
"""

import pandas as pd

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


# taxsim #1146: DE joint, ages 37/35, 1 dependent, $157,143 + $10,057 wages,
# $2,930 interest, $29,883 child care, $2,204 property tax. PolicyEngine
# elects combined separate; TaxAct's PIT-RES shows the two columns' tax as
# $194 + $9,237 = $9,431, versus a joint single-column pre-credit tax of
# $9,783. staxbc is only emitted at idtl >= 5.
DE_COMBINED_SEPARATE = {
    "taxsimid": 1,
    "year": 2022,
    "state": 8,  # DE
    "mstat": 2,
    "page": 37,
    "sage": 35,
    "depx": 1,
    "pwages": 157142.86,
    "swages": 10057.143,
    "intrec": 2930.4197,
    "proptax": 2203.6172,
    "childcare": 29882.531,
    "idtl": 5,
}

DE_SINGLE = {
    "taxsimid": 2,
    "year": 2022,
    "state": 8,  # DE
    "mstat": 1,
    "page": 40,
    "sage": 0,
    "depx": 0,
    "pwages": 80_000,
    "idtl": 5,
}


def _run(record):
    return PolicyEngineRunner(
        pd.DataFrame([record]), logs=False, disable_salt=False
    ).run(show_progress=False)


def test_de_staxbc_reports_elected_combined_separate_path():
    result = _run(DE_COMBINED_SEPARATE)
    staxbc = float(result["staxbc"].iloc[0])
    siitax = float(result["siitax"].iloc[0])
    # PE elects combined separate here, so the tax before credits is the two
    # per-column liabilities summed (~$9,431), not the joint figure (~$9,783).
    assert 9200 < staxbc < 9600, (
        f"DE combined-separate staxbc {staxbc} should be the summed per-column "
        "tax (~9,431), not the joint single-column figure (~9,783)"
    )
    # Liability after credits cannot exceed the tax before credits.
    assert siitax <= staxbc + 0.01


def test_de_single_filer_staxbc_unaffected():
    """A single filer never elects combined separate, so staxbc stays the
    ordinary single-column tax before credits."""
    result = _run(DE_SINGLE)
    staxbc = float(result["staxbc"].iloc[0])
    siitax = float(result["siitax"].iloc[0])
    assert staxbc > 0
    assert siitax <= staxbc + 0.01
