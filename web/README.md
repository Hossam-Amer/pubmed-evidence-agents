# pubmed-evidence-agents Web (Next.js)

React/Next.js frontend for pubmed-evidence-agents, replacing the Streamlit `app.py`. Implements the
plan in [../UI_PLAN.md](../UI_PLAN.md): streaming pipeline progress, retrieval
score charts, timing waterfall, evidence/citation explorer with verification
overlay, evidence-landscape timeline, a conflicting-evidence consensus banner,
and a human-in-the-loop PICO editor.

## Run

1. Start the backend (from the repo's `pubmed-evidence-agents/` dir):
   ```
   uvicorn main:app --host 0.0.0.0 --port 8015
   ```
2. Configure and start the frontend (from this `web/` dir):
   ```
   cp .env.local.example .env.local   # set PUBMED_EVIDENCE_AGENTS_API_URL if not :8015
   npm install
   npm run dev                          # http://localhost:3000
   ```

## How it talks to the backend

The browser only calls same-origin Next.js route handlers in `app/api/*`, which
proxy to the FastAPI backend server-side (no CORS, backend URL stays private):

- `POST /api/query` → streams FastAPI `POST /query/stream` (NDJSON) back unbuffered.
  Forwards `clinical_text` and optional `pico_json` (PICO editor re-run).
- `GET /api/health`, `DELETE /api/cache` → proxy the matching backend endpoints.

## Layout

```
app/            page + layout + api proxy routes
components/     query-form, stream-progress, charts, evidence-explorer, pico-editor, result-view, ui
lib/            types (mirror PipelineOutput), stream (NDJSON reader), derive (timing spans)
```

Charts use Recharts; the answer renderer turns `[n]` markers into interactive
citation chips. Types in `lib/types.ts` mirror `pubmed-evidence-agents/models/schemas.py` plus the
`evidence_trace` fields added in `pubmed-evidence-agents/pipeline/orchestrator.py`
(`top_k_docs[].score/text`, `verification`, `consensus`, `confidence_breakdown`,
`retrieval`).
