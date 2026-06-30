import json
import re
from config import OPENBIO_MODEL_ID, RAG_CONTEXT_TOKEN_BUDGET, RAG_PASSAGE_TOKEN_BUDGET
from pipeline.llm_caller import call_llm
from pipeline.prompt_budget import format_numbered_passages
from models.schemas import GeneratorOutput

_SYSTEM_PROMPT = """You are a clinical evidence synthesizer specializing in evidence-based medicine.

Rules:
1. Answer the clinical question using ONLY the provided context passages — never use outside knowledge.
2. Add inline citation markers [1], [2] etc. that correspond to the passage numbers below.
3. If the evidence is insufficient or conflicting, state this explicitly.
4. Self-assess confidence: "high" if multiple passages strongly support the answer, "medium" if partial, "low" if weak or conflicting.
5. Review every provided passage before synthesizing the answer.
6. When available, synthesize and cite 4 to 6 distinct relevant papers, especially
   independent studies that agree, disagree, or cover different outcomes.
7. Never add a citation merely to reach a number. Exclude irrelevant papers and do
   not claim that a paper supports a statement unless its passage directly does.

Return ONLY valid JSON — no markdown, no explanation outside the JSON:
{"answer": "...", "citations": [{"id": 1, "pmid": "...", "title": "...", "year": 0}], "confidence": "high|medium|low"}"""


def build_evidence_context(chunks: list[dict]) -> str:
    return format_numbered_passages(
        chunks,
        total_tokens=RAG_CONTEXT_TOKEN_BUDGET,
        per_passage_tokens=RAG_PASSAGE_TOKEN_BUDGET,
        include_title=True,
        include_year=True,
    )


def generate_answer(
    clinical_question: str,
    pico: dict,
    chunks: list[dict],
    fix_instructions: list[str] = [],
) -> GeneratorOutput:
    """
    Generate a cited answer from the top-k chunks.
    If fix_instructions provided, prepend correction guidance to the prompt.
    """
    context = build_evidence_context(chunks)
    user_prompt = (
        f"Clinical question: {clinical_question}\n\n"
        f"PICO summary: {json.dumps(pico)}\n\n"
        f"Context passages:\n{context}"
    )

    if fix_instructions:
        correction_block = "\n".join(f"- {c}" for c in fix_instructions)
        user_prompt = (
            f"The previous answer contained unsupported claims that must be corrected:\n"
            f"{correction_block}\n\n"
            f"Generate a corrected answer using only the context below.\n\n"
            + user_prompt
        )

    raw = call_llm(OPENBIO_MODEL_ID, _SYSTEM_PROMPT, user_prompt, max_tokens=1024)

    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return GeneratorOutput(**data)
    except (json.JSONDecodeError, ValueError):
        pass

    # Graceful fallback: return raw text, no citations, low confidence
    return GeneratorOutput(answer=raw.strip(), citations=[], confidence="low")
