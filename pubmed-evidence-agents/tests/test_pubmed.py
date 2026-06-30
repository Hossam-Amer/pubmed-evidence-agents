import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pipeline.retrieval.pubmed import fetch_articles_for_queries


@pytest.mark.integration
def test_pubmed_returns_results():
    """Requires internet access + optional NCBI_API_KEY."""
    articles = fetch_articles_for_queries(["metformin type 2 diabetes HbA1c"])
    assert len(articles) > 0, "Expected at least one article"
    assert all("pmid" in a and "abstract" in a for a in articles)
    assert all(a["abstract"] for a in articles)


@pytest.mark.integration
def test_pubmed_deduplication():
    queries = [
        "SGLT2 inhibitor cardiovascular outcomes",
        "SGLT2 inhibitor heart failure hospitalization",
    ]
    articles = fetch_articles_for_queries(queries)
    pmids = [a["pmid"] for a in articles]
    assert len(pmids) == len(set(pmids)), "Duplicate PMIDs found"
