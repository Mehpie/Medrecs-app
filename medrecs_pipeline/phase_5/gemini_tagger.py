from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import json_repair
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from src.llm import get_chat_model, invoke_with_model_retries, usage_from_response

from .schemas import Chunk, GeminiTagExtraction
from .vocab import clinical_classes_prompt, legal_classes_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a US medical-legal named-entity recognition tagger for electronic medical records and personal-injury case documents.

Extract entities from the user-provided text and return character offsets relative to that exact input string.

Clinical entity classes (use exactly these labels):
{clinical_classes_prompt()}

Legal entity classes — US personal-injury / med-legal only (use exactly these labels):
{legal_classes_prompt()}

Rules:
- US context only. Do not tag UK case citations, statutes, or instruments.
- Do not tag page chrome: print timestamps, "Page X of Y", file paths, EMR software footers, or bare section headers with no clinical content.
- Return start/end as Python-style character offsets: body_text[start:end] must equal surface when possible.
- confidence is 0.0–1.0 reflecting extraction certainty.
- The same span may appear in both clinical_tags and legal_tags when clinically and legally relevant (e.g. pain limiting daily activities).
- Examples: "MVC on 12/4/23" → INJURY_EVENT + TEMPORAL_MARKER; "concussion with loss of consciousness" → DIAGNOSIS; "unable to work" → FUNCTIONAL_LIMITATION + DAILY_LIFE_IMPACT.
- Return at most 40 tags per domain; prefer highest-confidence entities.
- If no entities apply, return empty lists.
- Do not invent entities not present in the text."""


def build_user_prompt(chunk: Chunk) -> str:
    section = " / ".join(chunk.section_path) if chunk.section_path else "UNSPECIFIED"
    return (
        f"chunk_id: {chunk.chunk_id}\n"
        f"section_path: {section}\n"
        f"atomic_kind: {chunk.atomic_kind}\n\n"
        f"Tag the following text:\n---\n{chunk.body_text}\n---"
    )


def _raw_text_from_response(raw: Any) -> str:
    if raw is None:
        return ""
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _coerce_extraction(payload: Any) -> GeminiTagExtraction:
    if isinstance(payload, GeminiTagExtraction):
        return payload
    if isinstance(payload, dict):
        return GeminiTagExtraction.model_validate(payload)
    raise ValueError(f"unexpected extraction payload type: {type(payload)!r}")


def _sanitize_extraction(extraction: GeminiTagExtraction) -> GeminiTagExtraction:
    """Drop malformed LLM tags without failing the whole chunk."""
    clinical: list = []
    legal: list = []
    dropped = 0
    for tag in extraction.clinical_tags:
        try:
            clinical.append(tag.model_copy())
        except ValidationError:
            dropped += 1
    for tag in extraction.legal_tags:
        try:
            legal.append(tag.model_copy())
        except ValidationError:
            dropped += 1
    if dropped:
        logger.debug("dropped %d invalid LlmTag row(s) during sanitize", dropped)
    return GeminiTagExtraction(clinical_tags=clinical, legal_tags=legal)


def _invoke_once(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    chunk_id: str,
) -> tuple[GeminiTagExtraction, dict]:
    llm = get_chat_model(model_name).with_structured_output(
        GeminiTagExtraction, include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    out = llm.invoke(messages)
    usage = usage_from_response(out.get("raw")) if isinstance(out, dict) else {}
    usage["parse_mode"] = "structured"

    if isinstance(out, GeminiTagExtraction):
        return _sanitize_extraction(out), usage

    if isinstance(out, dict):
        parsed = out.get("parsed")
        if parsed is not None:
            try:
                return _sanitize_extraction(_coerce_extraction(parsed)), usage
            except (ValidationError, ValueError) as exc:
                logger.warning(
                    "[pass5] chunk=%s model=%s structured parsed invalid: %s",
                    chunk_id,
                    model_name,
                    exc,
                )

        raw_text = _raw_text_from_response(out.get("raw"))
        if raw_text.strip():
            for mode, loader in (
                ("json", json.loads),
                ("json_repair", json_repair.loads),
            ):
                try:
                    payload = loader(raw_text)
                    extraction = _sanitize_extraction(_coerce_extraction(payload))
                    usage["parse_mode"] = mode
                    logger.warning(
                        "[pass5] chunk=%s model=%s recovered via %s (structured parsed was None)",
                        chunk_id,
                        model_name,
                        mode,
                    )
                    return extraction, usage
                except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
                    continue

            logger.warning(
                "[pass5] chunk=%s model=%s parse failed; raw_preview=%r",
                chunk_id,
                model_name,
                raw_text[:300],
            )
        else:
            logger.warning(
                "[pass5] chunk=%s model=%s empty raw response",
                chunk_id,
                model_name,
            )

    raise ValueError(
        f"chunk={chunk_id} model={model_name}: no parseable GeminiTagExtraction"
    )


def extract_tags_with_gemini(chunk: Chunk) -> tuple[GeminiTagExtraction, dict]:
    user_prompt = build_user_prompt(chunk)

    def _invoke(model_name: str) -> tuple[GeminiTagExtraction, dict]:
        return _invoke_once(
            model_name,
            SYSTEM_PROMPT,
            user_prompt,
            chunk_id=chunk.chunk_id,
        )

    return invoke_with_model_retries(
        _invoke,
        label=f"phase5_tag chunk={chunk.chunk_id}",
    )
