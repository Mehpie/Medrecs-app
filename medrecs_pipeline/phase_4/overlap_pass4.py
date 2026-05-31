from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from .schemas import (
    AtomicGroup,
    AtomicGroupsCorpus,
    OverlappedGroup,
    OverlappedGroupsCorpus,
)
from .token_utils import count_tokens, take_tail_tokens


@dataclass(frozen=True)
class OverlapPass4Config:
    overlap_tokens: int = 64
    max_chunk_tokens: int = 768

    @classmethod
    def from_env(cls) -> OverlapPass4Config:
        return cls(
            overlap_tokens=int(os.getenv("PHASE4_OVERLAP_TOKENS", "64")),
            max_chunk_tokens=int(os.getenv("PHASE4_MAX_CHUNK_TOKENS", "768")),
        )


def _join_overlap(prefix: str, body: str) -> str:
    prefix = (prefix or "").strip()
    body = (body or "").strip()
    if not prefix:
        return body
    if not body:
        return prefix
    return f"{prefix}\n\n{body}"


def _fit_overlap_prefix(
    prefix: str,
    body: str,
    *,
    max_chunk_tokens: int,
) -> tuple[str, int]:
    """Shrink prefix until combined text fits max_chunk_tokens."""
    if not prefix:
        return "", 0

    body_tokens = count_tokens(body)
    if body_tokens >= max_chunk_tokens:
        return "", 0

    budget = max_chunk_tokens - body_tokens
    prefix_tokens = count_tokens(prefix)
    while prefix_tokens > budget and prefix_tokens > 0:
        prefix = take_tail_tokens(prefix, prefix_tokens - 1)
        prefix_tokens = count_tokens(prefix)

    if prefix_tokens <= 0:
        return "", 0
    return prefix, prefix_tokens


def _eligible_for_overlap(prev: AtomicGroup, curr: AtomicGroup) -> bool:
    return (
        prev.parent_group_id == curr.parent_group_id
        and prev.atomic_kind == "prose"
        and curr.atomic_kind == "prose"
    )


def apply_overlap(
    groups: List[AtomicGroup],
    *,
    config: OverlapPass4Config,
) -> tuple[List[OverlappedGroup], List[str]]:
    warnings: List[str] = []
    overlapped: List[OverlappedGroup] = []

    for idx, group in enumerate(groups):
        body_text = group.text or ""
        overlap_prefix = ""
        overlap_prefix_tokens = 0
        overlap_source = ""

        prev_atomic: AtomicGroup | None = groups[idx - 1] if idx > 0 else None
        if prev_atomic is not None and _eligible_for_overlap(prev_atomic, group):
            prev_body = prev_atomic.text or ""
            raw_prefix = take_tail_tokens(prev_body, config.overlap_tokens)
            overlap_prefix, overlap_prefix_tokens = _fit_overlap_prefix(
                raw_prefix,
                body_text,
                max_chunk_tokens=config.max_chunk_tokens,
            )
            if overlap_prefix_tokens < count_tokens(raw_prefix):
                warnings.append(
                    f"{group.atomic_id}: overlap prefix trimmed to fit token cap"
                )
            if overlap_prefix:
                overlap_source = prev_atomic.atomic_id

        final_text = _join_overlap(overlap_prefix, body_text)
        token_total = count_tokens(final_text)
        if token_total > config.max_chunk_tokens:
            warnings.append(
                f"{group.atomic_id}: token_count {token_total} exceeds "
                f"max {config.max_chunk_tokens}; dropping overlap"
            )
            overlap_prefix = ""
            overlap_prefix_tokens = 0
            overlap_source = ""
            final_text = body_text
            token_total = count_tokens(final_text)

        if group.atomic_kind in ("table", "code"):
            overlap_prefix = ""
            overlap_prefix_tokens = 0
            overlap_source = ""
            final_text = body_text
            token_total = group.token_count

        payload = group.model_dump()
        payload.update(
            {
                "overlapped_id": group.atomic_id,
                "body_text": body_text,
                "text": final_text,
                "token_count": token_total,
                "char_count": len(final_text),
                "overlap_prefix": overlap_prefix,
                "overlap_prefix_tokens": overlap_prefix_tokens,
                "overlap_source_atomic_id": overlap_source,
            }
        )
        item = OverlappedGroup.model_validate(payload)
        overlapped.append(item)

    return overlapped, warnings


