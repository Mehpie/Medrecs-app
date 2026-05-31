from __future__ import annotations

import base64
import io
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

import fitz
from PIL import Image
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .schemas import (
    DocumentElement,
    ElementType,
    PageElementsResult,
    StructuredDocument,
)

T = TypeVar("T")


PAGE_EXTRACT_SYSTEM = """You are a medical document layout extraction agent.
Extract SEMANTIC layout blocks — NOT one element per printed line.

## Element types
HEADER, BANNER, BARCODE, TEXT, CHECKBOX, TABLE, IMAGE, SIGNATURE, FOOTER

## BANNER rules (critical — page chrome, NOT clinical sections)
Use BANNER for repeated page chrome at the top of the page:
- Patient demographics strip (name, DOB, Acc No, DOS) — e.g. "SAYED, MURWARED DOB: Nov 26, 2002 (21 yo F) Acc No. 23486"
- Print timestamps — e.g. "5/16/24, 6:30 PM"
- Multi-line facility letterhead / clinic address blocks at the top
- Document title lines that repeat on every page (e.g. "Patient Medical Record")
Never use BANNER for clinical section titles like "Examination" or "Subjective:".

## HEADER rules (critical — clinical section headings only)
Use HEADER only for short clinical section labels that introduce body content below:
- Examples: "Presenting Problem:", "Past Medical History", "Allergies", "Examination", "Assessments", "Subjective:", "Objective:", "Assessment:", "Plan:", "Progress Notes", "Flowsheet:", "Follow Up"
- Must be a section title, NOT page chrome or patient demographics
- Do NOT label patient name/DOB/Acc No lines as HEADER
- Short title lines may each be HEADER; do not merge unrelated headers together

## TEXT granularity (critical)
- TEXT = one element per PARAGRAPH or continuous body block
- Merge all wrapped lines of the same paragraph into a single "content" string (use spaces between lines)
- One bounding_boxes entry enclosing the FULL paragraph (union of all its lines)
- Do NOT emit separate elements for each visual line of the same paragraph
- Form/meta lines: keep logical units together when on the same block

## Other types
- TABLE = one element per table (markdown pipe table in content, one enclosing box)
- CHECKBOX content: "state: CHECKED|UNCHECKED | label: <label text>"
- SIGNATURE content: "PRESENCE_DETECTED" when a signature/stamp area exists, else omit
- IMAGE content: brief description only (do NOT output base64)
- FOOTER = bottom-of-page only (page numbers, legal disclaimers) — NOT top patient strips
- BARCODE = barcode regions

## Bounding boxes
- Normalized [x0, y0, x1, y1], values 0.0–1.0, top-left origin
- Must wrap the entire semantic block, not a single text line

## Output
- Top-to-bottom, then left-to-right order
- page_number must match the user message
- If the page is blank, return {"elements": []}
- Return ONLY valid JSON:
  {"elements": [{"element_type": "TEXT", "page_number": 1, "content": "...", "bounding_boxes": [[0.1, 0.2, 0.9, 0.5]]}]}
- Use "content" not "text". Never use pixel coordinates
- Escape double quotes inside content as \\". Use \\n for line breaks, not raw newlines in strings
- Valid JSON only: no trailing commas, no comments
- Transcribe faithfully. Do not invent text not visible on the page."""

PAGE_EXTRACT_USER = """page_number: {page_number}
Extract semantic layout blocks from this page image.
Remember: BANNER for page chrome (patient strip, timestamps), HEADER for clinical section titles only, one TEXT element per paragraph."""


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _slug_document_id(pdf_path: Path) -> str:
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


def _usage_from_response(raw: Any) -> Dict[str, Any]:
    meta = getattr(raw, "response_metadata", None) or {}
    usage = meta.get("usage_metadata") or meta.get("token_usage") or {}
    if not usage:
        return {}
    return {
        "prompt_tokens": usage.get("prompt_token_count") or usage.get("input_tokens"),
        "candidates_tokens": usage.get("candidates_token_count") or usage.get("output_tokens"),
        "total_tokens": usage.get("total_token_count") or usage.get("total_tokens"),
    }


