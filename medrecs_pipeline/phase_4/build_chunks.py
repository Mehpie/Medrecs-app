from __future__ import annotations

from typing import List

from ulid import ULID

from .schemas import Chunk, ChunksCorpus, OverlappedGroup, OverlappedGroupsCorpus


def overlapped_to_chunk(group: OverlappedGroup) -> Chunk:
    return Chunk(
        chunk_id=str(ULID()),
        doc_id=group.doc_id,
        page_start=group.page_start,
        page_end=group.page_end,
        section_path=list(group.section_path),
        text=group.text,
        body_text=group.body_text,
        token_count=group.token_count,
        contains_table=group.contains_table,
        contains_handwriting=group.contains_handwriting,
        extraction_confidence_min=group.extraction_confidence_min,
        units=list(group.unit_ids),
        atomic_kind=group.atomic_kind,
        parent_group_id=group.parent_group_id,
        source_atomic_id=group.atomic_id,
        overlap_prefix_tokens=group.overlap_prefix_tokens,
    )


def build_chunks_corpus(
    overlapped: OverlappedGroupsCorpus,
    *,
    source_overlapped_path: str = "",
) -> ChunksCorpus:
    chunks: List[Chunk] = [overlapped_to_chunk(g) for g in overlapped.groups]
    with_prefix = sum(1 for c in chunks if c.overlap_prefix_tokens > 0)

    return ChunksCorpus(
        doc_id=overlapped.doc_id,
        total_pages=overlapped.total_pages,
        source_overlapped_groups=source_overlapped_path,
        source_extracted_units=overlapped.source_extracted_units,
        groups=chunks,
        meta={
            "pass": "chunks_assembly",
            "overlapped_group_count": len(overlapped.groups),
            "chunk_count": len(chunks),
            "groups_with_prefix": with_prefix,
            "overlap_tokens": overlapped.meta.get("overlap_tokens", 64),
            "max_chunk_tokens": overlapped.meta.get("max_chunk_tokens", 768),
        },
    )


def summarize_chunks(chunks: List[Chunk]) -> dict:
    if not chunks:
        return {"chunk_count": 0, "largest_chunk_tokens": 0}
    return {
        "chunk_count": len(chunks),
        "total_tokens": sum(c.token_count for c in chunks),
        "largest_chunk_tokens": max(c.token_count for c in chunks),
        "groups_with_prefix": sum(1 for c in chunks if c.overlap_prefix_tokens > 0),
        "prose": sum(1 for c in chunks if c.atomic_kind == "prose"),
        "table": sum(1 for c in chunks if c.atomic_kind == "table"),
        "code": sum(1 for c in chunks if c.atomic_kind == "code"),
    }
