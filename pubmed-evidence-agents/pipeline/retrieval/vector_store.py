from collections import defaultdict

import faiss
import numpy as np

from config import EMBED_CANDIDATE_K, RRF_K


def _normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / (norms + 1e-8)


def build_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """
    Build a FAISS inner-product index over L2-normalized embeddings.
    Inner product on unit vectors is cosine similarity.
    """
    normed = _normalize(embeddings.astype("float32"))
    index = faiss.IndexFlatIP(normed.shape[1])
    index.add(normed)
    print(f"[VectorStore] Index built: {index.ntotal} vectors, dim={normed.shape[1]}.")
    return index


def search_index(
    index: faiss.IndexFlatIP,
    chunks: list[dict],
    query_embedding: np.ndarray,
    k: int = EMBED_CANDIDATE_K,
) -> list[dict]:
    """
    Search the FAISS index for the top-k chunks closest to query_embedding.
    Returns copies of matched chunks with the cosine score in score.
    """
    normed_q = _normalize(query_embedding.reshape(1, -1).astype("float32"))
    k = min(k, index.ntotal)
    scores, indices = index.search(normed_q, k)

    results: list[dict] = []
    for score, idx in zip(scores[0], indices[0]):
        if 0 <= idx < len(chunks):
            chunk = dict(chunks[idx])
            chunk["score"] = float(score)
            results.append(chunk)
    return results


def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """
    Fuse ranked result lists with Reciprocal Rank Fusion.
    Each query and retriever votes independently, so complementary semantic and
    lexical hits can rise to the top. Deduplicates by PMID while preserving the
    best available cosine and BM25 component scores.
    """
    fused: dict[str, float] = defaultdict(float)
    best_chunk: dict[str, dict] = {}
    best_cos: dict[str, float] = {}
    best_bm25: dict[str, float] = {}

    for results in result_lists:
        for rank, chunk in enumerate(results):
            key = chunk["pmid"]
            fused[key] += 1.0 / (k + rank + 1)

            cos = float(chunk.get("score", 0.0))
            if key not in best_cos or cos > best_cos[key]:
                best_cos[key] = cos
                best_chunk[key] = chunk

            bm25 = chunk.get("bm25_score")
            if bm25 is not None and (key not in best_bm25 or float(bm25) > best_bm25[key]):
                best_bm25[key] = float(bm25)
                best_chunk.setdefault(key, chunk)

    ordered = sorted(fused, key=lambda key: fused[key], reverse=True)
    out: list[dict] = []
    for key in ordered:
        c = dict(best_chunk[key])
        c["score"] = best_cos.get(key, 0.0)
        if key in best_bm25:
            c["bm25_score"] = best_bm25[key]
        c["rrf_score"] = round(fused[key], 5)
        out.append(c)
    return out
