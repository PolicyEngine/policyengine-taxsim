"""
PolicyEngine TAXSIM API — runs on Modal.

Deploy:
    modal deploy policyengine_taxsim/api.py

Dev (hot-reload):
    modal serve policyengine_taxsim/api.py

Local (no Modal):
    uvicorn policyengine_taxsim.api:local_app --port 8440
"""

import modal

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "policyengine-taxsim",
    "fastapi[standard]",
    "resend",
)

app = modal.App("policyengine-taxsim")

REQUIRED_COLUMNS = {"year"}
NUMERIC_COLUMNS = {
    "taxsimid",
    "year",
    "state",
    "mstat",
    "depx",
    "pwages",
    "swages",
    "page",
    "sage",
    "pensions",
    "gssi",
    "ltcg",
    "stcg",
    "intrec",
    "idtl",
}

# All recognized TAXSIM input column names
KNOWN_COLUMNS = {
    "taxsimid",
    "year",
    "state",
    "mstat",
    "page",
    "sage",
    "dependent_exemption",
    "depx",
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
    "pbusinc",
    "pprofinc",
    "idtl",
}

MAILCHIMP_URL = (
    "https://policyengine.us5.list-manage.com/subscribe/post-json"
    "?u=e5ad35332666289a0f48013c5&id=71ed1f89d8&f_id=00f173e6f0"
)


def _validate_csv(csv_text):
    """Parse and validate CSV text, return a DataFrame."""
    import pandas as pd
    from io import StringIO

    if not csv_text or not csv_text.strip():
        raise ValueError("No CSV data provided. Upload a file or paste CSV text.")

    try:
        df = pd.read_csv(StringIO(csv_text))
    except Exception:
        raise ValueError(
            "Could not parse CSV. Make sure the file is comma-separated "
            "with a header row (e.g. taxsimid,year,state,mstat,pwages)."
        )

    if len(df) == 0:
        raise ValueError("CSV has a header but no data rows.")

    # Check required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            "See the documentation for the full list of input variables."
        )

    # Validate numeric columns have parseable values
    for col in set(df.columns) & NUMERIC_COLUMNS:
        try:
            pd.to_numeric(df[col])
        except (ValueError, TypeError):
            bad_vals = df[col][pd.to_numeric(df[col], errors="coerce").isna()]
            examples = bad_vals.head(3).tolist()
            raise ValueError(
                f"Column '{col}' contains non-numeric values: {examples}. "
                "All input variables must be numbers."
            )

    # Warn about unrecognized columns (they'll be silently ignored)
    warnings = []
    unknown = set(df.columns) - KNOWN_COLUMNS
    if unknown:
        warnings.append(
            f"Unrecognized column(s): {', '.join(sorted(unknown))}. "
            "These will be ignored. See the documentation for valid input variables."
        )

    return df, warnings


def _run_taxsim(csv_text, disable_salt, assume_w2_wages, idtl, on_progress=None):
    """Shared logic for both Modal and local endpoints."""
    from policyengine_taxsim.runners.stitched_runner import StitchedRunner

    df, warnings = _validate_csv(csv_text)

    # Override idtl on all rows if specified
    if idtl is not None:
        df["idtl"] = int(idtl)

    runner = StitchedRunner(
        df,
        logs=False,
        disable_salt=disable_salt,
        assume_w2_wages=assume_w2_wages,
    )
    results = runner.run(show_progress=False, on_progress=on_progress)

    # idtl=5 returns text per-household; everything else returns a DataFrame
    base = {"rows_processed": len(df)}
    if warnings:
        base["warnings"] = warnings
    if isinstance(results, str):
        return {"csv": results, **base}

    return {"csv": results.to_csv(index=False), **base}


def _subscribe_to_mailchimp(email):
    """Subscribe an email to the PolicyEngine Mailchimp list (best-effort)."""
    import urllib.request
    import urllib.parse
    import json

    try:
        url = f"{MAILCHIMP_URL}&EMAIL={urllib.parse.quote(email)}&c=cb"
        resp = urllib.request.urlopen(url, timeout=10)
        body = resp.read().decode()
        # JSONP response: cb({...})
        json_str = body[body.index("(") + 1 : body.rindex(")")]
        data = json.loads(json_str)
        if data.get("result") == "error":
            import logging

            logging.getLogger(__name__).warning(
                "Mailchimp subscription for %s: %s", email, data.get("msg", "")
            )
    except Exception:
        pass  # Best-effort — don't fail the request if Mailchimp is down


def _send_results_email(email, csv_text, rows_processed, filename):
    """Send results CSV via Resend."""
    import os
    import base64
    import resend

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise ValueError("Email delivery is not configured (missing RESEND_API_KEY).")

    resend.api_key = api_key

    output_filename = (
        filename.replace(".csv", "_output.csv") if filename else "output.csv"
    )

    resend.Emails.send(
        {
            "from": "PolicyEngine Team <hello@policyengine.org>",
            "to": email,
            "subject": f"Your TAXSIM emulator results ({rows_processed:,} households)",
            "html": (
                f"<p>Your TAXSIM emulator results are attached.</p>"
                f"<p><strong>{rows_processed:,}</strong> households were processed successfully.</p>"
                f"<p>Run more simulations at "
                f"<a href='https://policyengine.org/us/taxsim/run/'>policyengine.org/us/taxsim/run</a>.</p>"
                f"<p style='color: #666; font-size: 12px;'>— PolicyEngine</p>"
            ),
            "attachments": [
                {
                    "filename": output_filename,
                    "content": base64.b64encode(csv_text.encode()).decode(),
                }
            ],
        }
    )


@app.cls(image=image, container_idle_timeout=300, timeout=600)
class TaxsimAPI:
    @modal.enter()
    def load(self):
        """Pre-import policyengine-us so first request is fast."""
        import policyengine_us  # noqa: F401

    @modal.fastapi_endpoint(method="POST", docs=True)
    def run(self, req: dict):
        """Accept TAXSIM-format CSV, run through PolicyEngine, return results."""
        csv_text = req.get("csv", "")
        if not csv_text:
            return {"error": "No CSV provided"}

        try:
            return _run_taxsim(
                csv_text,
                disable_salt=bool(req.get("disable_salt", False)),
                assume_w2_wages=bool(req.get("assume_w2_wages", False)),
                idtl=req.get("idtl"),
            )
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Processing error: {e}"}


# ---------------------------------------------------------------------------
# Local fallback: `uvicorn policyengine_taxsim.api:local_app --port 8440`
# ---------------------------------------------------------------------------
def _build_local_app():
    import asyncio
    import json
    from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    from typing import Optional

    _app = FastAPI(title="PolicyEngine TAXSIM API (local)")

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["POST"],
        allow_headers=["*"],
    )

    class RunRequest(BaseModel):
        csv: str
        disable_salt: bool = False
        assume_w2_wages: bool = False
        idtl: Optional[int] = None

    class EmailRunRequest(BaseModel):
        csv: str
        email: str
        filename: str = "input.csv"
        disable_salt: bool = False
        assume_w2_wages: bool = False
        idtl: Optional[int] = None
        subscribe: bool = True

    @_app.post("/run")
    def run_taxsim(req: RunRequest):
        try:
            return _run_taxsim(
                req.csv,
                disable_salt=req.disable_salt,
                assume_w2_wages=req.assume_w2_wages,
                idtl=req.idtl,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing error: {e}")

    @_app.post("/run/stream")
    async def run_taxsim_stream(request: Request):
        """SSE endpoint that streams chunk progress, then the final result."""
        body = await request.json()
        req = RunRequest(**body)

        async def event_stream():
            progress_state = {"chunks_done": 0, "total_chunks": 0}

            def on_progress(chunks_done, total_chunks, rows_done, total_rows):
                progress_state["chunks_done"] = chunks_done
                progress_state["total_chunks"] = total_chunks
                progress_state["rows_done"] = rows_done
                progress_state["total_rows"] = total_rows

            try:
                # Run in a thread so we can yield SSE events
                loop = asyncio.get_event_loop()
                import concurrent.futures

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

                future = loop.run_in_executor(
                    executor,
                    lambda: _run_taxsim(
                        req.csv,
                        disable_salt=req.disable_salt,
                        assume_w2_wages=req.assume_w2_wages,
                        idtl=req.idtl,
                        on_progress=on_progress,
                    ),
                )

                # Poll for progress while the runner works
                last_chunks = -1
                while not future.done():
                    await asyncio.sleep(0.3)
                    if (
                        progress_state["chunks_done"] != last_chunks
                        and progress_state["total_chunks"] > 0
                    ):
                        last_chunks = progress_state["chunks_done"]
                        evt = {
                            "type": "progress",
                            "chunks_done": progress_state["chunks_done"],
                            "total_chunks": progress_state["total_chunks"],
                            "rows_done": progress_state.get("rows_done", 0),
                            "total_rows": progress_state.get("total_rows", 0),
                        }
                        yield f"data: {json.dumps(evt)}\n\n"

                result = await future
                yield f"data: {json.dumps({'type': 'result', **result})}\n\n"

            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': f'Processing error: {e}'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @_app.post("/run/email")
    def run_and_email(req: EmailRunRequest, background_tasks: BackgroundTasks):
        """Validate CSV, subscribe to Mailchimp, then process and email results in background."""
        import re

        # Validate email
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", req.email):
            raise HTTPException(status_code=400, detail="Invalid email address.")

        # Validate CSV upfront so the user gets immediate feedback
        try:
            _df, _warnings = _validate_csv(req.csv)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        def _process_and_email():
            try:
                # Subscribe to Mailchimp (best-effort, only if user opted in)
                if req.subscribe:
                    _subscribe_to_mailchimp(req.email)

                # Run the simulation
                result = _run_taxsim(
                    req.csv,
                    disable_salt=req.disable_salt,
                    assume_w2_wages=req.assume_w2_wages,
                    idtl=req.idtl,
                )

                # Email the results
                _send_results_email(
                    req.email,
                    result["csv"],
                    result["rows_processed"],
                    req.filename,
                )
            except Exception as e:
                # Log but don't raise — user already got a 200
                import logging

                logging.getLogger(__name__).error(f"Background email job failed: {e}")

        background_tasks.add_task(_process_and_email)

        return {
            "message": f"Results will be emailed to {req.email} when processing completes."
        }

    return _app


try:
    local_app = _build_local_app()
except ImportError:
    pass
