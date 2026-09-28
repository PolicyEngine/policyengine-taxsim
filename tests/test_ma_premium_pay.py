"""
MA's COVID-19 Essential Employee Premium Pay Program must stay out of siitax.

Chapter 102 of the Acts of 2021 funded $500-per-worker premium pay checks
mailed during 2022 to low-income essential workers (earnings above a minimum,
AGI under 300% of poverty). They were direct payments, never a Form 1 line,
so neither TAXSIM nor commercial software reports them. PolicyEngine models
the program as a 2021 person-level refundable credit
(ma_covid_19_essential_employee_premium_pay_program); the emulator zeroes it
so MA 2021 comparisons are not off by $500-1,000 per record — and so the
Chapter 62F rebate base (tax net of other refundable credits) is not
understated. See taxsim #1084.
"""

import io

import pandas as pd
from click.testing import CliRunner

from policyengine_taxsim.cli import cli

MA = 22


def _row(pwages: float, swages: float, intrec: float):
    record = (
        f"taxsimid,year,state,mstat,page,sage,depx,pwages,swages,intrec,idtl\n"
        f"1,2021,{MA},2,63,61,0,{pwages},{swages},{intrec},2\n"
    )
    result = CliRunner().invoke(cli, [], input=record)
    assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.exception}"
    out = result.output
    idx = out.find("taxsimid,")
    assert idx != -1, f"No CSV output:\n{out}"
    return pd.read_csv(io.StringIO(out[idx:])).iloc[0]


def test_ma_2021_excludes_premium_pay():
    """A 2021 MA joint filer with two qualifying essential workers must not
    receive the $1,000 (2 x $500) premium pay through siitax.

    From taxsim #1084: MFJ ages 63/61, ~$44K combined wages, ~$3.4K interest.
    With the payment included, siitax was 647.85 and the 62F rebate base was
    understated ($105.74 instead of $246.06); without it, tax before credits
    (~$1,753.58) splits into siitax plus the 62F srebate."""
    r = _row(pwages=20952.381, swages=23047.619, intrec=3437.6497)
    total = r["siitax"] + r["srebate"]
    assert abs(total - 1753.58) < 5, (
        f"siitax + srebate = {total}, expected ~1753.58 (tax before credits); "
        f"a gap of ~1000 means the premium pay is still included"
    )
    assert r["siitax"] > 1400, (
        f"siitax {r['siitax']} suggests the $1,000 premium pay is still "
        f"reducing MA state liability"
    )
