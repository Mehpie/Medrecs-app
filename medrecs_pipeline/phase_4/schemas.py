from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class ExtractedUnit(BaseModel):
    """Stage-2 unit (loaded from Phase-2 output JSON)."""

    unit_id: str
    doc_id: str
    page_no: int
    block_idx: int
    bbox: Tuple[float, float, float, float]
    text: str

    font_size: Optional[float] = None
    is_bold: bool = False
    is_table: bool = False
    is_handwritten: bool = False

    section_path: List[str] = Field(default_factory=lambda: ["UNSPECIFIED"])
    confidence: float = 1.0

    extractor: str = "gemini_vision"
    extractor_version: str = ""

    @field_validator("bbox", mode="before")
    @classmethod
    def validate_bbox(cls, v: Any) -> Tuple[float, float, float, float]:
        if isinstance(v, tuple) and len(v) == 4:
            xs = [float(x) for x in v]
        elif isinstance(v, list) and len(v) == 4:
            xs = [float(x) for x in v]
        else:
            xs = [0.0, 0.0, 1.0, 1.0]
        x0, y0, x1, y1 = xs
        if x0 >= x1:
            x1 = min(1.0, x0 + 0.01)
        if y0 >= y1:
            y1 = min(1.0, y0 + 0.01)
        return (x0, y0, x1, y1)


class ExtractedUnitsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    is_scanned_ocr: bool = False
    model_name: str = ""
    units: List[ExtractedUnit] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class StructuralGroup(BaseModel):
    """
    Pass-1 output: consecutive units sharing the same section_path within one document.
    """

    group_id: str
    doc_id: str
    section_path: List[str]
    page_start: int
    page_end: int
    unit_ids: List[str] = Field(default_factory=list)
    text: str
    unit_count: int
    char_count: int
    contains_table: bool = False
    contains_handwriting: bool = False
    extraction_confidence_min: float = 1.0


class StructuralGroupsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_extracted_units: str = ""
    groups: List[StructuralGroup] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class SemanticGroup(BaseModel):
    """
    Pass-2 output: semantic sub-chunk of a Pass-1 structural group.
    """

    semantic_id: str
    parent_group_id: str
    doc_id: str
    section_path: List[str]
    page_start: int
    page_end: int
    unit_ids: List[str] = Field(default_factory=list)
    text: str
    unit_count: int
    char_count: int
    token_count: int
    contains_table: bool = False
    contains_handwriting: bool = False
    extraction_confidence_min: float = 1.0
    split_method: str = "passthrough"


class SemanticGroupsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_structural_groups: str = ""
    source_extracted_units: str = ""
    groups: List[SemanticGroup] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class AtomicGroup(SemanticGroup):
    """
    Pass-3 output: atomic prose, table, or code chunk derived from a Pass-2 semantic group.
    """

    atomic_id: str
    source_semantic_id: str
    atomic_kind: str = "prose"  # prose | table | code


class AtomicGroupsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_semantic_groups: str = ""
    source_extracted_units: str = ""
    groups: List[AtomicGroup] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class OverlappedGroup(AtomicGroup):
    """
    Pass-4 output: atomic group with optional prefix overlap from previous prose sibling.
    """

    overlapped_id: str
    body_text: str
    overlap_prefix: str = ""
    overlap_prefix_tokens: int = 0
    overlap_source_atomic_id: str = ""


class OverlappedGroupsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_atomic_groups: str = ""
    source_extracted_units: str = ""
    groups: List[OverlappedGroup] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """
    Final Stage-4 chunk suitable for embedding and LLM consumption (SYSTEM_DESIGN §3.4).
    """

    chunk_id: str
    doc_id: str
    page_start: int
    page_end: int
    section_path: List[str]
    text: str
    body_text: str
    token_count: int
    contains_table: bool = False
    contains_handwriting: bool = False
    extraction_confidence_min: float = 1.0
    units: List[str] = Field(default_factory=list)
    atomic_kind: str = "prose"
    parent_group_id: str = ""
    source_atomic_id: str = ""
    overlap_prefix_tokens: int = 0


class ChunksCorpus(BaseModel):
    doc_id: str
    total_pages: int
    source_overlapped_groups: str = ""
    source_extracted_units: str = ""
    groups: List[Chunk] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
