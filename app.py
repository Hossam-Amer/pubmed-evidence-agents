import streamlit as st
import requests
import json
import pandas as pd

API_URL = "http://localhost:8015"

st.set_page_config(
    page_title="pubmed-evidence-agents — Medical Evidence Retrieval Agent",
    page_icon="🩺",
    layout="wide",
)

# ── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.confidence-high   { background:#d4edda; color:#155724; padding:4px 12px; border-radius:12px; font-weight:600; }
.confidence-medium { background:#fff3cd; color:#856404; padding:4px 12px; border-radius:12px; font-weight:600; }
.confidence-low    { background:#f8d7da; color:#721c24; padding:4px 12px; border-radius:12px; font-weight:600; }
.citation-card { background:#f8f9fa; border-left:4px solid #0288D1; padding:10px 14px; margin:6px 0; border-radius:4px; }
.pico-label { font-weight:700; color:#7E57C2; min-width:120px; display:inline-block; }

/* Debug log terminal */
.log-terminal {
    background:#0d1117; color:#c9d1d9; font-family:'Consolas','Courier New',monospace;
    font-size:0.82rem; padding:14px 16px; border-radius:8px;
    max-height:460px; overflow-y:auto; line-height:1.7;
    border: 1px solid #30363d;
}
.log-info    { color:#8b949e; }
.log-success { color:#3fb950; }
.log-warn    { color:#d29922; }
.log-error   { color:#f85149; }
.log-step    { color:#58a6ff; font-weight:700; }
.log-time    { color:#6e7681; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
STEP_ICONS = {
    "Pipeline": "⚡", "PICO": "🧩",
    "Cache": "💾", "PubMed": "📡", "Preprocess": "✂️",
    "Embed": "🔢", "FAISS": "🔍", "TopK": "📊",
    "Generator": "✍️", "Verifier": "✅", "LoopCtrl": "🔄",
}

def _render_terminal(entries: list[dict], cursor: bool = False) -> str:
    lines = []
    for e in entries:
        elapsed = e.get("elapsed_ms", 0)
        step    = e.get("step", "")
        msg     = e.get("message", "")
        level   = e.get("level", "info")
        icon    = STEP_ICONS.get(step, "•")
        msg_esc = (msg.replace("&", "&amp;").replace("<", "&lt;")
                      .replace(">", "&gt;").replace('"', "&quot;"))
        lines.append(
            f'<span class="log-time">[{elapsed:>6}ms]</span> '
            f'<span class="log-step">[{icon} {step:<9}]</span> '
            f'<span class="log-{level}">{msg_esc}</span>'
        )
    if cursor:
        lines.append('<span class="log-warn">▌</span>')
    return '<div class="log-terminal">' + "<br>".join(lines) + "</div>"


# ── Header ───────────────────────────────────────────────────────────────────
st.title("🩺 pubmed-evidence-agents — Medical Evidence Retrieval Agent")
st.caption("Agentic RAG pipeline · PubMed retrieval · Groq LLaMA inference · MedCPT embeddings")
st.divider()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    api_url = st.text_input("API Base URL", value=API_URL)

    st.divider()
    st.subheader("🔍 About")
    st.markdown("""
**Pipeline stages:**
1. PICO extraction (Llama 3.1 8B)
2. PubMed search
3. MedCPT embedding + FAISS
4. RAG generation (Llama 3.1 8B)
5. Verification (Llama 3.1 8B)

**Models via:** Groq free API
**Embeddings:** MedCPT (local CPU)
    """)

    st.divider()
    if st.button("🗑️ Clear cache", use_container_width=True):
        try:
            r = requests.delete(f"{api_url}/cache", timeout=5)
            st.success("Cache cleared." if r.ok else f"Error: {r.text}")
        except Exception as e:
            st.error(f"Server unreachable: {e}")

    try:
        h = requests.get(f"{api_url}/health", timeout=3)
        data = h.json()
        st.success(f"✅ Server online · Cache: {data['cache']['size']} entries")
    except Exception:
        st.error("❌ Server offline — start uvicorn first")

# ── Input ─────────────────────────────────────────────────────────────────────
clinical_text = st.text_area(
    "Clinical case description",
    placeholder=(
        "e.g. 65-year-old male, type 2 diabetes, HbA1c 9.2%, on metformin. "
        "Considering adding SGLT2 inhibitor. What is the cardiovascular benefit evidence?"
    ),
    height=160,
    label_visibility="collapsed",
)

run_btn = st.button(
    "🔬 Run Evidence Query", type="primary", use_container_width=True,
    disabled=not clinical_text.strip(),
)

# ── Run pipeline (streaming) ──────────────────────────────────────────────────
if run_btn and clinical_text.strip():
    st.divider()

    # Live log panel — updates in real-time as pipeline runs
    st.subheader("🐛 Pipeline Debug Log")
    status_text  = st.empty()
    log_panel    = st.empty()

    log_entries: list[dict] = []
    result: dict | None = None
    error_msg: str | None = None

    status_text.info("⏳ Connecting to pipeline… (first run downloads MedCPT models ~880MB)")

    try:
        data  = {"clinical_text": clinical_text}

        with requests.post(
            f"{api_url}/query/stream",
            data=data,
            stream=True,
            timeout=360,
        ) as resp:
            resp.raise_for_status()

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                item = json.loads(raw_line)

                if item["type"] == "log":
                    entry = item["data"]
                    log_entries.append(entry)
                    # Update the terminal in-place with blinking cursor
                    log_panel.markdown(_render_terminal(log_entries, cursor=True), unsafe_allow_html=True)
                    # Update status chip with current step
                    step = entry.get("step", "")
                    icon = STEP_ICONS.get(step, "•")
                    status_text.info(f"{icon} **{step}** — {entry.get('message','')[:80]}")

                elif item["type"] == "result":
                    result = item["data"]

                elif item["type"] == "error":
                    error_msg = item["data"].get("message", "Unknown error")

    except requests.exceptions.ConnectionError:
        error_msg = "Cannot reach the API server. Make sure uvicorn is running."
    except requests.exceptions.Timeout:
        error_msg = "Request timed out (>6 min)."
    except Exception as e:
        error_msg = str(e)

    # Final log state (no cursor)
    if log_entries:
        log_panel.markdown(_render_terminal(log_entries, cursor=False), unsafe_allow_html=True)

    if error_msg:
        status_text.error(f"Pipeline error: {error_msg}")
        st.stop()

    if not result:
        status_text.error("No result received from pipeline.")
        st.stop()

    status_text.success("✅ Pipeline complete")

    # Timing bar chart (collapsed by default)
    with st.expander("⏱️ Step timing breakdown"):
        step_times: dict[str, int] = {}
        for entry in log_entries:
            s   = entry["step"]
            ms  = entry["elapsed_ms"]
            prev = max(step_times.values()) if step_times else 0
            delta = ms - prev
            if delta > 0:
                step_times[s] = step_times.get(s, 0) + delta

        df = pd.DataFrame(
            {"Step": list(step_times.keys()), "ms": list(step_times.values())}
        ).query("ms > 0")
        if not df.empty:
            st.bar_chart(df.set_index("Step")["ms"], use_container_width=True)

    # ── Results ───────────────────────────────────────────────────────────────
    st.divider()

    trace   = result.get("evidence_trace", {})
    conf    = result.get("confidence", "low")
    latency = trace.get("latency_seconds", 0)
    n_iter  = trace.get("verification_iterations", 0)
    cached  = trace.get("cache_hit", False)
    n_docs  = len(trace.get("top_k_docs", []))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Confidence",   conf.upper())
    m2.metric("Latency",      f"{latency:.1f}s")
    m3.metric("Verif. loops", n_iter)
    m4.metric("Docs used",    n_docs)
    m5.metric("Cache hit",    "Yes" if cached else "No")

    conf_class = f"confidence-{conf}"
    st.markdown(f'<span class="{conf_class}">Confidence: {conf.upper()}</span>', unsafe_allow_html=True)
    st.divider()

    col_ans, col_meta = st.columns([3, 2])

    with col_ans:
        st.subheader("📋 Clinical Answer")
        st.markdown(result.get("answer", ""))

        citations = result.get("citations", [])
        if citations:
            st.subheader(f"📚 Citations ({len(citations)})")
            seen: set = set()
            for c in citations:
                pmid = c.get("pmid", "")
                if pmid in seen:
                    continue
                seen.add(pmid)
                title = c.get("title", "No title")
                year  = c.get("year", "")
                journal = c.get("journal") or c.get("journal_abbreviation") or "Journal not available"
                pub_date = c.get("publication_date") or year or "Date not available"
                pub_types = ", ".join(c.get("publication_types") or []) or "Study type not available"
                cited_by = c.get("cited_by_count")
                cited_label = f"{cited_by:,}" if isinstance(cited_by, int) else "Not available"
                pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
                st.markdown(
                    f'<div class="citation-card">'
                    f'<strong>[{c.get("id","")}]</strong> {title} '
                    f'<span style="color:#888">({year})</span><br>'
                    f'<span style="color:#555">{journal} · Published: {pub_date} · {pub_types} · Cited by: {cited_label}</span><br>'
                    f'<a href="{pubmed_url}" target="_blank">PMID: {pmid}</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with col_meta:
        pico = trace.get("pico", {})
        if pico:
            st.subheader("🧩 PICO Breakdown")
            for key, label in [("P","Population"), ("I","Intervention"), ("C","Comparison"), ("O","Outcome")]:
                val = pico.get(key) or "—"
                st.markdown(
                    f'<p><span class="pico-label">{label}</span>{val}</p>',
                    unsafe_allow_html=True,
                )

        queries = trace.get("queries_used", [])
        if queries:
            with st.expander("🔎 PubMed queries used"):
                for q in queries:
                    st.code(q, language="text")

        top_docs = trace.get("top_k_docs", [])
        if top_docs:
            with st.expander(f"📄 Retrieved documents ({len(top_docs)})"):
                for doc in top_docs:
                    pmid = doc.get("pmid", "")
                    url  = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    st.markdown(
                        f"**{doc.get('title','?')}** ({doc.get('year','?')})  \n"
                        f"[PMID {pmid}]({url})"
                    )
                    st.divider()

        with st.expander("🔬 Full evidence trace (JSON)"):
            st.json(trace)
