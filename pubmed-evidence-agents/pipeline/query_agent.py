import json
import re
from config import OPENBIO_MODEL_ID, PICO_INPUT_TOKEN_BUDGET
from pipeline.llm_caller import call_llm
from pipeline.prompt_budget import trim_to_tokens
from models.schemas import PICOQuery

# LLM extracts SHORT clinical CONCEPTS only — no query syntax, no field tags.
# Code builds the actual PubMed queries from those concepts deterministically.
_SYSTEM_PROMPT = """You are a clinical information specialist.
Extract the PICO elements from the clinical case. Be CONCISE — each field is a short phrase (2-5 words), NOT a full sentence.

Fields:
- P: the primary patient CONDITION, including risk group when it matters — 2-5 words (e.g. "type 2 diabetes", "high-risk prostate cancer", "acute asthma"). Do NOT copy raw staging values, lab numbers, or scores into this field.
- I: the main INTERVENTION — any of: a drug or drug class, a procedure, a radiotherapy strategy, a surgery, an imaging approach, or a management strategy. 1-5 words, common clinical shorthand (e.g. "SGLT2 inhibitor", "prostate-only radiotherapy", "active surveillance", "carbapenem").
- C: the comparator — use it whether stated explicitly OR clearly implied by the question. Phrasing like "omitting X", "instead of X", "vs X", or "should we add X" implies a comparison (e.g. omitting nodal radiotherapy implies "elective nodal irradiation"). Set null ONLY when there is genuinely nothing to compare against.
- O: the CLINICAL outcome category — 2-4 words, keep it broad (e.g. "cardiovascular mortality", "biochemical recurrence", "lung function"). Do NOT include study design words like "randomized" or "meta-analysis".
- Q: ONE free-text PubMed query in natural clinician phrasing that best captures the core question — 4-10 words, the search you would actually type (e.g. "prostate-only versus whole-pelvic radiotherapy high-risk prostate cancer"). Do NOT include staging values, lab numbers, or scores.

Return ONLY valid JSON. No markdown, no explanation.
Schema: {"P": "...", "I": "...", "C": "..." or null, "O": "...", "Q": "..."}"""

_STRICT_SUFFIX = "\n\nIMPORTANT: Return ONLY the JSON object. Start with { and end with }. No other text."


def _build_queries(P: str, I: str, O: str, C: str | None, free_text: str = "") -> list[str]:
    """
    Build PubMed queries from PICO concepts.
    Three are deterministic templates (specific -> broad); a fourth is the
    LLM's free-text query, which acts as a safety net for cases that don't
    fit the templates (non-drug interventions, implicit comparisons, etc.).
    All plain-text — PubMed's Automatic Term Mapping handles MeSH lookup.
    """
    P = P.strip()
    I = I.strip()
    O = O.strip()
    C = C.strip() if C else ""

    queries = []

    # Q1: intervention + outcome + population  (primary evidence query)
    queries.append(f"{I} {O} {P}")

    # Q2: comparison angle if available, else broader intervention + population search
    if C:
        queries.append(f"{I} versus {C} {P}")
    else:
        queries.append(f"{I} {P} efficacy safety")

    # Q3: systematic review / meta-analysis on the core intervention + outcome
    queries.append(f"{I} {O} meta-analysis")

    # Q4: LLM free-text query — robustness net for cases the templates miss
    free_text = (free_text or "").strip()
    if free_text:
        queries.append(free_text)

    # Dedupe case-insensitively while preserving order
    seen: set[str] = set()
    deduped = []
    for q in queries:
        key = q.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped


def extract_pico(clinical_text: str) -> PICOQuery:
    """
    Extract PICO concepts via LLM, then build PubMed queries in code.
    Retries up to 2 times on JSON parse failure.
    """
    user_content = trim_to_tokens(clinical_text.strip(), PICO_INPUT_TOKEN_BUDGET)

    last_raw = ""
    for attempt in range(3):
        system = _SYSTEM_PROMPT + (_STRICT_SUFFIX if attempt > 0 else "")
        raw = call_llm(OPENBIO_MODEL_ID, system, user_content, max_tokens=256)
        last_raw = raw
        try:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                continue
            data = json.loads(match.group())

            P = str(data.get("P") or "").strip()
            I = str(data.get("I") or "").strip()
            O = str(data.get("O") or "").strip()
            Q = str(data.get("Q") or "").strip()
            C = data.get("C") or None
            if isinstance(C, str):
                C = C.strip() or None

            if not P or not I or not O:
                continue

            queries = _build_queries(P, I, O, C, free_text=Q)
            return PICOQuery(P=P, I=I, C=C, O=O, queries=queries)

        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    raise ValueError(
        f"PICO extraction failed after 3 attempts. Last model output:\n{last_raw}"
    )
