import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.cache import get, put, clear, stats

_QUERIES = ["SGLT2 inhibitor cardiovascular", "empagliflozin heart failure"]
_CHUNKS  = [{"pmid": "1", "title": "T", "year": 2022, "text": "Sample.", "score": 0.9}]


def setup_function():
    clear()


def test_cache_miss_on_empty():
    assert get(_QUERIES) is None


def test_cache_hit_after_put():
    put(_QUERIES, _CHUNKS)
    result = get(_QUERIES)
    assert result is not None
    assert result[0]["pmid"] == "1"


def test_cache_key_order_insensitive():
    put(_QUERIES, _CHUNKS)
    reversed_q = list(reversed(_QUERIES))
    assert get(reversed_q) is not None


def test_cache_expiry(monkeypatch):
    import pipeline.cache as c_module
    monkeypatch.setattr(c_module, "CACHE_TTL_SECONDS", 0)
    put(_QUERIES, _CHUNKS)
    time.sleep(0.01)
    assert get(_QUERIES) is None


def test_stats():
    put(_QUERIES, _CHUNKS)
    s = stats()
    assert s["size"] == 1
    assert s["oldest_age_seconds"] is not None
