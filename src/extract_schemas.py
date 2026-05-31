from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


class ElementType(str, Enum):
    HEADER = "HEADER"
    BARCODE = "BARCODE"
    TEXT = "TEXT"
    CHECKBOX = "CHECKBOX"
    TABLE = "TABLE"
    IMAGE = "IMAGE"
    SIGNATURE = "SIGNATURE"
    FOOTER = "FOOTER"


class DocumentElement(BaseModel):
    element_type: ElementType
    page_number: int
    content: str
    bounding_boxes: List[List[float]] = Field(
        description="Normalized boxes [x0, y0, x1, y1] in 0.0-1.0 page coordinates"
    )

    @field_validator("bounding_boxes")
    @classmethod
    def validate_boxes(cls, boxes: List[List[float]]) -> List[List[float]]:
        for box in boxes:
            if len(box) != 4:
                raise ValueError("Each bounding box must have exactly 4 floats")
            for v in box:
                if not 0.0 <= v <= 1.0:
                    raise ValueError("Bounding box coordinates must be in [0.0, 1.0]")
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError("Invalid box: x0 < x2 and y0 < y3 required")
        return boxes


class PageElementsResult(BaseModel):
    elements: List[DocumentElement] = Field(default_factory=list)


class StructuredDocument(BaseModel):
    document_id: str
    total_pages: int
    is_scanned_ocr: bool
    elements: List[DocumentElement] = Field(default_factory=list)
