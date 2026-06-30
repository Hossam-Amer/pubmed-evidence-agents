import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.retrieval.preprocessor import chunk_text, preprocess_articles
from config import CHUNK_SIZE


def test_chunk_token_count():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    text = "This is a test sentence about diabetes treatment with metformin. " * 50
    chunks = chunk_text(text, pmid="123", title="Test", year=2024)
    for c in chunks:
        token_count = len(enc.encode(c["text"]))
        assert token_count <= CHUNK_SIZE + 5, f"Chunk too large: {token_count} tokens"


def test_preprocess_deduplication():
    articles = [
        {"pmid": "1", "title": "A", "abstract": "Diabetes treatment.", "year": 2020},
        {"pmid": "1", "title": "A", "abstract": "Diabetes treatment.", "year": 2020},  # duplicate
        {"pmid": "2", "title": "B", "abstract": "Hypertension management.", "year": 2021},
    ]
    chunks = preprocess_articles(articles)
    pmids = {c["pmid"] for c in chunks}
    assert "1" in pmids and "2" in pmids
    # Should not double-process PMID 1
    count_pmid1 = sum(1 for c in chunks if c["pmid"] == "1")
    expected = len(chunk_text("Diabetes treatment.", "1", "A", 2020))
    assert count_pmid1 == expected


def test_empty_abstract_skipped():
    articles = [{"pmid": "99", "title": "Empty", "abstract": "", "year": 2020}]
    chunks = preprocess_articles(articles)
    assert all(c["pmid"] != "99" for c in chunks)
