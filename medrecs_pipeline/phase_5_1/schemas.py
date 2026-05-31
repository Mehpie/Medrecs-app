from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from medrecs_pipeline.phase_5.schemas import LlmTag


class GeminiLegalExtraction(BaseModel):
    """Legal-only LLM output for Phase 5.1."""

    legal_tags: List[LlmTag] = Field(default_factory=list)
