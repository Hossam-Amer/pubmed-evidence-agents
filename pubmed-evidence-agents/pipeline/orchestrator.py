import time
import queue as _queue_mod
from models.schemas import PipelineOutput, PICOQuery
from pipeline import cache
from pipeline.query_agent import extract_pico
from pipeline.retrieval.pubmed import fetch_articles_for_queries
from pipeline.retrieval.preprocessor import preprocess_articles
from pipeline.retrieval.embeddings import embed_articles, embed_query
from pipeline.retrieval.bm25 import search_bm25
from pipeline.retrieval.vector_store import build_index, search_index, reciprocal_rank_fusion
from pipeline.reranker import rerank
from pipeline.loop_controller import run_verification_loop
from pipeline.confidence import calibrate_confidence
from pipeline.consensus import detect_consensus
from config import (
    OPENBIO_MODEL_ID,
    DEPLOY_MODE,
    LOOP_MAX_ITER,
    EMBED_CANDIDATE_K,
    USE_BM25,
    RERANK_TOP_K,
)

_SOURCE_FIELDS = (
    "journal",
    "journal_abbreviation",
    "publication_date",
    "publication_types",
    "doi",
    "pmc",
    "first_author",
    "cited_by_count",
)


def _source_metadata(chunk: dict) -> dict:
    return {field: chunk.get(field) for field in _SOURCE_FIELDS if chunk.get(field) not in (None, "", [])}


def _enrich_citations(citations: list[dict], chunks: list[dict]) -> list[dict]:
    by_pmid = {str(c.get("pmid")): c for c in chunks if c.get("pmid")}
    enriched = []
    for citation in citations:
        item = dict(citation)
        source = by_pmid.get(str(item.get("pmid")))
        if source:
            item.update({k: v for k, v in _source_metadata(source).items() if k not in item})
        enriched.append(item)
    return enriched


