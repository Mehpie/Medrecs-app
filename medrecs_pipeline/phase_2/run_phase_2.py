from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import fitz
from dotenv import load_dotenv

from .schemas import ExtractedUnitsCorpus, ElementType
from .structured_to_units import (
    assert_stage2_shape,
    structured_document_to_extracted_units,
)
from .vision_extractor import VisionExtractorConfig, extract_structured_document


def _load_phase2_config() -> VisionExtractorConfig:
    return VisionExtractorConfig(
        dpi=int(os.getenv("PHASE2_DPI", "150")),
        primary_model=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        retry_model=os.getenv("GEMINI_MODEL_RETRY", "gemini-3.1-pro-preview"),
        max_retries=int(os.getenv("MAX_EXTRACTION_RETRIES", "3")),
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_pdf(pdf_path: Path, *, output_root: Path, config: VisionExtractorConfig) -> None:
    input_doc_id = pdf_path.stem
    started_at = time.perf_counter()
    with fitz.open(pdf_path) as doc:
        input_pages = len(doc)
    min_api_calls = input_pages
    max_api_calls = input_pages * max(1, config.max_retries)
    print(
        f"[pdf] {pdf_path.name} | pages={input_pages} | expected_api_calls={min_api_calls}..{max_api_calls}",
        flush=True,
    )

    structured, usage_log = extract_structured_document(
        pdf_path,
        n_pages=None,  # all pages
        document_id=None,  # use deterministic slug internally
        config=config,
    )

    # 1) Persist raw vision/layout output.
    structured_out = (
        output_root / "structured_documents" / f"{structured.document_id}_structured_document.json"
    )
    _write_json(structured_out, structured.model_dump(mode="json"))

    element_type_counts = Counter(el.element_type.value for el in structured.elements)
    print(
        f"      element_types: "
        f"HEADER={element_type_counts.get(ElementType.HEADER.value, 0)} "
        f"BANNER={element_type_counts.get(ElementType.BANNER.value, 0)} "
        f"TEXT={element_type_counts.get(ElementType.TEXT.value, 0)} "
        f"TABLE={element_type_counts.get(ElementType.TABLE.value, 0)}",
        flush=True,
    )

    # 2) Convert to Stage-2-style ExtractedUnit list for Stage-4 chunking.
    units, warnings = structured_document_to_extracted_units(
        structured, model_name=config.primary_model
    )

    # Validate structure for downstream safety.
    errors = assert_stage2_shape(units)
    if errors:
        raise RuntimeError(
            "Phase-2 conversion produced invalid Stage-2 units:\n"
            + "\n".join(f"- {e}" for e in errors)
        )

    corpus = ExtractedUnitsCorpus(
        doc_id=structured.document_id,
        total_pages=structured.total_pages,
        is_scanned_ocr=structured.is_scanned_ocr,
        model_name=config.primary_model,
        units=units,
        meta={
            "warnings": warnings,
            "source_pdf_stem": input_doc_id,
            "dpi": config.dpi,
            "primary_model": config.primary_model,
            "retry_model": config.retry_model,
        },
    )

    extracted_out = (
        output_root / "extracted_units" / f"{structured.document_id}_extracted_units.json"
    )
    _write_json(extracted_out, corpus.model_dump(mode="json"))

    usage_out = output_root / "usage_logs" / f"{structured.document_id}_usage_log.json"
    _write_json(usage_out, usage_log)

    total_attempts = sum(int(u.get("attempt", 1)) for u in usage_log)
    retries_used = sum(max(0, int(u.get("attempt", 1)) - 1) for u in usage_log)
    elapsed_s = time.perf_counter() - started_at
    print(
        f"[pdf] complete {pdf_path.name} | doc_id={structured.document_id} | "
        f"pages={structured.total_pages} elements={len(structured.elements)} units={len(units)}",
        flush=True,
    )
    print(
        f"      api_calls={len(usage_log)} total_attempts={total_attempts} retries={retries_used} "
        f"elapsed_s={elapsed_s:.1f}",
        flush=True,
    )
    print(
        f"      outputs:\n"
        f"        - {structured_out}\n"
        f"        - {extracted_out}\n"
        f"        - {usage_out}",
        flush=True,
    )


def main() -> int:
    load_dotenv()
    config = _load_phase2_config()

    # Paths relative to this file:
    # medrecs_pipeline/phase_2/run_phase_2.py -> medrecs_pipeline/
    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "input_phase_2"
    output_dir = pipeline_root / "data" / "output_phase_2"

    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")

    pdfs = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in: {input_dir}")

    print(
        f"Phase-2 start: {len(pdfs)} pdf(s) | output={output_dir}\n"
        f"primary_model={config.primary_model} retry_model={config.retry_model} dpi={config.dpi}"
    )

    for pdf_path in pdfs:
        print(f"\nProcessing: {pdf_path.name}")
        run_one_pdf(pdf_path, output_root=output_dir, config=config)
        print(f"Done: {pdf_path.name}")

    print("\nPhase-2 complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

