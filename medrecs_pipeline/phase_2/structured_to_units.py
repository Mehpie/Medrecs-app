from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

from .schemas import ExtractedUnitsCorpus, ExtractedUnit, ElementType, StructuredDocument

# Safety net when the model still labels page chrome as HEADER.
_PAGE_CHROME_PATTERNS = (
    re.compile(r"DOB\s*:", re.IGNORECASE),
    re.compile(r"Acc\s*No", re.IGNORECASE),
    re.compile(r"\bDOS\s*:", re.IGNORECASE),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*(AM|PM)?$", re.IGNORECASE),
)

__all__ = [
    "structured_document_to_extracted_units",
    "assert_stage2_shape",
    "load_and_validate_extracted_units_json",
]


def _split_header_to_section_path(header_text: str, *, top_k: int = 2) -> List[str]:
    """
    Convert header text into a small section-path list.

    Design intent: consecutive content under a HEADER belongs to that section.
    """

    # Normalize and split into candidate segments.
    lines = [ln.strip() for ln in header_text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Remove trailing colon which appears frequently in medical record headings.
    cleaned: List[str] = []
    for ln in lines:
        while ln.endswith(":"):
            ln = ln[:-1].strip()
        if ln:
            cleaned.append(ln)

    # Limit depth to keep chunker manageable and deterministic.
    if not cleaned:
        return ["UNSPECIFIED"]
    return cleaned[:top_k]


def _looks_like_page_chrome(header_text: str) -> bool:
    """True if HEADER content matches common EMR page-banner patterns."""
    text = header_text.strip()
    if not text:
        return False
    dob = _PAGE_CHROME_PATTERNS[0].search(text) is not None
    acc = _PAGE_CHROME_PATTERNS[1].search(text) is not None
    if dob and acc:
        return True
    if _PAGE_CHROME_PATTERNS[2].search(text) and acc:
        return True
    if _PAGE_CHROME_PATTERNS[3].match(text):
        return True
    return False


def structured_document_to_extracted_units(
    structured: StructuredDocument,
    *,
    model_name: str = "",
    header_top_k: int = 2,
) -> Tuple[List[ExtractedUnit], List[str]]:
    """
    Convert Phase-2 vision layout elements into Stage-2-style ExtractedUnit rows
    required by Stage-4 chunking (structural sectionization + reading order).

    Returns: (units, warnings)
    """

    warnings: List[str] = []

    # Ensure stable traversal: process in reading order as emitted.
    # We compute block_idx as the index within the filtered page elements.
    all_units: List[ExtractedUnit] = []

    # Build a mapping page_no -> elements in emitted order.
    # (Assumption: vision extractor emits page-ordered elements.)
    page_numbers = list(range(1, structured.total_pages + 1))
    current_section_path: List[str] = ["UNSPECIFIED"]

    for page_no in page_numbers:
        elements = [el for el in structured.elements if el.page_number == page_no]
        if not elements:
            warnings.append(f"page_no={page_no} has no elements; emitting none")
            continue

        for block_idx, el in enumerate(elements):
            if el.element_type == ElementType.HEADER and not _looks_like_page_chrome(
                el.content
            ):
                current_section_path = _split_header_to_section_path(
                    el.content, top_k=header_top_k
                )
            elif el.element_type == ElementType.HEADER and _looks_like_page_chrome(
                el.content
            ):
                warnings.append(
                    f"page_no={page_no} block_idx={block_idx}: HEADER looks like page "
                    f"chrome; section_path unchanged"
                )

            # Stage-4 pass 3: atomic tables.
            is_table = el.element_type == ElementType.TABLE

            # Stage-4 can function without accurate bboxes, but we still provide one.
            if el.bounding_boxes:
                x0, y0, x1, y1 = el.bounding_boxes[0]
                bbox = (x0, y0, x1, y1)
            else:
                # Placeholder covering the page; validators in schemas allow it.
                bbox = (0.0, 0.0, 1.0, 1.0)

            unit_id = f"{structured.document_id}:p{page_no}:b{block_idx}"

            all_units.append(
                ExtractedUnit(
                    unit_id=unit_id,
                    doc_id=structured.document_id,
                    page_no=page_no,
                    block_idx=block_idx,
                    bbox=bbox,
                    text=el.content or "",
                    font_size=None,
                    is_bold=False,
                    is_table=is_table,
                    is_handwritten=False,
                    section_path=list(current_section_path),
                    confidence=1.0,
                    extractor="gemini_vision",
                    extractor_version=model_name,
                )
            )

    return all_units, warnings


def assert_stage2_shape(units: List[ExtractedUnit]) -> List[str]:
    """
    Lightweight structural checks for pipeline hygiene.
    """

    errors: List[str] = []
    if not units:
        errors.append("no units generated")
        return errors

    # For each page, block_idx must start at 0 and be consecutive.
    by_page: dict[int, List[ExtractedUnit]] = {}
    for u in units:
        by_page.setdefault(u.page_no, []).append(u)

    for page_no, page_units in by_page.items():
        page_units_sorted = sorted(page_units, key=lambda x: x.block_idx)
        if page_units_sorted[0].block_idx != 0:
            errors.append(f"page_no={page_no} first block_idx != 0")

        expected = list(range(len(page_units_sorted)))
        actual = [u.block_idx for u in page_units_sorted]
        if actual != expected:
            errors.append(
                f"page_no={page_no} block_idx mismatch: expected={expected[:5]}..., got={actual[:5]}..."
            )

        # Every unit must have a non-empty section_path.
        for u in page_units_sorted:
            if not u.section_path or not all(seg for seg in u.section_path):
                errors.append(f"page_no={page_no} unit_id={u.unit_id} has invalid section_path")

    return errors


def load_and_validate_extracted_units_json(path: Path) -> ExtractedUnitsCorpus:
    """
    Importable validator for post-write checks.

    - Parses the JSON into ExtractedUnitsCorpus (schema validation)
    - Runs assert_stage2_shape for ordering/section_path hygiene
    - Raises RuntimeError on failure; returns corpus on success
    """
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    corpus = ExtractedUnitsCorpus.model_validate(raw)
    errors = assert_stage2_shape(corpus.units)
    if errors:
        raise RuntimeError(
            "extracted_units.json failed validation:\n" + "\n".join(f"- {e}" for e in errors)
        )
    return corpus

