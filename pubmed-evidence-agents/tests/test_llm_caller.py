import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from pipeline import llm_caller


class _FakeResponse:
    def __init__(self, status_code, *, headers=None, text="", content="ok"):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self._content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP status {self.status_code}")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_groq_retries_after_429_then_returns(monkeypatch):
    responses = [
        _FakeResponse(429, headers={"retry-after": "2"}, text="rate limited"),
        _FakeResponse(200, content="done"),
    ]
    sleeps = []

    monkeypatch.setattr(llm_caller, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_caller, "GROQ_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(llm_caller, "GROQ_MIN_REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(llm_caller, "GROQ_MAX_RETRY_WAIT_SECONDS", 120)
    monkeypatch.setattr(llm_caller.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        llm_caller.requests,
        "post",
        lambda *args, **kwargs: responses.pop(0),
    )

    assert llm_caller._call_groq("model", "system", "user", 16) == "done"
    assert sleeps == [2.0]


def test_groq_does_not_sleep_after_final_429(monkeypatch):
    sleeps = []

    monkeypatch.setattr(llm_caller, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_caller, "GROQ_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(llm_caller, "GROQ_MIN_REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(llm_caller.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        llm_caller.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            429,
            headers={"retry-after": "30"},
            text="quota exceeded",
        ),
    )

    with pytest.raises(RuntimeError, match="Rate limit persists after 1 attempts"):
        llm_caller._call_groq("model", "system", "user", 16)

    assert sleeps == []


def test_groq_verifier_requests_json_without_reasoning(monkeypatch):
    captured = {}

    monkeypatch.setattr(llm_caller, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm_caller, "GROQ_MIN_REQUEST_INTERVAL_SECONDS", 0)

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]
        return _FakeResponse(
            200,
            content='{"verdict":"pass","unsupported_claims":[],"suggested_corrections":[]}',
        )

    monkeypatch.setattr(llm_caller.requests, "post", fake_post)

    llm_caller._call_groq(
        "qwen/qwen3.6-27b",
        "system",
        "user",
        128,
        json_mode=True,
        disable_reasoning=True,
    )

    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["reasoning_effort"] == "none"
