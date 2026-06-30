import torch
from config import RERANK_TOP_K, MEDCPT_CROSS_ID, USE_CROSS_ENCODER
from pipeline.model_loader import load_cross_encoder

_BATCH_SIZE = 16


def _cross_encoder_scores(query: str, chunks: list[dict]) -> list[float]:
    """Score each (query, title+abstract) pair with the MedCPT Cross-Encoder."""
    tokenizer, model = load_cross_encoder(MEDCPT_CROSS_ID)
    pairs = [[query, f"{c.get('title', '')} {c.get('text', '')}".strip()] for c in chunks]

    scores: list[float] = []
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i: i + _BATCH_SIZE]
        encoded = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(**encoded).logits.squeeze(dim=-1)
        scores.extend(logits.tolist())
    return scores


def rerank(query: str, chunks: list[dict], top_k: int = RERANK_TOP_K) -> list[dict]:
    """
    Second-stage reranking. The MedCPT Cross-Encoder scores each (query, article)
    pair jointly — far more precise than the bi-encoder cosine used for first-stage
    candidate retrieval. Falls back to cosine sort if disabled or unavailable.
    """
    if not chunks:
        return []

    if USE_CROSS_ENCODER:
        try:
            scores = _cross_encoder_scores(query, chunks)
            for c, s in zip(chunks, scores):
                c["ce_score"] = float(s)
            ranked = sorted(chunks, key=lambda c: c.get("ce_score", c.get("score", 0.0)), reverse=True)
            print(f"[Reranker] Cross-encoder reranked {len(chunks)} -> top {min(top_k, len(ranked))}.")
            return ranked[:top_k]
        except Exception as exc:
            print(f"[Reranker] Cross-encoder failed ({exc}); falling back to cosine sort.")

    ranked = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    return ranked[:top_k]
