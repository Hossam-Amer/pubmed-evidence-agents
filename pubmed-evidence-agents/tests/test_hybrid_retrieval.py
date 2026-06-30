import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.retrieval.bm25 import search_bm25
from pipeline.retrieval.vector_store import reciprocal_rank_fusion


def test_bm25_exact_terms_rank_highest():
    chunks = [
        {
            "pmid": "1",
            "title": "Cardiovascular outcomes with SGLT2 inhibitors",
            "text": "Empagliflozin reduced heart failure hospitalization in type 2 diabetes.",
            "score": 0.0,
        },
        {
            "pmid": "2",
            "title": "Lifestyle counseling in diabetes",
            "text": "Diet and exercise were associated with glycemic improvement.",
            "score": 0.0,
        },
    ]

    results = search_bm25(chunks, "SGLT2 heart failure diabetes")

    assert results[0]["pmid"] == "1"
    assert results[0]["bm25_score"] > 0


def test_rrf_preserves_cosine_and_bm25_component_scores():
    cosine_results = [
        {"pmid": "1", "title": "A", "text": "semantic match", "score": 0.71},
        {"pmid": "2", "title": "B", "text": "other", "score": 0.4},
    ]
    bm25_results = [
        {"pmid": "1", "title": "A", "text": "semantic match", "score": 0.0, "bm25_score": 3.2},
    ]

    fused = reciprocal_rank_fusion([cosine_results, bm25_results])

    assert fused[0]["pmid"] == "1"
    assert fused[0]["score"] == 0.71
    assert fused[0]["bm25_score"] == 3.2
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
