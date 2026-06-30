"""Conflicting-evidence (consensus) detection over the retrieved top-K
(see RETRIEVAL_PLAN.md §5.2).

One LLM pass classifies each passage's stance toward the PICO outcome and
returns an aggregate agreement label. Graceful fallback on parse failure,
matching the rest of the pipeline.
"""
import json
import re
from config import OPENBIO_MODEL_ID
from pipeline.llm_caller import call_llm

_SYSTEM_PROMPT = """You are an evidence-synthesis analyst.
Given a clinical PICO and several source passages, judge whether the passages
AGREE about the effect of the Intervention on the Outcome.

Classify each passage's stance ("supports", "refutes", or "neutral"), then
summarise the overall agreement.

Return ONLY valid JSON — no markdown, no prose outside the JSON:
{"agreement": "strong|mixed|conflicting",
 "supporting_pmids": ["pmid", ...],
 "conflicting_pmids": ["pmid", ...],
 "summary": "one sentence; describe the disagreement if any, else 'consistent evidence'"}

- "strong": passages broadly agree.
- "mixed": mostly agree, minor divergence.
- "conflicting": passages reach opposing conclusions."""

_FALLBACK = {
    "agreement": "unknown",
    "supporting_pmids": [],
    "conflicting_pmids": [],
    "summary": "",
}


def detect_consensus(pico: dict, chunks: list[dict]) -> dict:
    """Return an agreement summary over the retrieved chunks. Never raises."""
    if not chunks:
        return dict(_FALLBACK)

    passages = "\n\n".join(
        f"[{i}] PMID:{c.get('pmid','?')}\n{c.get('text', '')[:600]}"
        for i, c in enumerate(chunks, 1)
    )
    user_prompt = f"PICO: {json.dumps(pico)}\n\nSource passages:\n{passages}"

    try:
        raw = call_llm(OPENBIO_MODEL_ID, _SYSTEM_PROMPT, user_prompt, max_tokens=512)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "agreement": data.get("agreement", "unknown"),
                "supporting_pmids": data.get("supporting_pmids", []),
                "conflicting_pmids": data.get("conflicting_pmids", []),
                "summary": data.get("summary", ""),
            }
    except Exception as exc:  # parse error, network, rate limit — degrade gracefully
        print(f"[Consensus] Falling back to 'unknown': {exc}")

    return dict(_FALLBACK)
