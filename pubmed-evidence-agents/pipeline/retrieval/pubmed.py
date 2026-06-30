import re as _re
import time
import requests
from xml.etree import ElementTree as ET
from config import NCBI_API_KEY, PUBMED_MAX_RESULTS

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_RATE_DELAY = 0.34 if not NCBI_API_KEY else 0.11  # ~3 req/s free, ~9 with key
_MONTHS = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

# Demographic / study-type terms that over-restrict a short keyword query
_NOISE_TERMS = {
    "male", "female", "aged", "humans", "adult", "middle aged",
    "comparative study", "clinical trial", "randomized controlled trial",
    "review", "meta-analysis", "systematic review",
}


def _run_esearch(term: str, base_params: dict) -> list[str]:
    resp = requests.get(
        f"{_BASE}/esearch.fcgi",
        params={**base_params, "term": term},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


def _strip_qualifiers(query: str) -> str:
    """Remove any [Field] tags that slipped through, keeping bare terms."""
    return _re.sub(r'\[[^\]]+\]', ' ', query).strip()


def _minimal_fallback(query: str) -> str:
    """
    Emergency fallback: extract quoted phrases, drop noise, keep top 3.
    Only reached if the query somehow contains brackets (shouldn't happen
    with the new deterministic query builder).
    """
    terms = _re.findall(r'"([^"]+)"', query)
    core = [t for t in terms if t.lower() not in _NOISE_TERMS][:3]
    if not core:
        # No quotes — just take first 3 space-separated words
        words = query.split()
        core = [w for w in words if w.lower() not in _NOISE_TERMS][:3]
    return " AND ".join(f'"{t}"' for t in core) if core else query


def _first_text(parent: ET.Element, paths: list[str]) -> str:
    for path in paths:
        value = parent.findtext(path, default="")
        if value:
            return value.strip()
    return ""


def _normalise_month(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if value.isdigit():
        return value.zfill(2)
    return _MONTHS.get(value[:3].lower(), "")


def _publication_date(article: ET.Element) -> tuple[int | None, str | None]:
    date_node = article.find(".//ArticleDate")
    if date_node is None:
        date_node = article.find(".//JournalIssue/PubDate")

    if date_node is None:
        return None, None

    year_text = date_node.findtext("Year", default="").strip()
    if not year_text:
        medline = date_node.findtext("MedlineDate", default="")
        match = _re.search(r"\b(19|20)\d{2}\b", medline)
        year_text = match.group(0) if match else ""

    year = int(year_text) if year_text.isdigit() else None
    if not year:
        return None, None

    month = _normalise_month(date_node.findtext("Month"))
    day = (date_node.findtext("Day", default="") or "").strip().zfill(2)

    if month and day and day != "00":
        return year, f"{year}-{month}-{day}"
    if month:
        return year, f"{year}-{month}"
    return year, str(year)


def _first_author(article: ET.Element) -> str:
    author = article.find(".//AuthorList/Author")
    if author is None:
        return ""
    collective = author.findtext("CollectiveName", default="").strip()
    if collective:
        return collective
    last = author.findtext("LastName", default="").strip()
    initials = author.findtext("Initials", default="").strip()
    if last and initials:
        return f"{last} {initials}"
    return last or author.findtext("ForeName", default="").strip()


def _fetch_cited_by_counts(pmids: list[str]) -> dict[str, int]:
    """Best-effort cited-by counts from Europe PMC. Never blocks the pipeline on failure."""
    counts: dict[str, int] = {}
    if not pmids:
        return counts

    for i in range(0, len(pmids), 20):
        batch = pmids[i: i + 20]
        query = "(" + " OR ".join(f"EXT_ID:{pmid}" for pmid in batch) + ") AND SRC:MED"
        try:
            resp = requests.get(
                _EUROPE_PMC_SEARCH,
                params={
                    "query": query,
                    "format": "json",
                    "pageSize": len(batch),
                    "resultType": "core",
                },
                timeout=8,
            )
            resp.raise_for_status()
            results = resp.json().get("resultList", {}).get("result", [])
        except requests.RequestException as exc:
            print(f"[PubMed] Europe PMC citation-count lookup skipped: {exc}")
            continue

        for result in results:
            pmid = str(result.get("pmid") or result.get("id") or "")
            try:
                counts[pmid] = int(result.get("citedByCount") or 0)
            except (TypeError, ValueError):
                continue

    return counts


def _esearch(query: str) -> list[str]:
    """
    Search PubMed with two-level fallback.

    L1  Plain-text query + date filter (PubMed ATM maps terms to MeSH automatically).
        This is the normal path when queries come from _build_queries().
    L2  Strip any rogue [Field] tags + retry (safety net for malformed queries).
    L3  Minimal 3-term core query (last resort).
    """
    base_params = {
        "db": "pubmed",
        "retmode": "json",
        "retmax": PUBMED_MAX_RESULTS,
    }
    if NCBI_API_KEY:
        base_params["api_key"] = NCBI_API_KEY

    clean_query = _strip_qualifiers(query)

    # L1: standard query with human + date filters
    term_l1 = f'{clean_query} AND "last 10 years"[PDat] AND "humans"[MeSH]'
    pmids = _run_esearch(term_l1, base_params)
    if pmids:
        return pmids

    # L2: drop date + species filters (rare topics / older literature)
    print(f"[PubMed] L1 returned 0 — retrying without date filter: {clean_query[:100]}")
    pmids = _run_esearch(clean_query, base_params)
    if pmids:
        return pmids

    # L3: minimal core terms
    minimal = _minimal_fallback(clean_query)
    if minimal and minimal != clean_query:
        print(f"[PubMed] L2 returned 0 — minimal fallback: {minimal[:100]}")
        pmids = _run_esearch(minimal, base_params)

    return pmids


def _efetch(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "rettype": "abstract",
        "retmode": "xml",
        "id": ",".join(pmids),
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    resp = requests.get(f"{_BASE}/efetch.fcgi", params=params, timeout=20)
    resp.raise_for_status()

    articles = []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        print(f"[PubMed] XML parse error: {exc}")
        return []

    for article in root.findall(".//PubmedArticle"):
        pmid     = article.findtext(".//PMID", default="")
        title    = "".join(article.find(".//ArticleTitle").itertext()).strip() if article.find(".//ArticleTitle") is not None else ""
        parts    = [" ".join(t.itertext()) for t in article.findall(".//AbstractText")]
        abstract = " ".join(parts).strip()
        year, publication_date = _publication_date(article)
        publication_types = [
            " ".join(pt.itertext()).strip()
            for pt in article.findall(".//PublicationTypeList/PublicationType")
            if " ".join(pt.itertext()).strip()
        ]

        if abstract:
            articles.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "publication_date": publication_date,
                "journal": _first_text(article, [".//Journal/Title"]),
                "journal_abbreviation": _first_text(article, [".//Journal/ISOAbbreviation"]),
                "publication_types": publication_types,
                "doi": _first_text(article, [".//ArticleId[@IdType='doi']"]),
                "pmc": _first_text(article, [".//ArticleId[@IdType='pmc']"]),
                "first_author": _first_author(article),
            })

    cited_by = _fetch_cited_by_counts([a["pmid"] for a in articles])
    for article in articles:
        article["cited_by_count"] = cited_by.get(article["pmid"])

    return articles


def fetch_articles_for_queries(queries: list[str]) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []

    for query in queries:
        try:
            pmids    = _esearch(query)
            articles = _efetch(pmids)
            for a in articles:
                if a["pmid"] not in seen:
                    seen.add(a["pmid"])
                    results.append(a)
        except requests.RequestException as exc:
            print(f"[PubMed] Request failed for '{query}': {exc}")
        time.sleep(_RATE_DELAY)

    print(f"[PubMed] Retrieved {len(results)} unique articles.")
    return results