def run_pipeline(
    clinical_text: str,
    log_queue: _queue_mod.Queue | None = None,
    pico_override: dict | None = None,
) -> PipelineOutput:
    t_start = time.time()
    log: list[dict] = []

    def _log(step: str, message: str, level: str = "info"):
        elapsed = round((time.time() - t_start) * 1000)
        entry = {"step": step, "message": message, "elapsed_ms": elapsed, "level": level}
        log.append(entry)
        if log_queue is not None:
            log_queue.put(entry)
        print(f"[{elapsed:>6}ms] [{step}] {message}")

    _log("Pipeline", f"Starting pipeline | deploy_mode={DEPLOY_MODE}")

    override_pico = PICOQuery(**pico_override) if pico_override else None
    if override_pico is not None:
        _log("Pipeline", "Client-supplied PICO override present — extraction will be skipped")

    # ── Step 1: PICO extraction ──────────────────────────────────────────────
    t = time.time()
    if override_pico is not None:
        pico = override_pico
        _log("PICO", "Using client-supplied PICO override — skipping LLM extraction")
    else:
        _log("PICO", f"Extracting PICO with {OPENBIO_MODEL_ID}...")
        pico = extract_pico(clinical_text)
    _log("PICO", (
        f"Extracted in {round((time.time()-t)*1000)}ms | "
        f"P={pico.P[:60]!r} | I={pico.I!r} | O={pico.O!r} | "
        f"queries={len(pico.queries)}"
    ))
    for i, q in enumerate(pico.queries, 1):
        _log("PICO", f"  Query {i}: {q}")

    # ── Step 3: Cache check ───────────────────────────────────────────────────
    _log("Cache", f"Checking cache for {len(pico.queries)} query/queries...")
    cache_hit = False
    n_candidates: int | None = None
    cached = cache.get(pico.queries)

    if cached is not None:
        top_k_chunks = cached
        cache_hit = True
        _log("Cache", f"CACHE HIT — returning {len(top_k_chunks)} cached chunks, skipping retrieval", level="success")
    else:
        _log("Cache", "Cache MISS — proceeding to full retrieval")

        # ── Step 4: PubMed retrieval ──────────────────────────────────────────
        _log("PubMed", f"Searching PubMed for {len(pico.queries)} queries...")
        t = time.time()
        articles = fetch_articles_for_queries(pico.queries)
        _log("PubMed", f"Retrieved {len(articles)} unique articles in {round((time.time()-t)*1000)}ms")

        if not articles:
            _log("PubMed", "No articles found — returning early with no-results answer", level="error")
            return PipelineOutput(
                answer="No relevant literature found for the given clinical question.",
                citations=[],
                confidence="low",
                evidence_trace={
                    "pico": pico.model_dump(),
                    "queries_used": pico.queries,
                    "top_k_docs": [],
                    "verification_iterations": 0,
                    "verification_verdict": "no_results",
                    "verification": {"verdict": "no_results", "status": "no_results", "unsupported_claims": [], "suggested_corrections": []},
                    "consensus": {"agreement": "unknown", "supporting_pmids": [], "conflicting_pmids": [], "summary": ""},
                    "confidence_breakdown": {},
                    "retrieval": {"candidates": 0, "selected": 0, "bm25": USE_BM25},
                    "cache_hit": False,
                    "latency_seconds": round(time.time() - t_start, 2),
                },
                debug_log=log,
            )

        # ── Step 5: Preprocess (one title+abstract unit per article) ──────────
        _log("Preprocess", f"Cleaning {len(articles)} articles (title+abstract kept whole, no chunking)...")
        t = time.time()
        chunks = preprocess_articles(articles)
        _log("Preprocess", f"Prepared {len(chunks)} article units in {round((time.time()-t)*1000)}ms")

        # ── Step 6: Embed articles (MedCPT title [SEP] abstract) + index ──────
        _log("Embed", f"Embedding {len(chunks)} articles with MedCPT Article Encoder (CPU)...")
        t = time.time()
        article_embs = embed_articles(chunks)
        index = build_index(article_embs)
        _log("Embed", f"Embedded + indexed in {round((time.time()-t)*1000)}ms | shape={article_embs.shape}")

        # ── Step 7: Per-query semantic search + Reciprocal Rank Fusion ────────
        bm25_label = " + BM25" if USE_BM25 else ""
        _log("Hybrid", f"Searching each of {len(pico.queries)} query/queries with FAISS{bm25_label} + RRF fusion...")
        t = time.time()
        result_lists = []
        for q in pico.queries:
            result_lists.append(search_index(index, chunks, embed_query(q)))
            if USE_BM25:
                result_lists.append(search_bm25(chunks, q))
        candidates = reciprocal_rank_fusion(result_lists)[:EMBED_CANDIDATE_K]
        n_candidates = len(candidates)
        _log("Hybrid", f"Fused to {len(candidates)} candidates in {round((time.time()-t)*1000)}ms")
        if candidates:
            _log(
                "Hybrid",
                (
                    f"Top fused rrf={candidates[0].get('rrf_score',0):.5f} "
                    f"cos={candidates[0].get('score',0):.4f} "
                    f"bm25={candidates[0].get('bm25_score',0):.2f} | "
                    f"{candidates[0].get('title','?')[:80]}"
                ),
            )

        # ── Step 8: Cross-encoder reranking (MedCPT Cross-Encoder) ────────────
        _log("TopK", f"Reranking {len(candidates)} candidates with cross-encoder -> top {RERANK_TOP_K}...")
        t = time.time()
        top_k_chunks = rerank(clinical_text, candidates)
        _log("TopK", f"Selected top {len(top_k_chunks)} in {round((time.time()-t)*1000)}ms (cross-encoder)")

        # ── Step 9: Cache store ───────────────────────────────────────────────
        cache.put(pico.queries, top_k_chunks)
        _log("Cache", f"Stored {len(top_k_chunks)} chunks in cache (TTL 24h)")

    # ── Step 10: Consensus / conflicting-evidence detection ──────────────────
    _log("Consensus", "Analyzing agreement across retrieved evidence...")
    t = time.time()
    consensus = detect_consensus(pico.model_dump(), top_k_chunks)
    _log(
        "Consensus",
        f"Agreement: {consensus.get('agreement')} in {round((time.time()-t)*1000)}ms | "
        f"{consensus.get('summary', '')[:80]}",
        level="warn" if consensus.get("agreement") == "conflicting" else "info",
    )

    # ── Step 11: Generate + Verify loop ──────────────────────────────────────
    _log("Generator", f"Starting generate→verify loop (max {LOOP_MAX_ITER} iterations) with {OPENBIO_MODEL_ID}...")
    t = time.time()
    final_output, n_iter, verdict, loop_log, verification = run_verification_loop(
        clinical_text, pico.model_dump(), top_k_chunks, loop_log=[], log_queue=log_queue
    )
    log.extend(loop_log)
    _log("Pipeline", (
        f"Loop complete in {round((time.time()-t)*1000)}ms | "
        f"iterations={n_iter} verdict={verdict} self_confidence={final_output.confidence}"
    ), level="success" if verdict == "pass" else "warn")

    # ── Step 12: Calibrated confidence (overrides self-reported) ─────────────
    cal_level, confidence_breakdown = calibrate_confidence(
        top_k_chunks, verification, final_output.confidence
    )
    if cal_level != final_output.confidence:
        _log("Pipeline", f"Confidence recalibrated: {final_output.confidence} → {cal_level}")
    final_output.confidence = cal_level
    final_output.citations = _enrich_citations(final_output.citations, top_k_chunks)

    total = round(time.time() - t_start, 2)
    _log("Pipeline", f"Done in {total}s | citations={len(final_output.citations)}", level="success")

    return PipelineOutput(
        answer=final_output.answer,
        citations=final_output.citations,
        confidence=final_output.confidence,
        evidence_trace={
            "pico": pico.model_dump(),
            "queries_used": pico.queries,
            "top_k_docs": [
                {
                    "pmid": c["pmid"],
                    "title": c["title"],
                    "year": c.get("year"),
                    **_source_metadata(c),
                    "score": round(float(c.get("score", 0.0)), 4),
                    "bm25_score": round(float(c.get("bm25_score", 0.0)), 4),
                    "rrf_score": round(float(c.get("rrf_score", 0.0)), 5),
                    "text": c.get("text", ""),
                }
                for c in top_k_chunks
            ],
            "verification_iterations": n_iter,
            "verification_verdict": verdict,
            "verification": {
                "verdict": verification.verdict if verification else verdict,
                "status": verdict,
                "unsupported_claims": verification.unsupported_claims if verification else [],
                "suggested_corrections": verification.suggested_corrections if verification else [],
                "error": verification.error if verification else None,
            },
            "consensus": consensus,
            "confidence_breakdown": confidence_breakdown,
            "retrieval": {"candidates": n_candidates, "selected": len(top_k_chunks), "bm25": USE_BM25},
            "cache_hit": cache_hit,
            "latency_seconds": total,
        },
        debug_log=log,
    )
