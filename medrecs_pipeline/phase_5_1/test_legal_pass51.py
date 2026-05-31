from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from medrecs_pipeline.phase_5.schemas import LlmTag, Tag, TaggedChunk, TaggedChunksCorpus
from medrecs_pipeline.phase_5.span_utils import llm_tags_to_tags
from medrecs_pipeline.phase_5.thresholds import ThresholdConfig

from medrecs_pipeline.phase_5_1.legal_pass51 import (
    Pass51Config,
    assert_pass51_shape,
    augment_corpus,
)
from medrecs_pipeline.phase_5_1.legal_router import LegalRouterConfig, should_route_legal
from medrecs_pipeline.phase_5_1.legal_rule_tagger import tag_legal_phrases
from medrecs_pipeline.phase_5_1.load_tagged_chunks import load_tagged_chunks
from medrecs_pipeline.phase_5_1.merge_legal import dedupe_legal_tags, merge_legal_into_chunk
from medrecs_pipeline.phase_5_1.schemas import GeminiLegalExtraction


def _tagged_chunk(**kwargs) -> TaggedChunk:
    defaults = {
        "chunk_id": "test_chunk",
        "doc_id": "doc_test",
        "page_start": 1,
        "page_end": 1,
        "section_path": ["HPI"],
        "text": "body",
        "body_text": "body",
        "token_count": 50,
        "atomic_kind": "prose",
        "clinical_tags": [],
        "legal_tags": [],
        "uncertain_tags": [],
        "tagging_method": "gemini",
    }
    defaults.update(kwargs)
    return TaggedChunk(**defaults)


def test_router_hpi_rear_ended_routed() -> None:
    chunk = _tagged_chunk(
        chunk_id="01KSWH41RY4C03QGH138GT92WG",
        body_text="Patient was rear-ended by a semi-truck on 12/4/23.",
        text="Patient was rear-ended by a semi-truck on 12/4/23.",
        section_path=["History of Present Illness"],
    )
    cfg = LegalRouterConfig()
    assert should_route_legal(chunk, cfg) is True


def test_router_nav_skipped_not_routed() -> None:
    nav = "| Patient Medical Record | Page(s) |\n| Total Pages | 40 |"
    chunk = _tagged_chunk(
        atomic_kind="table",
        body_text=nav,
        text=nav,
        tagging_method="skipped",
        token_count=20,
    )
    cfg = LegalRouterConfig()
    assert should_route_legal(chunk, cfg) is False


def test_pi_rules_semi_truck_and_out_of_work() -> None:
    body = "Rear-ended by semi-truck. Patient remains out of work."
    tags = tag_legal_phrases(body)
    classes = {t.tag_class for t in tags}
    assert "INJURY_EVENT" in classes
    assert "ECONOMIC_LOSS" in classes
    assert "FUNCTIONAL_LIMITATION" in classes
    for tag in tags:
        assert body[tag.start : tag.end] == tag.surface


def test_merge_dedupes_same_span_keeps_max_confidence() -> None:
    a = Tag(
        tag_class="INJURY_EVENT",
        surface="MVC",
        start=0,
        end=3,
        confidence=0.7,
    )
    b = Tag(
        tag_class="INJURY_EVENT",
        surface="MVC",
        start=0,
        end=3,
        confidence=0.92,
    )
    out = dedupe_legal_tags([a, b])
    assert len(out) == 1
    assert out[0].confidence == 0.92


