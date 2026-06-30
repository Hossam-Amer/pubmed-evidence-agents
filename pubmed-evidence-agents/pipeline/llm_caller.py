import json
import time
from email.utils import parsedate_to_datetime
from threading import Lock

import requests
import torch

from config import (
    DEPLOY_MODE,
    HF_TOKEN,
    GROQ_API_KEY,
    GROQ_MAX_REQUEST_BYTES,
    GROQ_MAX_RETRY_WAIT_SECONDS,
    GROQ_MIN_REQUEST_INTERVAL_SECONDS,
    GROQ_RETRY_ATTEMPTS,
    together_client,
)
from pipeline.model_loader import load_causal_lm

_HF_API_BASE = "https://router.huggingface.co/hf-inference/models"
_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_TRUNCATION_NOTICE = "\n\n[Input truncated to fit Groq request-size limit.]"
_GROQ_LOCK = Lock()
_last_groq_request_at = 0.0


def _payload_size_bytes(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _build_chat_payload(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    json_mode: bool = False,
    disable_reasoning: bool = False,
) -> dict:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if disable_reasoning:
        payload["reasoning_effort"] = "none"
    return payload


def _coerce_retry_after(value: str | None, default: float = 10.0) -> float:
    if not value:
        return default

    try:
        return max(float(value), 0.0)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
        return max(retry_at.timestamp() - time.time(), 0.0)
    except (TypeError, ValueError, IndexError, OverflowError):
        return default


def _wait_for_groq_slot() -> None:
    """Serialize Groq calls in this process to avoid avoidable burst 429s."""
    global _last_groq_request_at

    if GROQ_MIN_REQUEST_INTERVAL_SECONDS <= 0:
        return

    with _GROQ_LOCK:
        now = time.monotonic()
        wait = GROQ_MIN_REQUEST_INTERVAL_SECONDS - (now - _last_groq_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_groq_request_at = time.monotonic()


def _fit_groq_payload(payload: dict, max_request_bytes: int) -> tuple[dict, int, int]:
    """
    Groq can reject large JSON request bodies even when token budgets look valid.
    Trim only the user message and preserve system instructions.
    """
    original_size = _payload_size_bytes(payload)
    if original_size <= max_request_bytes:
        return payload, original_size, original_size

    user_message = payload["messages"][-1]
    original_content = user_message.get("content") or ""
    low = 0
    high = len(original_content)
    best_content = None
    best_size = None

    while low <= high:
        mid = (low + high) // 2
        candidate = original_content[:mid].rstrip() + _TRUNCATION_NOTICE
        user_message["content"] = candidate
        size = _payload_size_bytes(payload)
        if size <= max_request_bytes:
            best_content = candidate
            best_size = size
            low = mid + 1
        else:
            high = mid - 1

    if best_content is None:
        user_message["content"] = original_content
        raise RuntimeError(
            "[Groq] Payload too large even after trimming the user prompt. "
            "Lower GROQ_MAX_REQUEST_BYTES or shorten the system prompt."
        )

    user_message["content"] = best_content
    return payload, original_size, best_size or original_size


def call_llm(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 512,
    json_mode: bool = False,
    disable_reasoning: bool = False,
) -> str:
    """
    Route based on DEPLOY_MODE:
      "groq"    -> Groq API (model selected by the caller)
      "hf"      -> HF Inference API (medical fine-tunes, free but restricted)
      "together"-> Together AI serverless
      "local"   -> local HuggingFace transformers
    """
    if DEPLOY_MODE == "local":
        return _call_local(model_id, system_prompt, user_prompt, max_tokens)
    if DEPLOY_MODE == "hf":
        return _call_hf_inference(model_id, system_prompt, user_prompt, max_tokens)
    if DEPLOY_MODE == "groq":
        return _call_groq(
            model_id,
            system_prompt,
            user_prompt,
            max_tokens,
            json_mode=json_mode,
            disable_reasoning=disable_reasoning,
        )
    return _call_together(model_id, system_prompt, user_prompt, max_tokens)


def _call_together(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    resp = together_client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip()


def _call_groq(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    json_mode: bool = False,
    disable_reasoning: bool = False,
) -> str:
    if not GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY not set; required for DEPLOY_MODE=groq")

    payload = _build_chat_payload(
        model_id,
        system_prompt,
        user_prompt,
        max_tokens,
        json_mode=json_mode,
        disable_reasoning=disable_reasoning,
    )
    payload, original_size, fitted_size = _fit_groq_payload(payload, GROQ_MAX_REQUEST_BYTES)
    if fitted_size < original_size:
        print(
            "[Groq] Trimmed request body "
            f"from {original_size / 1024:.1f} KiB to {fitted_size / 1024:.1f} KiB"
        )

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    last_rate_limit_body = ""
    attempts = max(GROQ_RETRY_ATTEMPTS, 1)
    for attempt in range(1, attempts + 1):
        _wait_for_groq_slot()
        resp = requests.post(_GROQ_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 413:
            size_kb = _payload_size_bytes(payload) / 1024
            raise RuntimeError(
                "[Groq] Payload too large "
                f"({size_kb:.1f} KiB request body). Lower GROQ_MAX_REQUEST_BYTES, "
                "RAG_CONTEXT_TOKEN_BUDGET, RAG_PASSAGE_TOKEN_BUDGET, "
                "VERIFY_CONTEXT_TOKEN_BUDGET, or PICO_INPUT_TOKEN_BUDGET in your .env."
            )
        if resp.status_code == 429:
            last_rate_limit_body = resp.text[:500]
            if attempt == attempts:
                break
            retry_after = _coerce_retry_after(resp.headers.get("retry-after"))
            wait = min(retry_after, GROQ_MAX_RETRY_WAIT_SECONDS)
            print(f"[Groq] Rate limited, waiting {wait:.0f}s (attempt {attempt}/{attempts})")
            if wait > 0:
                time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    detail = f" Last response: {last_rate_limit_body}" if last_rate_limit_body else ""
    raise RuntimeError(
        f"[Groq] Rate limit persists after {attempts} attempts."
        " Wait for the Groq quota window to reset, lower prompt budgets, or switch DEPLOY_MODE."
        f"{detail}"
    )


def _call_hf_inference(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    if not HF_TOKEN:
        raise EnvironmentError("HF_TOKEN not set; required for DEPLOY_MODE=hf")

    url = f"{_HF_API_BASE}/{model_id}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = _build_chat_payload(model_id, system_prompt, user_prompt, max_tokens)

    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 503:
            try:
                wait = float(resp.json().get("estimated_time", 20))
            except Exception:
                wait = 20.0
            print(f"[HF] {model_id} loading, waiting {min(wait, 30):.0f}s (attempt {attempt + 1}/3)")
            time.sleep(min(wait, 30))
            continue
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    raise RuntimeError(f"[HF] {model_id} unavailable after 3 attempts")


def _call_local(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> str:
    tokenizer, model = load_causal_lm(model_id)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        input_ids = tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True
        ).to(model.device)
    else:
        text = f"[INST] {system_prompt}\n\n{user_prompt} [/INST]"
        input_ids = tokenizer(text, return_tensors="pt").input_ids.to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][input_ids.shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
