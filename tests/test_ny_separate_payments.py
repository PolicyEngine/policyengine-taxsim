"""
New York separate-payment parity with TAXSIM.

The Additional Empire State child credit payment and the New York inflation
refund are separate checks, not lines on Form IT-201. TAXSIM's siitax excludes
both. PolicyEngine models them as refundable credits booked to the return year,
so the emulator zeros them (NY is SOI code 33) so siitax and the state child
credit (sctc) match TAXSIM's return-based figures. See taxsim #1154.

Reproduces the #1154 record: NY joint 2023, one child, $14,667 wages,
$6,794 property tax. TaxAct's IT-201 shows Empire State child credit $330
(line 63) and a $1,529 refund; without the fix PolicyEngine reports sctc
$577.50 (330 + $247.50 additional payment) and siitax -$2,223 (also including
the $400 inflation refund).
"""

import pandas as pd

from policyengine_taxsim.runners.policyengine_runner import PolicyEngineRunner


def _run_1154():
    columns = (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,psemp,swages,ssemp,"
        "dividends,intrec,stcg,ltcg,otherprop,nonprop,pensions,gssi,pui,sui,"
        "transfers,rentpaid,proptax,otheritem,childcare,mortgage,scorp,idtl"
    ).split(",")
    values = [
        5024033,
        2023,
        33,
        2,
        43,
        49,
        1,
        14666.667,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        6794.4863,
        0,
        0,
        0,
        0,
        5,
    ]
    df = pd.DataFrame([dict(zip(columns, values))])
    return PolicyEngineRunner(df, logs=False).run(show_progress=False).iloc[0]


def test_ny_sctc_excludes_additional_esc_payment():
    """sctc should be the Empire State child credit alone ($330), not the
    $577.50 that includes the separate Additional ESC payment."""
    row = _run_1154()
    assert abs(row["sctc"] - 330) < 1, (
        f"NY sctc {row['sctc']} should be the $330 Empire State child credit, "
        "not include the separate Additional ESC payment"
    )


def test_ny_siitax_excludes_separate_payments():
    """siitax should exclude the Additional ESC payment ($247.50) and the
    inflation refund ($400), which are separate checks not on Form IT-201."""
    row = _run_1154()
    # ESCC 330 + NY EITC 1198.5 = 1528.5 of refundable credits; PolicyEngine
    # additionally grants a $47 real property tax credit here (a separate
    # difference), so siitax is about -1575.5, not the pre-fix -2223.
    assert -1600 < row["siitax"] < -1550, (
        f"NY siitax {row['siitax']} looks like it still includes the "
        "Additional ESC payment and/or inflation refund (expected ~ -1575.5)"
    )


def _run_1185():
    """taxsim #1185: NY head-of-household 2021, one child (age 10), $24,097.71
    wages, $1,524.17 property tax. TaxAct's return shows NY earned income
    credit $807 (IT-215 line 16 = 30% x recomputed federal EIC $2,890 - $60
    household credit) and Empire State child credit $330 (IT-213 line 16 =
    33% x the $1,000 2017-law federal CTC). Without the fix PolicyEngine adds
    the $721.62 supplemental EIC payment (25% of the federal EITC) into v39 and
    the $247.50 Additional ESC payment into sctc -- both fall-2022 separate
    checks not on the 2021 return."""
    columns = (
        "taxsimid,year,state,mstat,page,sage,depx,pwages,psemp,swages,ssemp,"
        "dividends,intrec,stcg,ltcg,otherprop,nonprop,pensions,gssi,pui,sui,"
        "transfers,rentpaid,proptax,otheritem,childcare,mortgage,scorp,idtl"
    ).split(",")
    values = [
        9326633,
        2021,
        33,
        1,
        24,
        0,
        1,
        24097.709,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1524.1686,
        0,
        0,
        0,
        0,
        5,
    ]
    df = pd.DataFrame([dict(zip(columns, values))])
    return PolicyEngineRunner(df, logs=False).run(show_progress=False).iloc[0]


def test_ny_v39_excludes_supplemental_eic_payment():
    """v39 (state EITC) should be the NY earned income credit alone (TaxAct
    IT-215 line 16 = $807), not include the ~$721.62 supplemental EIC payment
    that would push it toward $1,508."""
    row = _run_1185()
    assert row["v39"] < 900, (
        f"NY v39 {row['v39']} should be the ~$807 NY earned income credit, "
        "not include the separate supplemental EIC payment"
    )


def test_ny_2021_siitax_excludes_supplemental_payments():
    """siitax should exclude the supplemental EIC payment ($721.62) and the
    Additional ESC payment ($247.50), separate 2021 checks not on Form IT-201.
    With both removed the refund is ~-$700.73, not the pre-fix -$1,669.85."""
    row = _run_1185()
    assert -750 < row["siitax"] < -650, (
        f"NY 2021 siitax {row['siitax']} looks like it still includes the "
        "supplemental EIC and/or Additional ESC payment (expected ~ -700.73)"
    )
