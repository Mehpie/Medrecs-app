from __future__ import annotations

from typing import Iterable, List, Tuple

from medrecs_pipeline.phase_5.schemas import Tag, TaggedChunk
from medrecs_pipeline.phase_5.thresholds import ThresholdConfig, apply_thresholds
from medrecs_pipeline.phase_5.vocab import is_clinical_class


def dedupe_legal_tags(tags: Iterable[Tag]) -> List[Tag]:
    """Keep highest confidence per (tag_class, start, end)."""
    best: dict[tuple[str, int, int], Tag] = {}
    for tag in tags:
        key = (tag.tag_class, tag.start, tag.end)
        prev = best.get(key)
        if prev is None or tag.confidence > prev.confidence:
            best[key] = tag
    return list(best.values())


def merge_legal_into_chunk(
    chunk: TaggedChunk,
    *,
    rule_tags: List[Tag],
    gemini_tags: List[Tag],
    config: ThresholdConfig,
) -> Tuple[TaggedChunk, int, int]:
    """
    Preserve clinical_tags from Phase 5; merge and threshold legal tags.
    Returns (updated_chunk, legal_added_count, invalid_class_dropped).
    """
    clinical_frozen = [t.model_copy() for t in chunk.clinical_tags]
    uncertain_clinical = [t for t in chunk.uncertain_tags if is_clinical_class(t.tag_class)]

    merged_raw = dedupe_legal_tags(list(chunk.legal_tags) + rule_tags + gemini_tags)
    before_count = len(chunk.legal_tags)

    _, legal_out, uncertain_legal, dropped = apply_thresholds(
        clinical_frozen,
        merged_raw,
        config=config,
    )

    uncertain_merged = dedupe_legal_tags(uncertain_clinical + uncertain_legal)

    data = chunk.model_dump()
    data.update(
        {
            "clinical_tags": clinical_frozen,
            "legal_tags": legal_out,
            "uncertain_tags": uncertain_merged,
            "tagging_method": "gemini+legal51",
        }
    )
    updated = TaggedChunk.model_validate(data)
    added = max(0, len(legal_out) - before_count)
    return updated, added, dropped


def assert_clinical_unchanged(before: TaggedChunk, after: TaggedChunk) -> bool:
    return [t.model_dump() for t in before.clinical_tags] == [
        t.model_dump() for t in after.clinical_tags
    ]
