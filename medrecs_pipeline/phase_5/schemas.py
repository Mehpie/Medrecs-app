from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from medrecs_pipeline.phase_4.schemas import Chunk


class Tag(BaseModel):
    """Named entity tag with character span in body_text."""

    tag_class: str
    surface: str
    start: int
    end: int
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start", 0)
        if v <= start:
            raise ValueError("end must be greater than start")
        return v


class LlmTag(BaseModel):
    """Lenient tag shape from Gemini before span normalization."""

    tag_class: str
    surface: str
    start: int | None = None
    end: int | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class GeminiTagExtraction(BaseModel):
    """Raw LLM output before threshold bucketing."""

    clinical_tags: List[LlmTag] = Field(default_factory=list)
    legal_tags: List[LlmTag] = Field(default_factory=list)


class TaggedChunk(Chunk):
    """Phase-4 chunk annotated with dual-domain entity tags."""

    clinical_tags: List[Tag] = Field(default_factory=list)
    legal_tags: List[Tag] = Field(default_factory=list)
    uncertain_tags: List[Tag] = Field(default_factory=list)
    tagging_method: str = "gemini"  # rules | gemini | skipped


class TaggedChunksCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_chunks: str = ""
    groups: List[TaggedChunk] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
