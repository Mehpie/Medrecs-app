from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from pydantic import ValidationError

from .schemas import LlmTag, Tag


@dataclass
class SpanRepairStats:
    verified: int = 0
    repaired: int = 0
    dropped: int = 0
    llm_rows_dropped: int = 0


def _normalize_surface(s: str) -> str:
    return " ".join(s.split())


def llm_tags_to_tags(llm_tags: List[LlmTag], body_text: str) -> Tuple[List[Tag], SpanRepairStats]:
    """Convert lenient LLM tags to strict Tag objects with span repair."""
    stats = SpanRepairStats()
    candidates: List[Tag] = []
    for lt in llm_tags:
        surface = (lt.surface or "").strip()
        if not surface:
            stats.llm_rows_dropped += 1
            continue
        tag: Tag | None = None
        if lt.start is not None and lt.end is not None and lt.end > lt.start:
            try:
                tag = Tag(
                    tag_class=lt.tag_class,
                    surface=surface,
                    start=lt.start,
                    end=lt.end,
                    confidence=lt.confidence,
                )
            except ValidationError:
                tag = None
        if tag is None:
            idx = body_text.find(surface)
            use_surface = surface
            if idx < 0:
                normalized = _normalize_surface(surface)
                idx = body_text.find(normalized) if normalized else -1
                if idx >= 0:
                    use_surface = normalized
            if idx < 0:
                stats.llm_rows_dropped += 1
                continue
            try:
                tag = Tag(
                    tag_class=lt.tag_class,
                    surface=use_surface,
                    start=idx,
                    end=idx + len(use_surface),
                    confidence=lt.confidence,
                )
            except ValidationError:
                stats.llm_rows_dropped += 1
                continue
        candidates.append(tag)

    repaired, repair_stats = validate_and_repair_tags(candidates, body_text)
    stats.verified = repair_stats.verified
    stats.repaired = repair_stats.repaired
    stats.dropped = repair_stats.dropped
    return repaired, stats


def validate_and_repair_tag(tag: Tag, body_text: str) -> Tuple[Tag | None, str]:
    """
    Ensure tag span aligns with body_text.
    Returns (tag, status) where status is verified | repaired | dropped.
    """
    if tag.start < 0 or tag.end > len(body_text):
        return _try_find(tag, body_text)

    slice_text = body_text[tag.start : tag.end]
    if slice_text == tag.surface:
        return tag, "verified"

    if _normalize_surface(slice_text) == _normalize_surface(tag.surface):
        repaired = tag.model_copy(update={"surface": slice_text})
        return repaired, "verified"

    return _try_find(tag, body_text)


def _try_find(tag: Tag, body_text: str) -> Tuple[Tag | None, str]:
    if not tag.surface:
        return None, "dropped"

    idx = body_text.find(tag.surface)
    if idx >= 0:
        return (
            tag.model_copy(update={"start": idx, "end": idx + len(tag.surface)}),
            "repaired",
        )

    normalized = _normalize_surface(tag.surface)
    if normalized and normalized != tag.surface:
        idx = body_text.find(normalized)
        if idx >= 0:
            return (
                tag.model_copy(
                    update={"start": idx, "end": idx + len(normalized), "surface": normalized}
                ),
                "repaired",
            )

    return None, "dropped"


def validate_and_repair_tags(
    tags: List[Tag], body_text: str
) -> Tuple[List[Tag], SpanRepairStats]:
    stats = SpanRepairStats()
    out: List[Tag] = []
    for tag in tags:
        fixed, status = validate_and_repair_tag(tag, body_text)
        if fixed is None:
            stats.dropped += 1
            continue
        if status == "repaired":
            stats.repaired += 1
        else:
            stats.verified += 1
        out.append(fixed)
    return out, stats
