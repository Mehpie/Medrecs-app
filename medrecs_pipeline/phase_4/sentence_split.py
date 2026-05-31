from __future__ import annotations

import re
from dataclasses import dataclass

# Abbreviations that should not trigger a sentence break after the period.
_ABBREV_PATTERN = re.compile(
    r"\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|e\.g|i\.e|No|Acc|DOS|DOB|Pt|Rx|"
    r"approx|dept|vol|fig|ref|ed|al|St)\.$",
    re.IGNORECASE,
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class SentenceSpan:
    text: str
    unit_ids: tuple[str, ...]
    atomic: bool = False


def sentence_split(text: str) -> list[str]:
    """Rule-based sentence splitter with common medical abbreviation guards."""
    text = (text or "").strip()
    if not text:
        return []

    parts = _SENTENCE_END.split(text)
    sentences: list[str] = []
    buffer = ""

    for part in parts:
        candidate = f"{buffer} {part}".strip() if buffer else part.strip()
        if not candidate:
            continue
        if (
            _ABBREV_PATTERN.search(candidate)
            or re.search(r"\d+\.\d+$", candidate)
            or re.search(r"\b\d+\.$", candidate)
        ):
            buffer = candidate
            continue
        sentences.append(candidate)
        buffer = ""

    if buffer:
        if sentences:
            sentences[-1] = f"{sentences[-1]} {buffer}".strip()
        else:
            sentences.append(buffer)

    return [s for s in sentences if s.strip()]
