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

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "policyengine-taxsim",
        "fastapi[standard]",
    )
)

app = modal.App("policyengine-taxsim")

REQUIRED_COLUMNS = {"year"}
NUMERIC_COLUMNS = {
    "taxsimid", "year", "state", "mstat", "depx", "pwages", "swages",
    "page", "sage", "pensions", "gssi", "ltcg", "stcg", "intrec", "idtl",
}


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

    return df


def _run_taxsim(csv_text, disable_salt, assume_w2_wages, idtl, on_progress=None):
    """Shared logic for both Modal and local endpoints."""
    from policyengine_taxsim.runners.stitched_runner import StitchedRunner

    df = _validate_csv(csv_text)

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
    if isinstance(results, str):
        return {"csv": results, "rows_processed": len(df)}

    return {"csv": results.to_csv(index=False), "rows_processed": len(df)}


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
    from fastapi import FastAPI, HTTPException, Request
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
                    if progress_state["chunks_done"] != last_chunks and progress_state["total_chunks"] > 0:
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

    return _app


try:
    local_app = _build_local_app()
except ImportError:
    pass
