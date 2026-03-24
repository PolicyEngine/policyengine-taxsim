"""Runner that submits CSV to NBER's hosted TAXSIM-35 web service."""

import logging
import pandas as pd
from io import StringIO

from .base_runner import BaseTaxRunner
from ..core.utils import convert_taxsim32_dependents

logger = logging.getLogger(__name__)

TAXSIM_URL = "https://taxsim.nber.org/taxsim35/redirect.cgi"

# Max records per HTTP request (NBER recommends ~2000)
BATCH_SIZE = 2000


class RemoteTaxsimRunner(BaseTaxRunner):
    """Submits CSV to NBER's TAXSIM-35 web service via HTTP POST."""

    REQUIRED_COLUMNS = [
        "taxsimid",
        "year",
        "state",
        "mstat",
        "page",
        "sage",
        "depx",
    ]

    DEPENDENT_AGE_COLUMNS = [f"age{i}" for i in range(1, 12)]

    INCOME_COLUMNS = [
        "pwages",
        "swages",
        "psemp",
        "ssemp",
        "dividends",
        "intrec",
        "stcg",
        "ltcg",
        "otherprop",
        "nonprop",
        "pensions",
        "gssi",
        "pui",
        "sui",
        "transfers",
        "rentpaid",
        "proptax",
        "otheritem",
        "childcare",
        "mortgage",
        "scorp",
        "idtl",
    ]

    ALL_COLUMNS = REQUIRED_COLUMNS + DEPENDENT_AGE_COLUMNS + INCOME_COLUMNS

    def __init__(self, input_df: pd.DataFrame):
        super().__init__(input_df)

    def _format_input(self, df: pd.DataFrame) -> str:
        """Format DataFrame as CSV text for TAXSIM submission."""
        formatted_df = df.copy()

        # Convert TAXSIM32 format to individual ages
        for idx, row in formatted_df.iterrows():
            row_dict = row.to_dict()
            converted_row = convert_taxsim32_dependents(row_dict)
            for key, value in converted_row.items():
                formatted_df.loc[idx, key] = value

        # Ensure all columns exist with default values
        for col in self.ALL_COLUMNS:
            if col not in formatted_df.columns:
                formatted_df[col] = 0

        # Determine max dependents across all rows to set consistent columns
        max_depx = (
            int(formatted_df["depx"].max()) if "depx" in formatted_df.columns else 0
        )
        max_depx = min(max_depx, 11)

        # Build consistent column list
        columns = list(self.REQUIRED_COLUMNS)
        for i in range(max_depx):
            columns.append(f"age{i + 1}")
        columns.extend(self.INCOME_COLUMNS)

        # Build CSV
        lines = [",".join(columns)]

        for _, row in formatted_df.iterrows():
            depx = int(row.get("depx", 0))
            values = []
            for col in columns:
                val = row.get(col, 0)
                if pd.isna(val):
                    val = 0
                # For age columns: set to 10 only if this row has that dependent
                if col.startswith("age") and col[3:].isdigit():
                    age_idx = int(col[3:])
                    if age_idx > depx:
                        # This row doesn't have this dependent — must be 0
                        val = 0
                    elif float(val) <= 0:
                        # Has dependent but no age specified — default to 10
                        val = 10
                values.append(str(val))
            lines.append(",".join(values))

        return "\n".join(lines) + "\n"

    def _submit_to_taxsim(self, csv_text: str) -> str:
        """POST CSV to NBER's TAXSIM-35 endpoint, return response text."""
        import urllib.request

        # Multipart form data with field name "txpydata.raw"
        boundary = "----TaxsimBoundary"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="txpydata.raw"; '
            f'filename="txpydata.raw"\r\n'
            f"Content-Type: text/plain\r\n"
            f"\r\n"
            f"{csv_text}"
            f"\r\n--{boundary}--\r\n"
        )

        req = urllib.request.Request(
            TAXSIM_URL,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        resp = urllib.request.urlopen(req, timeout=300)
        return resp.read().decode("utf-8")

    def _parse_response(self, response_text: str) -> pd.DataFrame:
        """Parse TAXSIM response CSV into a DataFrame."""
        lines = response_text.strip().split("\n")

        # Filter out TAXSIM diagnostic lines, error messages, and blank lines
        csv_lines = []
        errors = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("TAXSIM:") or stripped.startswith(" TAXSIM:"):
                if "Abandoning" in stripped or "error" in stripped.lower():
                    errors.append(stripped)
                continue
            if stripped.startswith("STOP") or stripped.startswith("*"):
                continue
            if "," in stripped:
                csv_lines.append(stripped)

        if errors and not csv_lines:
            raise ValueError(f"TAXSIM-35 returned errors: {'; '.join(errors)}")

        if not csv_lines:
            raise ValueError(
                f"TAXSIM-35 returned no usable data. Response: {response_text[:500]}"
            )

        csv_text = "\n".join(csv_lines)
        df = pd.read_csv(StringIO(csv_text))

        # Clean up column names (TAXSIM sometimes adds whitespace)
        df.columns = [c.strip().replace(".", "_") for c in df.columns]

        return df

    def run(self, show_progress: bool = True, on_progress=None) -> pd.DataFrame:
        """Submit input to NBER TAXSIM-35 and return results."""
        n_records = len(self.input_df)
        logger.info("Submitting %d records to NBER TAXSIM-35", n_records)

        # Batch if needed (NBER recommends ~2000 per request)
        if n_records <= BATCH_SIZE:
            csv_text = self._format_input(self.input_df)
            response = self._submit_to_taxsim(csv_text)
            return self._parse_response(response)

        # Process in batches
        frames = []
        for i in range(0, n_records, BATCH_SIZE):
            batch = self.input_df.iloc[i : i + BATCH_SIZE]
            csv_text = self._format_input(batch)
            response = self._submit_to_taxsim(csv_text)
            frames.append(self._parse_response(response))

            if on_progress:
                on_progress(
                    len(frames),
                    (n_records + BATCH_SIZE - 1) // BATCH_SIZE,
                    min(i + BATCH_SIZE, n_records),
                    n_records,
                )

        return pd.concat(frames, ignore_index=True)
