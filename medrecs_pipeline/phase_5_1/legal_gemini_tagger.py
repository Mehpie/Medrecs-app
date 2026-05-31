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

from medrecs_pipeline.phase_5.schemas import TaggedChunk
from medrecs_pipeline.phase_5.vocab import legal_classes_prompt

from .schemas import GeminiLegalExtraction

logger = logging.getLogger(__name__)

LEGAL_SYSTEM_PROMPT = f"""You are a US personal-injury / med-legal named-entity recognition tagger.

Extract ONLY legal entities from EMR and med-legal text. Do NOT emit clinical tags.

Legal entity classes (use exactly these labels):
{legal_classes_prompt()}

Class guidance:
- INJURY_EVENT: accident mechanism (MVC, MVA, rear-ended, collision, fall, lost consciousness at scene).
- CAUSATION_CLAIM: language linking symptoms/injury to accident (following MVC, due to accident, caused by collision).
- FUNCTIONAL_LIMITATION: inability to work, stand, walk, lift, or perform work duties.
- DAILY_LIFE_IMPACT: ADL disruption (out of work, sleep disturbance affecting function, cannot drive).
- ECONOMIC_LOSS: lost wages, out of work, unable to return to work.
- PRE_EXISTING_CONDITION: prior injury, pre-existing, before the accident.
- AGGRAVATING_FACTOR: worse with standing/lying, aggravated by activity.
- MITIGATING_FACTOR: improved with rest/treatment.
- ALLEGED_NEGLIGENCE: negligence, at-fault, liability language.
- LOSS_OF_CONSORTIUM: loss of consortium (rare in EMR).

Rules:
- US PI context only. No UK case citations or statutes.
- Return character offsets into the exact input string: body_text[start:end] == surface when possible.
- confidence 0.0–1.0.
- Scan even when text is clinically framed — EMR notes often bury legal signals in HPI.
- Examples:
  - "rear-ended by a semi-truck" → INJURY_EVENT
  - "MVC on 12/4/23" → INJURY_EVENT
  - "remains out of work" → ECONOMIC_LOSS + FUNCTIONAL_LIMITATION + DAILY_LIFE_IMPACT
  - "may reflect injury" (in imaging/impression) → CAUSATION_CLAIM
- Return at most 25 legal_tags. Prefer highest-confidence entities.
- If no legal entities apply, return an empty legal_tags list.
- Do not invent entities not present in the text."""


def build_legal_user_prompt(chunk: TaggedChunk) -> str:
    section = " / ".join(chunk.section_path) if chunk.section_path else "UNSPECIFIED"
    return (
        f"chunk_id: {chunk.chunk_id}\n"
        f"section_path: {section}\n"
        f"atomic_kind: {chunk.atomic_kind}\n\n"
        f"Extract legal_tags ONLY from the following text:\n---\n{chunk.body_text}\n---"
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


def _coerce_extraction(payload: Any) -> GeminiLegalExtraction:
    if isinstance(payload, GeminiLegalExtraction):
        return payload
    if isinstance(payload, dict):
        return GeminiLegalExtraction.model_validate(payload)
    raise ValueError(f"unexpected legal extraction payload type: {type(payload)!r}")


def _sanitize_extraction(extraction: GeminiLegalExtraction) -> GeminiLegalExtraction:
    legal: list = []
    dropped = 0
    for tag in extraction.legal_tags:
        try:
            legal.append(tag.model_copy())
        except ValidationError:
            dropped += 1
    if dropped:
        logger.debug("dropped %d invalid legal LlmTag row(s)", dropped)
    return GeminiLegalExtraction(legal_tags=legal)


def _invoke_once(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    *,
    chunk_id: str,
) -> tuple[GeminiLegalExtraction, dict]:
    llm = get_chat_model(model_name).with_structured_output(
        GeminiLegalExtraction, include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    out = llm.invoke(messages)
    usage = usage_from_response(out.get("raw")) if isinstance(out, dict) else {}
    usage["parse_mode"] = "structured"

    if isinstance(out, GeminiLegalExtraction):
        return _sanitize_extraction(out), usage

    if isinstance(out, dict):
        parsed = out.get("parsed")
        if parsed is not None:
            try:
                return _sanitize_extraction(_coerce_extraction(parsed)), usage
            except (ValidationError, ValueError) as exc:
                logger.warning(
                    "[pass51] chunk=%s model=%s structured parsed invalid: %s",
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
                        "[pass51] chunk=%s model=%s recovered via %s",
                        chunk_id,
                        model_name,
                        mode,
                    )
                    return extraction, usage
                except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
                    continue
            logger.warning(
                "[pass51] chunk=%s model=%s parse failed; raw_preview=%r",
                chunk_id,
                model_name,
                raw_text[:300],
            )

    raise ValueError(
        f"chunk={chunk_id} model={model_name}: no parseable GeminiLegalExtraction"
    )


def extract_legal_with_gemini(chunk: TaggedChunk) -> tuple[GeminiLegalExtraction, dict]:
    user_prompt = build_legal_user_prompt(chunk)

    def _invoke(model_name: str) -> tuple[GeminiLegalExtraction, dict]:
        return _invoke_once(
            model_name,
            LEGAL_SYSTEM_PROMPT,
            user_prompt,
            chunk_id=chunk.chunk_id,
        )

    return invoke_with_model_retries(
        _invoke,
        label=f"phase51_legal chunk={chunk.chunk_id}",
    )
