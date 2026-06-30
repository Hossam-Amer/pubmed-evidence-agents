"""Calibrated confidence — derive the answer's confidence from real signals
(retrieval strength + grounding + evidence breadth) instead of trusting the
generator's self-reported value (see RETRIEVAL_PLAN.md §5.1).

Thresholds are placeholders — calibrate on BioASQ/MedQA (PRD §7).
"""
from models.schemas import VerifierOutput

# Tunable thresholds on the mean of the top-N FAISS cosine scores
# (MedCPT CLS embeddings, IndexFlatIP). Placeholders — calibrate on eval data.
_HIGH_SCORE = 0.40
_LOW_SCORE = 0.20
_TOP_N = 5


def calibrate_confidence(
    chunks: list[dict],
    verification: VerifierOutput | None,
    self_reported: str,
) -> tuple[str, dict]:
    """Return (level, breakdown). `level` is one of high|medium|low.

    `breakdown` exposes the raw signals so the UI can explain the score.
    """
    scores = sorted((float(c.get("score", 0.0)) for c in chunks), reverse=True)[:_TOP_N]
    mean_top = sum(scores) / len(scores) if scores else 0.0
    n_pmids = len({c.get("pmid") for c in chunks if c.get("pmid")})

    verdict = verification.verdict if verification else "pass"
    n_unsupported = len(verification.unsupported_claims) if verification else 0
    grounded = (verdict == "pass") and (n_unsupported == 0)

    if grounded and n_pmids >= 2 and mean_top >= _HIGH_SCORE:
        level = "high"
    elif (not grounded) or n_pmids < 1 or mean_top < _LOW_SCORE:
        level = "low"
    else:
        level = "medium"

    breakdown = {
        "level": level,
        "self_reported": self_reported,
        "mean_top_score": round(mean_top, 4),
        "supporting_pmids": n_pmids,
        "verifier_verdict": verdict,
        "unsupported_claims": n_unsupported,
        "thresholds": {"high_score": _HIGH_SCORE, "low_score": _LOW_SCORE, "top_n": _TOP_N},
    }
    return level, breakdown