def build_overlapped_corpus(
    atomic: AtomicGroupsCorpus,
    *,
    config: OverlapPass4Config | None = None,
    source_atomic_path: str = "",
) -> OverlappedGroupsCorpus:
    if config is None:
        config = OverlapPass4Config.from_env()

    groups, warnings = apply_overlap(atomic.groups, config=config)
    with_prefix = sum(1 for g in groups if g.overlap_prefix_tokens > 0)

    return OverlappedGroupsCorpus(
        doc_id=atomic.doc_id,
        total_pages=atomic.total_pages,
        source_atomic_groups=source_atomic_path,
        source_extracted_units=atomic.source_extracted_units,
        groups=groups,
        meta={
            "pass": "overlap_pass4",
            "atomic_group_count": len(atomic.groups),
            "overlapped_group_count": len(groups),
            "groups_with_prefix": with_prefix,
            "overlap_tokens": config.overlap_tokens,
            "max_chunk_tokens": config.max_chunk_tokens,
            "warnings": warnings,
        },
    )


def summarize_overlapped_groups(groups: List[OverlappedGroup]) -> dict:
    if not groups:
        return {"group_count": 0, "largest_group_tokens": 0}
    return {
        "group_count": len(groups),
        "total_tokens": sum(g.token_count for g in groups),
        "largest_group_tokens": max(g.token_count for g in groups),
        "groups_with_prefix": sum(1 for g in groups if g.overlap_prefix_tokens > 0),
        "prose": sum(1 for g in groups if g.atomic_kind == "prose"),
        "table": sum(1 for g in groups if g.atomic_kind == "table"),
        "code": sum(1 for g in groups if g.atomic_kind == "code"),
    }


def assert_pass4_shape(
    overlapped: List[OverlappedGroup],
    atomic: List[AtomicGroup],
    *,
    config: OverlapPass4Config,
) -> List[str]:
    errors: List[str] = []
    atomic_by_id = {g.atomic_id: g for g in atomic}

    if len(overlapped) != len(atomic):
        errors.append(
            f"count mismatch: atomic={len(atomic)} overlapped={len(overlapped)}"
        )

    seen: set[str] = set()
    overlapped_by_id: dict[str, OverlappedGroup] = {}
    for og in overlapped:
        if og.atomic_id in seen:
            errors.append(f"duplicate atomic_id in overlapped output: {og.atomic_id}")
        seen.add(og.atomic_id)
        overlapped_by_id[og.atomic_id] = og

        source = atomic_by_id.get(og.atomic_id)
        if source is None:
            errors.append(f"{og.atomic_id}: missing source atomic group")
            continue

        if og.body_text != source.text:
            errors.append(f"{og.atomic_id}: body_text != atomic text")

        if og.atomic_kind in ("table", "code"):
            if og.text != og.body_text:
                errors.append(f"{og.atomic_id}: table/code text modified")
            if og.overlap_prefix_tokens != 0:
                errors.append(f"{og.atomic_id}: table/code has overlap prefix")

        if og.token_count > config.max_chunk_tokens:
            errors.append(
                f"{og.atomic_id}: token_count {og.token_count} > {config.max_chunk_tokens}"
            )

        if og.overlap_prefix_tokens > config.overlap_tokens:
            errors.append(
                f"{og.atomic_id}: overlap_prefix_tokens > config.overlap_tokens"
            )

    for idx, og in enumerate(overlapped):
        if not og.overlap_prefix:
            continue
        if idx == 0:
            errors.append(f"{og.atomic_id}: prefix on first overlapped group")
            continue
        prev = overlapped[idx - 1]
        if prev.parent_group_id != og.parent_group_id:
            errors.append(f"{og.atomic_id}: prefix spans different parent_group_id")
        if og.overlap_source_atomic_id != prev.atomic_id:
            errors.append(
                f"{og.atomic_id}: overlap_source_atomic_id != previous atomic_id"
            )

    atomic_units: set[str] = set()
    overlapped_units: set[str] = set()
    for g in atomic:
        atomic_units.update(g.unit_ids)
    for g in overlapped:
        overlapped_units.update(g.unit_ids)
        if set(g.unit_ids) != set(atomic_by_id[g.atomic_id].unit_ids):
            errors.append(f"{g.atomic_id}: unit_ids changed from atomic source")

    if atomic_units != overlapped_units:
        errors.append("document unit coverage mismatch between atomic and overlapped")

    return errors
