import re
import tiktoken
from config import CHUNK_SIZE, CHUNK_OVERLAP

_enc = tiktoken.get_encoding("cl100k_base")


def _clean(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)      # strip HTML/XML tags
    text = re.sub(r'\s+', ' ', text)           # collapse whitespace
    return text.strip()


def chunk_text(
    text: str,
    pmid: str,
    title: str,
    year: int | None,
    metadata: dict | None = None,
) -> list[dict]:
    """
    Split text into overlapping token windows of CHUNK_SIZE with CHUNK_OVERLAP.
    Each chunk dict carries its source metadata.
    """
    tokens = _enc.encode(text)
    chunks = []
    i = 0
    while i < len(tokens):
        window = tokens[i: i + CHUNK_SIZE]
        chunk = {
            "pmid":  pmid,
            "title": title,
            "year":  year,
            "text":  _enc.decode(window),
            "score": 0.0,
        }
        if metadata:
            chunk.update(metadata)
        chunks.append(chunk)
        if i + CHUNK_SIZE >= len(tokens):
            break
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def preprocess_articles(articles: list[dict]) -> list[dict]:
    """
    Clean each article into a single retrievable unit (title + abstract kept
    whole, no chunking). MedCPT's Article Encoder is trained on
    `title [SEP] abstract` pairs and abstracts comfortably fit its 512-token
    window, so chunking only split the title from the body and hurt embeddings.

    Deduplicates by PMID. Returns one dict per article:
    {pmid, title, year, text (cleaned abstract), score}.
    """
    seen: set[str] = set()
    units: list[dict] = []

    for a in articles:
        if a["pmid"] in seen:
            continue
        seen.add(a["pmid"])
        clean = _clean(a.get("abstract", ""))
        if not clean:
            continue
        units.append({
            "pmid":  a["pmid"],
            "title": a.get("title", ""),
            "year":  a.get("year"),
            "text":  clean,
            "score": 0.0,
            "publication_date": a.get("publication_date"),
            "journal": a.get("journal", ""),
            "journal_abbreviation": a.get("journal_abbreviation", ""),
            "publication_types": a.get("publication_types", []),
            "doi": a.get("doi", ""),
            "pmc": a.get("pmc", ""),
            "first_author": a.get("first_author", ""),
            "cited_by_count": a.get("cited_by_count"),
        })

    print(f"[Preprocessor] {len(units)} article units from {len(seen)} unique PMIDs.")
    return units
