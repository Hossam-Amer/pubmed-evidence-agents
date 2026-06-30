import hashlib
import time
from config import CACHE_TTL_SECONDS

# In-memory store: key -> (chunks, timestamp)
_store: dict[str, tuple[list[dict], float]] = {}


def _make_key(queries: list[str]) -> str:
    normalised = "|".join(sorted(q.lower().strip() for q in queries))
    return hashlib.sha256(normalised.encode()).hexdigest()


def get(queries: list[str]) -> list[dict] | None:
    """Return cached top-k chunks if still within TTL, else None."""
    key = _make_key(queries)
    entry = _store.get(key)
    if entry is None:
        return None
    chunks, ts = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        del _store[key]
        return None
    return chunks


def put(queries: list[str], chunks: list[dict]) -> None:
    """Store top-k chunks for this query set."""
    _store[_make_key(queries)] = (chunks, time.time())


def clear() -> None:
    """Flush all cached entries (useful in tests)."""
    _store.clear()


def stats() -> dict:
    """Return cache size and oldest entry age in seconds."""
    if not _store:
        return {"size": 0, "oldest_age_seconds": None}
    now = time.time()
    oldest = min(ts for _, ts in _store.values())
    return {"size": len(_store), "oldest_age_seconds": round(now - oldest)}
