"""PDF page rendering and Gemini vision extraction for structured layout JSON."""
import io
import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz
from PIL import Image

from src.extract_schemas import (
    DocumentElement,
    PageElementsResult,
    StructuredDocument,
)
from src.llm import generate_json_vision, invoke_with_model_retries

PAGE_EXTRACT_SYSTEM = """You are a medical document layout extraction agent.
Analyze the page image and extract every visible layout element.

Rules:
- bounding_boxes use normalized coordinates [x0, y0, x1, y1] with values from 0.0 to 1.0 (top-left origin).
- element_type must be one of: HEADER, BARCODE, TEXT, CHECKBOX, TABLE, IMAGE, SIGNATURE, FOOTER.
- Transcribe TEXT, HEADER, FOOTER, BARCODE, and TABLE content faithfully (TABLE as markdown pipe table).
- CHECKBOX content format: "state: CHECKED|UNCHECKED | label: <label text>".
- SIGNATURE content: "PRESENCE_DETECTED" when a signature/stamp area exists, else omit the element.
- IMAGE content: brief description only (do NOT output base64). Example: "Chest X-ray thumbnail".
- Order elements top-to-bottom, then left-to-right.
- page_number in every element must match the page number given in the user message.
- If the page is blank, return {"elements": []}.
- Do not invent content not visible on the page."""

PAGE_EXTRACT_USER = """page_number: {page_number}
Extract all layout elements from this page image.
Return JSON: {{"elements": [{{"element_type": "...", "page_number": {page_number}, "content": "...", "bounding_boxes": [[x0,y0,x1,y1]]}}]}}"""


def slug_document_id(pdf_path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", pdf_path.stem).strip("_").lower()
    return f"doc_{stem}" if stem else "doc_unknown"


def render_page_png(pdf_path: Path, page_index: int, dpi: int = 150) -> bytes:
    doc = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= len(doc):
            raise IndexError(f"Page index {page_index} out of range (0-{len(doc) - 1})")
        page = doc[page_index]
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def page_text_density(pdf_path: Path, page_index: int) -> float:
    """Chars per page area — low density suggests scanned/image PDF."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        text = (page.get_text() or "").strip()
        rect = page.rect
        area = max(rect.width * rect.height, 1.0)
        return len(text) / area
    finally:
        doc.close()


def detect_scanned_ocr(pdf_path: Path, sample_pages: int = 3, threshold: float = 0.002) -> bool:
    doc = fitz.open(pdf_path)
    try:
        n = min(sample_pages, len(doc))
        if n == 0:
            return True
        densities = [page_text_density(pdf_path, i) for i in range(n)]
        return sum(densities) / len(densities) < threshold
    finally:
        doc.close()


def extract_page_elements(
    png_bytes: bytes,
    page_number: int,
    model_name: Optional[str] = None,
) -> Tuple[PageElementsResult, dict]:
    user = PAGE_EXTRACT_USER.format(page_number=page_number)
    result, usage = generate_json_vision(
        PAGE_EXTRACT_SYSTEM,
        user,
        png_bytes,
        PageElementsResult,
        model_name=model_name,
    )
    for el in result.elements:
        el.page_number = page_number
    return result, usage


def crop_element_base64(
    png_bytes: bytes,
    box: List[float],
    max_width: int = 512,
) -> str:
    """Crop normalized bbox from page image and return data URI (for IMAGE elements)."""
    import base64

    img = Image.open(io.BytesIO(png_bytes))
    w, h = img.size
    x0, y0, x1, y1 = box
    left = int(x0 * w)
    top = int(y0 * h)
    right = int(x1 * w)
    bottom = int(y1 * h)
    cropped = img.crop((left, top, right, bottom))
    if cropped.width > max_width:
        ratio = max_width / cropped.width
        cropped = cropped.resize(
            (max_width, max(1, int(cropped.height * ratio))), Image.Resampling.LANCZOS
        )
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def enrich_image_elements(
    elements: List[DocumentElement],
    png_bytes: bytes,
    embed_crops: bool = True,
) -> List[DocumentElement]:
    if not embed_crops:
        return elements
    out: List[DocumentElement] = []
    for el in elements:
        if el.element_type.value == "IMAGE" and el.bounding_boxes:
            try:
                el = el.model_copy(
                    update={"content": crop_element_base64(png_bytes, el.bounding_boxes[0])}
                )
            except Exception:
                pass
        out.append(el)
    return out


def extract_structured_document(
    pdf_path: Path,
    n_pages: int,
    document_id: Optional[str] = None,
    dpi: int = 150,
    embed_image_crops: bool = False,
    model_name: Optional[str] = None,
) -> Tuple[StructuredDocument, List[dict]]:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    total_in_file = len(doc)
    doc.close()

    n = min(n_pages, total_in_file)
    doc_id = document_id or slug_document_id(pdf_path)
    is_scanned = detect_scanned_ocr(pdf_path)

    all_elements: List[DocumentElement] = []
    usage_log: List[dict] = []

    for i in range(n):
        page_number = i + 1
        png = render_page_png(pdf_path, i, dpi=dpi)
        page_result, usage = extract_page_elements(png, page_number, model_name=model_name)
        elements = page_result.elements
        if embed_image_crops:
            elements = enrich_image_elements(elements, png, embed_crops=True)
        all_elements.extend(elements)
        usage_log.append({"page": page_number, **usage})

    return (
        StructuredDocument(
            document_id=doc_id,
            total_pages=n,
            is_scanned_ocr=is_scanned,
            elements=all_elements,
        ),
        usage_log,
    )
