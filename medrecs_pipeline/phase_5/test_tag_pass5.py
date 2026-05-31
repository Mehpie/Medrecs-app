from __future__ import annotations

from unittest.mock import patch

import pytest

from medrecs_pipeline.phase_4.schemas import Chunk
from medrecs_pipeline.phase_5.rule_tagger import tag_code_chunk
from medrecs_pipeline.phase_5.schemas import GeminiTagExtraction, LlmTag, Tag, TaggedChunk
from medrecs_pipeline.phase_5.span_utils import (
    llm_tags_to_tags,
    validate_and_repair_tag,
    validate_and_repair_tags,
)
from medrecs_pipeline.phase_5.tag_pass5 import (
    Pass5Config,
    is_nav_toc_table,
    route_tagging_method,
    tag_one_chunk,
)
from medrecs_pipeline.phase_5.thresholds import ThresholdConfig, apply_thresholds


_ICD_SAMPLE = """1. Sprain of joints and ligaments of other parts of neck, initial encounter - S13.8XXA (Primary)
2. Bilateral occipital neuralgia - M54.81
3. Concussion with loss of consciousness of 30 minutes or less, initial encounter - S06.0X1A
4. Lumbar radiculitis - M54.16
5. Sprain of other parts of lumbar spine and pelvis, initial encounter - S33.8XXA
6. Strain of lumbar region, initial encounter - S39.012A"""


def _chunk(**kwargs) -> Chunk:
    defaults = {
        "chunk_id": "test_chunk",
        "doc_id": "doc_test",
        "page_start": 1,
        "page_end": 1,
        "section_path": ["Assessment"],
        "text": "body",
        "body_text": "body",
        "token_count": 10,
        "atomic_kind": "prose",
    }
    defaults.update(kwargs)
    return Chunk(**defaults)


def test_rule_tagger_icd_diagnosis_spans() -> None:
    tags = tag_code_chunk(_ICD_SAMPLE)
    assert len(tags) >= 6
    assert all(t.tag_class == "DIAGNOSIS" for t in tags)
    for tag in tags:
        assert _ICD_SAMPLE[tag.start : tag.end] == tag.surface


def test_thresholds_clinical_and_legal_boundaries() -> None:
    cfg = ThresholdConfig(tau_clinical=0.7, tau_legal=0.6, tau_uncertain_low=0.4)
    clinical = [
        Tag(tag_class="SYMPTOM", surface="pain", start=0, end=4, confidence=0.75),
        Tag(tag_class="SYMPTOM", surface="ache", start=5, end=9, confidence=0.5),
        Tag(tag_class="SYMPTOM", surface="hurt", start=10, end=14, confidence=0.39),
    ]
    legal = [
        Tag(
            tag_class="INJURY_EVENT",
            surface="MVC",
            start=0,
            end=3,
            confidence=0.65,
        ),
        Tag(
            tag_class="INJURY_EVENT",
            surface="fall",
            start=4,
            end=8,
            confidence=0.55,
        ),
    ]
    c_out, l_out, u_out, dropped = apply_thresholds(clinical, legal, config=cfg)
    assert len(c_out) == 1 and c_out[0].surface == "pain"
    assert len(l_out) == 1 and l_out[0].surface == "MVC"
    assert len(u_out) == 2
    assert {t.surface for t in u_out} == {"ache", "fall"}
    assert dropped == 0


def test_span_repair_finds_surface_elsewhere() -> None:
    body = "Patient reports neck pain and dizziness."
    tag = Tag(tag_class="SYMPTOM", surface="neck pain", start=0, end=4, confidence=0.9)
    fixed, status = validate_and_repair_tag(tag, body)
    assert status == "repaired"
    assert fixed is not None
    assert body[fixed.start : fixed.end] == "neck pain"


def test_span_validate_drops_missing_surface() -> None:
    body = "No matching text."
    tag = Tag(tag_class="SYMPTOM", surface="phantom", start=0, end=7, confidence=0.9)
    repaired, stats = validate_and_repair_tags([tag], body)
    assert repaired == []
    assert stats.dropped == 1


