import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.prompt_budget import format_numbered_passages, token_count, trim_to_tokens
from pipeline.llm_caller import _build_chat_payload, _fit_groq_payload, _payload_size_bytes


def test_trim_to_tokens_respects_budget():
    text = "alpha beta gamma " * 200
    trimmed = trim_to_tokens(text, 25)

    assert token_count(trimmed) <= 25
    assert trimmed.endswith("...")


def test_format_numbered_passages_preserves_metadata_under_budget():
    chunks = [
        {
            "pmid": "123",
            "title": "A useful trial",
            "year": 2024,
            "text": "clinically relevant finding " * 200,
        },
        {
            "pmid": "456",
            "title": "Another useful trial",
            "year": 2023,
            "text": "confirmatory result " * 200,
        },
    ]

    block = format_numbered_passages(
        chunks,
        total_tokens=80,
        per_passage_tokens=30,
        include_title=True,
        include_year=True,
    )

    assert "[1] A useful trial (2024) PMID:123" in block
    assert "[2] Another useful trial (2023) PMID:456" in block
    assert token_count(block) <= 80


def test_generation_budget_can_include_twelve_papers():
    chunks = [
        {
            "pmid": str(i),
            "title": f"Relevant trial {i}",
            "year": 2024,
            "text": "result and conclusion " * 300,
        }
        for i in range(1, 13)
    ]

    block = format_numbered_passages(
        chunks,
        total_tokens=3600,
        per_passage_tokens=260,
        include_title=True,
        include_year=True,
    )

    assert "[12] Relevant trial 12" in block
    assert token_count(block) <= 3600


def test_fit_groq_payload_trims_user_message_to_byte_budget():
    payload = _build_chat_payload("llama-test", "system prompt", "evidence " * 1000, 512)

    fitted, original_size, fitted_size = _fit_groq_payload(payload, 1200)

    assert original_size > 1200
    assert fitted_size <= 1200
    assert _payload_size_bytes(fitted) <= 1200
    assert fitted["messages"][0]["content"] == "system prompt"
    assert fitted["messages"][1]["content"].endswith("request-size limit.]")
