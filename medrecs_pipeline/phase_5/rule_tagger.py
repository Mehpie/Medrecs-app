from __future__ import annotations

import re
from typing import List

from medrecs_pipeline.phase_4.code_detect import _CPT_CODE, _ICD_LINE, _LAB_PANEL_HEADER, _VISIT_CODE

from .schemas import Tag

_RULE_CONFIDENCE = 0.95

_ICD_CODE = re.compile(r"[A-TV-Z]\d{2}\.\d+[A-Z0-9]*", re.IGNORECASE)


def tag_code_chunk(body_text: str) -> List[Tag]:
    """Deterministic tags for structured code / billing / lab chunks."""
    text = body_text or ""
    tags: List[Tag] = []
    tags.extend(_tag_icd_lines(text))
    tags.extend(_tag_cpt_codes(text))
    tags.extend(_tag_visit_codes(text))
    tags.extend(_tag_lab_panel(text))
    return tags


def _tag_icd_lines(text: str) -> List[Tag]:
    tags: List[Tag] = []
    for match in _ICD_LINE.finditer(text):
        line = match.group(0)
        code_match = _ICD_CODE.search(line)
        if code_match:
            start = match.start() + code_match.start()
            end = match.start() + code_match.end()
            surface = text[start:end]
        else:
            start = match.start()
            end = match.end()
            surface = line.strip()
        tags.append(
            Tag(
                tag_class="DIAGNOSIS",
                surface=surface,
                start=start,
                end=end,
                confidence=_RULE_CONFIDENCE,
            )
        )
    return tags


def _tag_cpt_codes(text: str) -> List[Tag]:
    if "procedure codes" not in text.lower():
        return []
    tags: List[Tag] = []
    for match in _CPT_CODE.finditer(text):
        tags.append(
            Tag(
                tag_class="PROCEDURE",
                surface=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=_RULE_CONFIDENCE,
            )
        )
    return tags


def _tag_visit_codes(text: str) -> List[Tag]:
    lowered = text.lower()
    if "visit code" not in lowered and "billing information" not in lowered:
        return []
    tags: List[Tag] = []
    for match in _VISIT_CODE.finditer(text):
        tags.append(
            Tag(
                tag_class="PROCEDURE",
                surface=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=_RULE_CONFIDENCE,
            )
        )
    return tags


def _tag_lab_panel(text: str) -> List[Tag]:
    if not _LAB_PANEL_HEADER.search(text):
        return []
    tags: List[Tag] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or ":---" in stripped:
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = cells[0]
        if name.lower() in {"name", "test", "component"}:
            continue
        idx = text.find(line)
        if idx < 0:
            continue
        name_start = text.find(name, idx)
        if name_start < 0:
            continue
        tags.append(
            Tag(
                tag_class="LAB_RESULT",
                surface=name,
                start=name_start,
                end=name_start + len(name),
                confidence=_RULE_CONFIDENCE,
            )
        )
    return tags
