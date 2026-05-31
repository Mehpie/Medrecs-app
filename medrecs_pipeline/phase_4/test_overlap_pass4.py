from __future__ import annotations

from typing import List

import pytest

from medrecs_pipeline.phase_4.build_chunks import build_chunks_corpus, overlapped_to_chunk
from medrecs_pipeline.phase_4.overlap_pass4 import (
    OverlapPass4Config,
    apply_overlap,
    assert_pass4_shape,
)
from medrecs_pipeline.phase_4.schemas import (
    AtomicGroup,
    AtomicGroupsCorpus,
    OverlappedGroupsCorpus,
)
from medrecs_pipeline.phase_4.token_utils import count_tokens, take_tail_tokens


def _atomic(
    atomic_id: str,
    *,
    parent: str,
    text: str,
    kind: str = "prose",
    contains_table: bool = False,
) -> AtomicGroup:
    return AtomicGroup(
        semantic_id=f"{parent}_sem_01",
        parent_group_id=parent,
        doc_id="doc_test",
        section_path=["Test"],
        page_start=1,
        page_end=1,
        unit_ids=[f"u_{atomic_id}"],
        text=text,
        unit_count=1,
        char_count=len(text),
        token_count=count_tokens(text),
        contains_table=contains_table,
        split_method="atomic_passthrough",
        atomic_id=atomic_id,
        source_semantic_id=f"{parent}_sem_01",
        atomic_kind=kind,
    )


def test_prose_prose_same_parent_gets_prefix() -> None:
    first = _atomic(
        "a1",
        parent="sg_1",
        text="First chunk has enough words. " * 20,
    )
    second = _atomic(
        "a2",
        parent="sg_1",
        text="Second chunk continues the clinical narrative.",
    )
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    overlapped, _ = apply_overlap([first, second], config=config)

    assert len(overlapped) == 2
    assert overlapped[0].overlap_prefix_tokens == 0
    assert overlapped[1].overlap_prefix_tokens > 0
    assert overlapped[1].overlap_prefix_tokens <= 64
    assert overlapped[1].body_text == second.text
    assert overlapped[1].overlap_source_atomic_id == "a1"


def test_prose_table_boundary_no_prefix() -> None:
    prose = _atomic("p1", parent="sg_1", text="Clinical narrative before table.")
    table = _atomic(
        "t1",
        parent="sg_1",
        text="| A | B |\n| :--- | :--- |\n| 1 | 2 |",
        kind="table",
        contains_table=True,
    )
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    overlapped, _ = apply_overlap([prose, table], config=config)

    assert overlapped[1].overlap_prefix_tokens == 0
    assert overlapped[1].text == table.text


def test_prose_code_boundary_no_prefix() -> None:
    prose = _atomic("p1", parent="sg_1", text="Assessment header")
    code = _atomic(
        "c1",
        parent="sg_1",
        text="1. Diagnosis one - M54.12\n2. Diagnosis two - M54.16\n3. Diagnosis three - M79.18",
        kind="code",
    )
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    overlapped, _ = apply_overlap([prose, code], config=config)

    assert overlapped[1].overlap_prefix_tokens == 0
    assert overlapped[1].text == code.text


def test_different_parent_no_overlap() -> None:
    first = _atomic("a1", parent="sg_1", text="Section one narrative. " * 30)
    second = _atomic("a2", parent="sg_2", text="Section two narrative.")
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    overlapped, _ = apply_overlap([first, second], config=config)

    assert overlapped[1].overlap_prefix_tokens == 0


def test_take_tail_tokens_respects_token_boundary() -> None:
    text = "alpha beta gamma delta epsilon"
    tail = take_tail_tokens(text, 2)
    assert count_tokens(tail) <= 2
    assert tail


def test_chunk_build_assigns_ulid_and_preserves_body() -> None:
    atomic = _atomic("a1", parent="sg_1", text="Sample chunk text.")
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    overlapped, _ = apply_overlap([atomic], config=config)
    chunk = overlapped_to_chunk(overlapped[0])

    assert chunk.chunk_id
    assert len(chunk.chunk_id) >= 20
    assert chunk.body_text == atomic.text
    assert chunk.units == atomic.unit_ids
    assert chunk.source_atomic_id == atomic.atomic_id


def test_assert_pass4_shape() -> None:
    first = _atomic("a1", parent="sg_1", text="First chunk. " * 40)
    second = _atomic("a2", parent="sg_1", text="Second chunk.")
    config = OverlapPass4Config(overlap_tokens=64, max_chunk_tokens=768)
    atomic = [first, second]
    overlapped, _ = apply_overlap(atomic, config=config)
    errors = assert_pass4_shape(overlapped, atomic, config=config)
    assert errors == []

    corpus = AtomicGroupsCorpus(doc_id="doc_test", total_pages=1, groups=atomic)
    overlapped_corpus = OverlappedGroupsCorpus(
        doc_id="doc_test",
        total_pages=1,
        groups=overlapped,
    )
    chunks = build_chunks_corpus(overlapped_corpus)
    assert len(chunks.groups) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
