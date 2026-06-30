import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")
_ELLIPSIS = "..."


def token_count(text: str) -> int:
    return len(_ENCODING.encode(text or ""))


def trim_to_tokens(text: str, max_tokens: int) -> str:
    """Trim text to a token budget while keeping valid decoded text."""
    if not text or max_tokens <= 0:
        return ""

    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text

    suffix_tokens = _ENCODING.encode(_ELLIPSIS)
    keep = max(0, max_tokens - len(suffix_tokens))
    return _ENCODING.decode(tokens[:keep]).rstrip() + _ELLIPSIS


def format_numbered_passages(
    chunks: list[dict],
    *,
    total_tokens: int,
    per_passage_tokens: int,
    include_title: bool = True,
    include_year: bool = True,
) -> str:
    """
    Build a compact evidence block. Passage numbering and PMID metadata are
    preserved so downstream citations still map back to the selected chunks.
    """
    if not chunks or total_tokens <= 0:
        return ""

    lines: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        pmid = chunk.get("pmid", "?")
        title = chunk.get("title", "")
        year = chunk.get("year") or "n.d."

        if include_title:
            heading = f"[{i}] {title} ({year}) PMID:{pmid}" if include_year else f"[{i}] PMID:{pmid} {title}"
        else:
            heading = f"[{i}] PMID:{pmid}"

        current = "\n\n".join(lines)
        prefix = f"{current}\n\n{heading}\n" if current else f"{heading}\n"
        prefix_tokens = token_count(prefix)
        if prefix_tokens >= total_tokens:
            break

        body_budget = min(per_passage_tokens, total_tokens - prefix_tokens)
        while body_budget >= 0:
            body = trim_to_tokens(chunk.get("text", ""), body_budget)
            candidate = f"{prefix}{body}".rstrip()
            if token_count(candidate) <= total_tokens:
                lines.append(f"{heading}\n{body}".rstrip())
                break
            body_budget -= 1

    return "\n\n".join(lines)