def test_route_code_chunk_to_rules() -> None:
    chunk = _chunk(atomic_kind="code", body_text=_ICD_SAMPLE, text=_ICD_SAMPLE)
    assert route_tagging_method(chunk) == "rules"


def test_route_nav_table_skipped() -> None:
    nav = "| Patient Medical Record | Page(s) |\n| Total Pages | 40 |"
    assert is_nav_toc_table(nav) is True
    chunk = _chunk(atomic_kind="table", body_text=nav, text=nav)
    assert route_tagging_method(chunk) == "skipped"


def test_tag_one_chunk_rules_no_api() -> None:
    chunk = _chunk(
        atomic_kind="code",
        body_text=_ICD_SAMPLE,
        text=_ICD_SAMPLE,
        token_count=100,
    )
    tagged, stats = tag_one_chunk(chunk, Pass5Config())
    assert tagged.tagging_method == "rules"
    assert len(tagged.clinical_tags) >= 6
    assert stats.gemini_calls == 0


def test_llm_tags_to_tags_missing_offsets() -> None:
    body = "MVC on 12/4/23. Neck pain limits daily activities."
    tags, stats = llm_tags_to_tags(
        [
            LlmTag(tag_class="INJURY_EVENT", surface="MVC", confidence=0.9),
            LlmTag(tag_class="SYMPTOM", surface="Neck pain", confidence=0.85),
        ],
        body,
    )
    assert len(tags) == 2
    assert body[tags[0].start : tags[0].end] == "MVC"
    assert stats.llm_rows_dropped == 0


def test_tag_one_chunk_gemini_mock() -> None:
    chunk = _chunk(
        body_text="MVC on 12/4/23. Neck pain limits daily activities.",
        text="MVC on 12/4/23. Neck pain limits daily activities.",
    )
    mock_result = GeminiTagExtraction(
        clinical_tags=[
            LlmTag(tag_class="SYMPTOM", surface="Neck pain", start=16, end=25, confidence=0.85),
            LlmTag(
                tag_class="TEMPORAL_MARKER",
                surface="12/4/23",
                start=7,
                end=14,
                confidence=0.9,
            ),
        ],
        legal_tags=[
            LlmTag(
                tag_class="INJURY_EVENT",
                surface="MVC",
                start=0,
                end=3,
                confidence=0.88,
            ),
            LlmTag(
                tag_class="FUNCTIONAL_LIMITATION",
                surface="limits daily activities",
                start=26,
                end=49,
                confidence=0.75,
            ),
        ],
    )

    with patch(
        "medrecs_pipeline.phase_5.tag_pass5.extract_tags_with_gemini",
        return_value=(mock_result, {"prompt_tokens": 100, "candidates_tokens": 50}),
    ):
        tagged, stats = tag_one_chunk(chunk, Pass5Config())

    assert tagged.tagging_method == "gemini"
    assert len(tagged.clinical_tags) == 2
    assert len(tagged.legal_tags) == 2
    assert stats.gemini_calls == 1


def test_tagged_chunk_roundtrip_serialization() -> None:
    chunk = TaggedChunk(
        chunk_id="01TEST",
        doc_id="doc_test",
        page_start=1,
        page_end=1,
        section_path=["HPI"],
        text="MVC",
        body_text="MVC",
        token_count=1,
        clinical_tags=[
            Tag(tag_class="TEMPORAL_MARKER", surface="MVC", start=0, end=3, confidence=0.8)
        ],
        legal_tags=[
            Tag(tag_class="INJURY_EVENT", surface="MVC", start=0, end=3, confidence=0.85)
        ],
        tagging_method="gemini",
    )
    data = chunk.model_dump(mode="json")
    restored = TaggedChunk.model_validate(data)
    assert restored.chunk_id == chunk.chunk_id
    assert len(restored.clinical_tags) == 1
    assert len(restored.legal_tags) == 1
