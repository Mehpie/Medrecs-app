from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_ENCODING.encode(text))


def take_tail_tokens(text: str, n: int) -> str:
    """Return the last n tokens of text (tiktoken-safe decode)."""
    if not text or n <= 0:
        return ""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= n:
        return text
    return _ENCODING.decode(tokens[-n:])


def take_head_tokens(text: str, n: int) -> str:
    """Return the first n tokens of text (tiktoken-safe decode)."""
    if not text or n <= 0:
        return ""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= n:
        return text
    return _ENCODING.decode(tokens[:n])


def split_text_by_token_budget(text: str, max_tokens: int) -> list[str]:
    """
    Hard-split text into windows of at most max_tokens (word-bounded when possible).
    """
    if max_tokens <= 0:
        return [text] if text else []
    if count_tokens(text) <= max_tokens:
        return [text] if text.strip() else []

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and count_tokens(candidate) > max_tokens:
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks
