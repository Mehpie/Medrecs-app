from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class ElementType(str, Enum):
    HEADER = "HEADER"
    BANNER = "BANNER"
    BARCODE = "BARCODE"
    TEXT = "TEXT"
    CHECKBOX = "CHECKBOX"
    TABLE = "TABLE"
    IMAGE = "IMAGE"
    SIGNATURE = "SIGNATURE"
    FOOTER = "FOOTER"


class DocumentElement(BaseModel):
    """
    Vision/layout element emitted per page by the Phase-2 vision extractor.

    Coordinates are normalized to [0.0, 1.0] with top-left origin.
    """

    element_type: ElementType
    page_number: int
    content: str
    bounding_boxes: List[List[float]] = Field(
        default_factory=list,
        description="Normalized boxes [x0, y0, x1, y1] in 0.0-1.0 page coordinates",
    )

    @field_validator("element_type", mode="before")
    @classmethod
    def coerce_element_type(cls, v: Any) -> Any:
        if isinstance(v, ElementType):
            return v
        s = str(v or "").strip().upper().replace(" ", "_").replace("-", "_")
        if s in ElementType.__members__:
            return s
        # Default to TEXT to avoid hard failures on minor model formatting drift.
        return ElementType.TEXT.value

    @field_validator("bounding_boxes", mode="before")
    @classmethod
    def normalize_boxes(cls, boxes: Any) -> List[List[float]]:
        if not boxes:
            return []

        out: List[List[float]] = []
        for box in boxes:
            if not isinstance(box, (list, tuple)):
                continue
            if len(box) < 4:
                continue

            # Clamp to valid range; keep only first 4 coords.
            x0, y0, x1, y1 = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
            x0 = max(0.0, min(1.0, x0))
            y0 = max(0.0, min(1.0, y0))
            x1 = max(0.0, min(1.0, x1))
            y1 = max(0.0, min(1.0, y1))

            # Ensure a valid non-empty rectangle.
            if x0 >= x1:
                x1 = min(1.0, x0 + 0.01)
            if y0 >= y1:
                y1 = min(1.0, y0 + 0.01)

            out.append([x0, y0, x1, y1])

        return out


class PageElementsResult(BaseModel):
    elements: List[DocumentElement] = Field(default_factory=list)


class StructuredDocument(BaseModel):
    document_id: str
    total_pages: int
    is_scanned_ocr: bool
    elements: List[DocumentElement] = Field(default_factory=list)


class ExtractedUnit(BaseModel):
    """
    Stage-2 unit normalized for downstream Stage-4 chunking input.

    Note: PHI redaction is deferred to Stage 3 in SYSTEM_DESIGN; Phase-2 units may
    still contain identifiable content for trusted/dev use only.
    """

    unit_id: str
    doc_id: str
    page_no: int
    block_idx: int
    bbox: Tuple[float, float, float, float]
    text: str

    # These fields exist in SYSTEM_DESIGN’s Stage-2 contract; Phase-2 vision output
    # does not provide them, so we use safe defaults.
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
    def validate_and_coerce_bbox(cls, v: Any) -> Tuple[float, float, float, float]:
        if isinstance(v, tuple) and len(v) == 4:
            xs = [float(x) for x in v]
        elif isinstance(v, list) and len(v) == 4:
            xs = [float(x) for x in v]
        else:
            xs = [0.0, 0.0, 1.0, 1.0]

        x0, y0, x1, y1 = xs
        x0 = max(0.0, min(1.0, x0))
        y0 = max(0.0, min(1.0, y0))
        x1 = max(0.0, min(1.0, x1))
        y1 = max(0.0, min(1.0, y1))

        if x0 >= x1:
            x1 = min(1.0, x0 + 0.01)
        if y0 >= y1:
            y1 = min(1.0, y0 + 0.01)
        return (x0, y0, x1, y1)


class ExtractedUnitsCorpus(BaseModel):
    doc_id: str
    total_pages: int
    is_scanned_ocr: bool
    model_name: str
    units: List[ExtractedUnit] = Field(default_factory=list)

    # Extra metadata so downstream stages can be deterministic/reproducible later.
    meta: Dict[str, Any] = Field(default_factory=dict)

