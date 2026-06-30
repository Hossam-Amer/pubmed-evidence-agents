import pytest
from pydantic import ValidationError

from models.schemas import VerifierOutput
from pipeline import verifier
from pipeline.generator import build_evidence_context


def _chunks():
    return [
        {
            "pmid": "123",
            "title": "Trial title",
            "year": 2024,
            "text": "The intervention reduced the measured outcome.",
        }
    ]


def test_parser_accepts_json_after_reasoning_text():
    result = verifier._parse_verifier_output(
        '<think>checking evidence</think>\n'
        '{"verdict":"pass","unsupported_claims":[],"suggested_corrections":[]}'
    )
    assert result.verdict == "pass"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "verdict": "pass",
            "unsupported_claims": ["contradiction"],
            "suggested_corrections": [],
        },
        {
            "verdict": "fix",
            "unsupported_claims": [],
            "suggested_corrections": [],
        },
        {
            "verdict": "unknown",
            "unsupported_claims": [],
            "suggested_corrections": [],
        },
    ],
)
def test_schema_rejects_inconsistent_verdicts(payload):
    with pytest.raises(ValidationError):
        VerifierOutput(**payload)


def test_malformed_responses_fail_closed_after_retry(monkeypatch):
    calls = []

    def fake_call(*args, **kwargs):
        calls.append(args)
        return "not json"

    monkeypatch.setattr(verifier, "call_llm", fake_call)
    result = verifier.verify_answer("An answer.", _chunks(), [])

    assert len(calls) == 3
    assert result.verdict == "error"
    assert result.error


def test_citation_mismatch_forces_fix(monkeypatch):
    monkeypatch.setattr(
        verifier,
        "call_llm",
        lambda *args, **kwargs: (
            '{"verdict":"pass","unsupported_claims":[],"suggested_corrections":[]}'
        ),
    )

    result = verifier.verify_answer(
        "The intervention helped [1].",
        _chunks(),
        [{"id": 1, "pmid": "wrong"}],
    )

    assert result.verdict == "fix"
    assert "does not match" in result.unsupported_claims[0]


def test_verifier_uses_the_generator_evidence_context(monkeypatch):
    captured = {}

    def fake_call(model_id, system_prompt, user_prompt, max_tokens, **kwargs):
        captured["prompt"] = user_prompt
        captured["system_prompt"] = system_prompt
        captured["max_tokens"] = max_tokens
        captured["options"] = kwargs
        return '{"verdict":"pass","unsupported_claims":[],"suggested_corrections":[]}'

    monkeypatch.setattr(verifier, "call_llm", fake_call)
    chunks = _chunks()
    verifier.verify_answer("An answer.", chunks, [])

    assert build_evidence_context(chunks) in captured["prompt"]
    assert "Report EVERY unsupported claim" in captured["system_prompt"]
    assert "missing, partial, ambiguous" in captured["system_prompt"]
    assert captured["max_tokens"] == 1024
    assert captured["options"] == {"json_mode": True, "disable_reasoning": True}
