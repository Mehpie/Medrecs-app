from __future__ import annotations

from typing import List

import pytest

from medrecs_pipeline.phase_4.schemas import ExtractedUnit, StructuralGroup
from medrecs_pipeline.phase_4.semantic_pass2 import (
    SemanticPass2Config,
    _SentenceChunk,
    _merge_small_chunks,
    assert_pass2_shape,
    find_split_points,
    semantic_pass2_split,
)
from medrecs_pipeline.phase_4.sentence_split import SentenceSpan, sentence_split


def _unit(unit_id: str, text: str, *, is_table: bool = False) -> ExtractedUnit:
    return ExtractedUnit(
        unit_id=unit_id,
        doc_id="doc_test",
        page_no=1,
        block_idx=0,
        bbox=(0.0, 0.0, 1.0, 1.0),
        text=text,
        is_table=is_table,
    )


def _parent(
    group_id: str,
    unit_ids: List[str],
    text: str,
    *,
    section_path: List[str] | None = None,
) -> StructuralGroup:
    return StructuralGroup(
        group_id=group_id,
        doc_id="doc_test",
        section_path=section_path or ["Progress Note", "HPI"],
        page_start=1,
        page_end=1,
        unit_ids=unit_ids,
        text=text,
        unit_count=len(unit_ids),
        char_count=len(text),
    )


def _mock_embed(texts: List[str]) -> List[List[float]]:
    """Deterministic pseudo-embeddings: topic shift at long repeated blocks."""
    vectors: List[List[float]] = []
    for text in texts:
        lowered = text.lower()
        if "topic b" in lowered or "second topic" in lowered:
            vectors.append([0.0, 1.0, 0.0])
        elif "topic c" in lowered or "third topic" in lowered:
            vectors.append([0.0, 0.0, 1.0])
        else:
            vectors.append([1.0, 0.0, 0.0])
    return vectors


def test_single_unit_split_retains_unit_ids_on_all_children() -> None:
    """When one unit's text is split across chunks, every child keeps that unit_id."""
    body = (
        "Topic A sentence one with enough words here. "
        "Topic A sentence two with enough words here. "
        "Topic A sentence three with enough words here. "
        "Topic B sentence one with enough words here. "
        "Topic B sentence two with enough words here. "
        "Topic B sentence three with enough words here. "
        "Topic C sentence one with enough words here. "
        "Topic C sentence two with enough words here. "
        "Topic C sentence three with enough words here."
    )
    header_id = "doc_test:p1:b1"
    body_id = "doc_test:p1:b2"
    units_map = {
        header_id: _unit(header_id, "History of Present Illness"),
        body_id: _unit(body_id, body),
    }
    combined = f"History of Present Illness\n\n{body}"
    parent = _parent("sg_test", [header_id, body_id], combined)

    config = SemanticPass2Config(
        tau_b=0.35,
        min_sentences=2,
        target_chunk_tokens=40,
        max_chunk_tokens=200,
        min_chunk_tokens=10,
    )
    groups, _ = semantic_pass2_split(
        parent, units_map, embed_fn=_mock_embed, config=config
    )

    assert len(groups) > 1
    body_chunks = [g for g in groups if body_id in g.unit_ids]
    assert len(body_chunks) > 1
    for group in body_chunks:
        assert body_id in group.unit_ids

    errors = assert_pass2_shape(groups, [parent])
    assert errors == []


def test_header_body_merge_avoids_tiny_first_chunk() -> None:
    header = "History of Present Illness"
    body = (
        "Patient reports ongoing neck pain for several weeks. "
        "Pain worsens with movement and improves with rest. "
        "No fever or chills reported today. "
        "Topic B second topic begins here with more detail. "
        "Topic B continues with additional clinical context. "
        "Topic B ends with follow-up instructions."
    )
    header_id = "doc_test:p1:b1"
    body_id = "doc_test:p1:b2"
    units_map = {
        header_id: _unit(header_id, header),
        body_id: _unit(body_id, body),
    }
    combined = f"{header}\n\n{body}"
    parent = _parent("sg_hpi", [header_id, body_id], combined)

    config = SemanticPass2Config(
        tau_b=0.35,
        min_sentences=2,
        target_chunk_tokens=40,
        max_chunk_tokens=200,
        min_chunk_tokens=64,
    )
    groups, _ = semantic_pass2_split(
        parent, units_map, embed_fn=_mock_embed, config=config
    )

    assert groups
    assert all(g.token_count >= config.min_chunk_tokens or len(groups) == 1 for g in groups)
    assert all(g.unit_ids for g in groups if g.text.strip())
    errors = assert_pass2_shape(groups, [parent])
    assert errors == []


def test_find_split_points_peak_detection() -> None:
    scores = [0.1, 0.5, 0.2, 0.6, 0.15]
    cuts = find_split_points(scores, tau_b=0.35, min_distance=1)
    assert cuts == [1, 3]


def test_merge_small_chunks_forward_and_backward() -> None:
    tiny = _SentenceChunk(
        sentences=[SentenceSpan(text="Short.", unit_ids=("u1",), atomic=False)]
    )
    medium = _SentenceChunk(
        sentences=[
            SentenceSpan(
                text="This is a longer chunk with enough tokens to exceed the minimum.",
                unit_ids=("u2",),
                atomic=False,
            )
        ]
    )
    tail = _SentenceChunk(
        sentences=[SentenceSpan(text="Tail.", unit_ids=("u3",), atomic=False)]
    )

    merged = _merge_small_chunks([tiny, medium, tail], min_tokens=20)
    assert len(merged) == 1
    assert "Short." in merged[0].text()
    assert "Tail." in merged[0].text()


def test_sentence_split_numbered_list_marker() -> None:
    text = "At C4-5, there is disc bulge. 5. At C5-6, there is another finding."
    sentences = sentence_split(text)
    assert len(sentences) == 2
    assert "5." not in sentences[0]
    assert sentences[1].startswith("5.")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
