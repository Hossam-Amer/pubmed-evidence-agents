import sys
import json
import queue
import threading

# Force UTF-8 stdout/stderr on Windows to handle Unicode in article text
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import PipelineOutput
from pipeline.orchestrator import run_pipeline
from pipeline import cache as query_cache

app = FastAPI(
    title="pubmed-evidence-agents — Medical Evidence Retrieval Agent",
    description=(
        "Agentic RAG pipeline that retrieves and synthesizes PubMed evidence "
        "from a patient case description."
    ),
    version="1.0.0",
)


def _parse_pico_override(pico_json: str | None) -> dict | None:
    """Parse the optional edited-PICO form field (human-in-the-loop re-run)."""
    if not pico_json:
        return None
    try:
        data = json.loads(pico_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="pico_json is not valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="pico_json must be a JSON object")
    return data


@app.post("/query", response_model=PipelineOutput, summary="Run full pubmed-evidence-agents pipeline")
async def query_endpoint(
    clinical_text: str = Form(..., description="Free-text clinical case narrative"),
    pico_json: str | None = Form(default=None, description="Optional edited PICO JSON; skips extraction for a human-in-the-loop re-run"),
):
    """
    Accept a clinical case and return a cited evidence-grounded answer.
    """
    pico_override = _parse_pico_override(pico_json)

    try:
        result = run_pipeline(clinical_text, pico_override=pico_override)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")


@app.post("/query/stream", summary="Run pipeline with live log streaming (NDJSON)")
async def query_stream(
    clinical_text: str = Form(...),
    pico_json: str | None = Form(default=None),
):
    """
    Same as /query but streams log entries as NDJSON lines in real-time.
    Each line is one of:
      {"type": "log",    "data": {step, message, elapsed_ms, level}}
      {"type": "result", "data": <PipelineOutput dict>}
      {"type": "error",  "data": {"message": "..."}}
    """
    pico_override = _parse_pico_override(pico_json)

    log_q: queue.Queue = queue.Queue()
    result_box: dict = {}
    error_box:  dict = {}

    def _run():
        try:
            result = run_pipeline(clinical_text, log_queue=log_q, pico_override=pico_override)
            result_box["r"] = result
        except Exception as exc:
            error_box["e"] = str(exc)
        finally:
            log_q.put(None)  # sentinel — signals stream end

    threading.Thread(target=_run, daemon=True).start()

    def _stream():
        while True:
            item = log_q.get()
            if item is None:
                if error_box:
                    yield json.dumps({"type": "error", "data": {"message": error_box["e"]}}) + "\n"
                elif result_box:
                    payload = result_box["r"].model_dump()
                    payload["debug_log"] = []  # already streamed line-by-line
                    yield json.dumps({"type": "result", "data": payload}) + "\n"
                break
            yield json.dumps({"type": "log", "data": item}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "cache": query_cache.stats()}


@app.delete("/cache", summary="Flush query cache")
def flush_cache():
    query_cache.clear()
    return {"status": "cache cleared"}