def get_chat_model(model_name: str, temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    api_key = _require_env("GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=8192,
    )


def _attempt_sequence(primary: str, retry: str, max_retries: int) -> List[str]:
    if max_retries <= 1:
        return [primary]
    # First attempt uses primary, remaining attempts use retry model.
    return [primary] + [retry] * (max_retries - 1)


def invoke_with_retries(
    invoke_fn: Callable[[str], Tuple[T, Dict[str, Any]]],
    *,
    primary_model: str,
    retry_model: str,
    max_retries: int,
    label: str,
) -> Tuple[T, Dict[str, Any]]:
    models = _attempt_sequence(primary_model, retry_model, max_retries)
    last_err: Exception | None = None
    for attempt, model_name in enumerate(models, start=1):
        try:
            print(
                f"  [api] {label} | attempt {attempt}/{len(models)} | model={model_name}",
                flush=True,
            )
            result, usage = invoke_fn(model_name)
            usage = dict(usage)
            usage["model"] = model_name
            usage["attempt"] = attempt
            usage["attempts_total"] = len(models)
            if attempt > 1:
                usage["retry_attempt"] = attempt
            total_toks = usage.get("total_tokens")
            tok_msg = f" total_tokens={total_toks}" if total_toks is not None else ""
            print(
                f"  [api] success {label} | attempt={attempt}{tok_msg}",
                flush=True,
            )
            return result, usage
        except Exception as exc:  # pragma: no cover - defensive
            last_err = exc
            print(
                f"  [api] failed {label} | attempt={attempt} | error={type(exc).__name__}: {exc}",
                flush=True,
            )
            if attempt < len(models):
                time.sleep(2 * attempt)
    raise RuntimeError(f"{label} failed after {len(models)} attempt(s)") from last_err


def generate_json_vision(
    *,
    system_prompt: str,
    user_prompt: str,
    image_png_bytes: bytes,
    response_model: Type[T],
    model_name: str,
) -> Tuple[T, Dict[str, Any]]:
    b64 = base64.standard_b64encode(image_png_bytes).decode("ascii")
    llm = get_chat_model(model_name).with_structured_output(response_model, include_raw=True)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]
        ),
    ]
    out = llm.invoke(messages)
    usage = _usage_from_response(out.get("raw")) if isinstance(out, dict) else {}
    if isinstance(out, dict) and "parsed" in out:
        parsed = out["parsed"]
        return response_model.model_validate(parsed), usage
    return response_model.model_validate(out), usage


def extract_page_elements(
    png_bytes: bytes,
    page_number: int,
    *,
    model_name: str,
) -> Tuple[PageElementsResult, Dict[str, Any]]:
    user = PAGE_EXTRACT_USER.format(page_number=page_number)
    return generate_json_vision(
        system_prompt=PAGE_EXTRACT_SYSTEM,
        user_prompt=user,
        image_png_bytes=png_bytes,
        response_model=PageElementsResult,
        model_name=model_name,
    )


@dataclass(frozen=True)
class VisionExtractorConfig:
    dpi: int = 150
    primary_model: str = "gemini-3-flash-preview"
    retry_model: str = "gemini-3.1-pro-preview"
    max_retries: int = 3


def extract_structured_document(
    pdf_path: Path,
    *,
    n_pages: Optional[int] = None,
    document_id: Optional[str] = None,
    config: Optional[VisionExtractorConfig] = None,
) -> Tuple[StructuredDocument, List[Dict[str, Any]]]:
    """
    Phase-2: Produce a StructuredDocument of DocumentElements for each page.

    This function intentionally keeps coordinates normalized to [0,1].
    """

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if config is None:
        config = VisionExtractorConfig(
            dpi=int(os.getenv("PHASE2_DPI", "150")),
            primary_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
            retry_model=os.getenv("GEMINI_MODEL_RETRY", "gemini-3.1-pro-preview"),
            max_retries=int(os.getenv("MAX_EXTRACTION_RETRIES", "3")),
        )

    doc = fitz.open(pdf_path)
    try:
        total_in_file = len(doc)
    finally:
        doc.close()

    take_n = total_in_file if n_pages is None else min(n_pages, total_in_file)

    doc_id = document_id or _slug_document_id(pdf_path)
    is_scanned = detect_scanned_ocr(pdf_path)

    all_elements: List[DocumentElement] = []
    usage_log: List[Dict[str, Any]] = []
    started_at = time.perf_counter()

    print(
        f"[pdf] start doc_id={doc_id} pages={take_n} scanned_ocr={is_scanned} dpi={config.dpi}",
        flush=True,
    )

    for i in range(take_n):
        page_number = i + 1
        print(f"[page] {page_number}/{take_n} render", flush=True)
        png = render_page_png(pdf_path, i, dpi=config.dpi)

        def _invoke(model_name: str) -> Tuple[PageElementsResult, Dict[str, Any]]:
            return extract_page_elements(png, page_number, model_name=model_name)

        page_result, usage = invoke_with_retries(
            _invoke,
            primary_model=config.primary_model,
            retry_model=config.retry_model,
            max_retries=config.max_retries,
            label=f"extract_page_elements(page={page_number})",
        )

        elements = list(page_result.elements)

        # Defensive: normalize element page_number to the one requested.
        for el in elements:
            el.page_number = page_number

        all_elements.extend(elements)
        usage_log.append({"page": page_number, "elements": len(elements), **usage})
        attempts = usage.get("attempt", 1)
        print(
            f"[page] {page_number}/{take_n} done | elements={len(elements)} attempts={attempts}",
            flush=True,
        )

    structured = StructuredDocument(
        document_id=doc_id,
        total_pages=take_n,
        is_scanned_ocr=is_scanned,
        elements=all_elements,
    )
    elapsed = time.perf_counter() - started_at
    retries_used = sum(max(0, int(u.get("attempt", 1)) - 1) for u in usage_log)
    print(
        f"[pdf] done doc_id={doc_id} pages={take_n} elements={len(all_elements)} "
        f"api_calls={len(usage_log)} retries={retries_used} elapsed_s={elapsed:.1f}",
        flush=True,
    )
    return structured, usage_log

