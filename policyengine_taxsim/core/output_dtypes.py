"""Number types of the output table.

PolicyEngine computes in 32-bit floating point, and a 32-bit float cannot hold
most amounts in cents exactly: the nearest one to 4009.20 is
4009.199951171875. Rounding in 32 bits leaves that value in place, and it shows
as soon as the column widens to 64 bits, which is what pandas does when
StitchedRunner joins PolicyEngine rows to the TAXSIM binary's 64-bit rows.
Amounts are therefore widened to 64 bits first and rounded there, so every
amount is the 64-bit float nearest to a whole number of cents.

The TAXSIM binary prints the record ID with a trailing decimal point ("1."),
which parses as a float, so the identifier columns are returned as integers
whenever their values are whole numbers.
"""

import numpy as np
import pandas as pd

# Columns that identify a record rather than measure it.
IDENTIFIER_COLUMNS = ("taxsimid", "year", "state")

# A float at or beyond 2**63 has no int64 equivalent.
_INT64_LIMIT = 2.0**63


def round_float64(values, decimals: int = 2) -> np.ndarray:
    """Round to ``decimals`` places in 64-bit floating point.

    The result is always float64, whatever the input's precision.
    """
    return np.round(np.asarray(values, dtype=np.float64), decimals)


def identifiers_as_integers(df: pd.DataFrame) -> pd.DataFrame:
    """Store whole-number float identifier columns of ``df`` as int64.

    Converts in place and returns ``df``. A column that holds a fraction or a
    missing value stays a float, and a column that is already an integer type
    is left alone, so no value ever changes; only the type does.
    """
    for column in IDENTIFIER_COLUMNS:
        if column not in df.columns:
            continue
        if not pd.api.types.is_float_dtype(df[column].dtype):
            continue
        values = df[column].to_numpy(dtype=np.float64, na_value=np.nan)
        if not np.isfinite(values).all():
            continue
        if (np.abs(values) >= _INT64_LIMIT).any():
            continue
        if (values != np.trunc(values)).any():
            continue
        df[column] = values.astype(np.int64)
    return df
