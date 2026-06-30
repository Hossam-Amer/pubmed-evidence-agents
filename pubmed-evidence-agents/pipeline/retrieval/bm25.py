import math
import re
from collections import Counter

from config import BM25_CANDIDATE_K

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)?")
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def search_bm25(
    chunks: list[dict],
    query: str,
    k: int = BM25_CANDIDATE_K,
) -> list[dict]:
    """
    Rank chunks lexically with BM25 over title + abstract text.
    Returns copies of chunks with bm25_score set; cosine score is preserved.
    """
    if not chunks or not query or k <= 0:
        return []

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    docs: list[list[str]] = [
        _tokenize(f"{chunk.get('title', '')} {chunk.get('text', '')}") for chunk in chunks
    ]
    doc_count = len(docs)
    avgdl = sum(len(doc) for doc in docs) / max(doc_count, 1)

    doc_freq: Counter[str] = Counter()
    for doc in docs:
        doc_freq.update(set(doc))

    ranked: list[tuple[float, int]] = []
    query_counts = Counter(query_terms)
    for idx, doc in enumerate(docs):
        if not doc:
            continue
        freqs = Counter(doc)
        doc_len = len(doc)
        score = 0.0
        for term, query_weight in query_counts.items():
            tf = freqs.get(term, 0)
            if tf == 0:
                continue
            idf = math.log(1.0 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denom = tf + _K1 * (1.0 - _B + _B * doc_len / max(avgdl, 1e-9))
            score += query_weight * idf * (tf * (_K1 + 1.0) / denom)
        if score > 0:
            ranked.append((score, idx))

    ranked.sort(key=lambda item: item[0], reverse=True)
    results: list[dict] = []
    for score, idx in ranked[: min(k, len(ranked))]:
        chunk = dict(chunks[idx])
        chunk["bm25_score"] = float(score)
        results.append(chunk)
    return results