def test_merge_preserves_existing_and_clinical() -> None:
    body = "MVC caused neck pain."
    existing_legal = [
        Tag(
            tag_class="CAUSATION_CLAIM",
            surface="caused",
            start=4,
            end=10,
            confidence=0.85,
        )
    ]
    clinical = [
        Tag(tag_class="SYMPTOM", surface="neck pain", start=11, end=20, confidence=0.9)
    ]
    chunk = _tagged_chunk(
        body_text=body,
        text=body,
        clinical_tags=clinical,
        legal_tags=existing_legal,
    )
    rule_tags = tag_legal_phrases(body)
    cfg = ThresholdConfig(tau_clinical=0.7, tau_legal=0.6, tau_uncertain_low=0.4)
    updated, added, _ = merge_legal_into_chunk(
        chunk,
        rule_tags=rule_tags,
        gemini_tags=[],
        config=cfg,
    )
    assert [t.model_dump() for t in chunk.clinical_tags] == [
        t.model_dump() for t in updated.clinical_tags
    ]
    classes = {t.tag_class for t in updated.legal_tags}
    assert "CAUSATION_CLAIM" in classes
    assert "INJURY_EVENT" in classes
    assert updated.tagging_method == "gemini+legal51"
    assert added >= 1


def test_mock_gemini_legal_merged() -> None:
    body = "Following the MVC patient has difficulty walking."
    llm_tags = [
        LlmTag(
            tag_class="CAUSATION_CLAIM",
            surface="Following the MVC",
            start=0,
            end=18,
            confidence=0.88,
        )
    ]
    gemini_tags, _ = llm_tags_to_tags(llm_tags, body)
    chunk = _tagged_chunk(body_text=body, text=body)
    cfg = ThresholdConfig()
    updated, _, _ = merge_legal_into_chunk(
        chunk,
        rule_tags=[],
        gemini_tags=gemini_tags,
        config=cfg,
    )
    assert any(t.tag_class == "CAUSATION_CLAIM" for t in updated.legal_tags)


def test_augment_corpus_mock_gemini_no_api() -> None:
    body = "Patient was rear-ended by semi-truck and remains out of work."
    chunk = _tagged_chunk(
        chunk_id="c1",
        body_text=body,
        text=body,
        clinical_tags=[
            Tag(tag_class="SYMPTOM", surface="pain", start=0, end=4, confidence=0.9)
        ],
    )
    corpus = TaggedChunksCorpus(
        doc_id="doc_test",
        total_pages=1,
        groups=[chunk],
    )

    def fake_extract(c: TaggedChunk):
        extraction = GeminiLegalExtraction(
            legal_tags=[
                LlmTag(
                    tag_class="INJURY_EVENT",
                    surface="rear-ended",
                    start=12,
                    end=23,
                    confidence=0.9,
                )
            ]
        )
        return extraction, {"parse_mode": "structured", "prompt_tokens": 10}

    cfg = Pass51Config(concurrency=1, enable_rules=True, retry_failed=False)
    with patch(
        "medrecs_pipeline.phase_5_1.legal_pass51.extract_legal_with_gemini",
        side_effect=fake_extract,
    ):
        out, stats = augment_corpus(corpus, config=cfg, source_tagged_path="/tmp/in.json")

    assert stats.chunks_routed == 1
    assert len(out.groups[0].legal_tags) >= 2  # rules + gemini
    assert len(out.groups[0].clinical_tags) == 1
    assert out.meta["legal_pass"] == "phase_5_1"
    errors = assert_pass51_shape(corpus, out)
    assert errors == []


def test_roundtrip_load_write_fixture() -> None:
    chunk = _tagged_chunk(
        chunk_id="c1",
        body_text="MVC on highway.",
        text="MVC on highway.",
        legal_tags=[
            Tag(
                tag_class="INJURY_EVENT",
                surface="MVC",
                start=0,
                end=3,
                confidence=0.8,
            )
        ],
    )
    corpus = TaggedChunksCorpus(
        doc_id="doc_fixture",
        total_pages=1,
        groups=[chunk],
        meta={"phase": 5},
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc_fixture_tagged_chunks.json"
        path.write_text(json.dumps(corpus.model_dump(mode="json")), encoding="utf-8")
        loaded = load_tagged_chunks(path)
        assert loaded.doc_id == "doc_fixture"
        assert loaded.groups[0].legal_tags[0].tag_class == "INJURY_EVENT"
