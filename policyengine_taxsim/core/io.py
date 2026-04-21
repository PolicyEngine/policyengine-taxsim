"""File I/O helpers supporting CSV and Stata (.dta) formats.

Format is auto-detected from file extensions:
  .dta  → Stata
  anything else → CSV (the default)
"""

import pandas as pd
from pathlib import Path
from typing import Union

STATA_EXTENSIONS = {".dta"}


def _is_stata(path: Union[str, Path]) -> bool:
    return Path(path).suffix.lower() in STATA_EXTENSIONS


def read_input(path: Union[str, Path]) -> pd.DataFrame:
    """Read a TAXSIM-format input file (CSV or Stata)."""
    if _is_stata(path):
        return pd.read_stata(path)
    return pd.read_csv(path)


def write_output(
    df: pd.DataFrame,
    path: Union[str, Path],
    index: bool = False,
) -> None:
    """Write a DataFrame to CSV or Stata based on file extension."""
    if _is_stata(path):
        df.to_stata(path, write_index=index)
    else:
        df.to_csv(path, index=index)
