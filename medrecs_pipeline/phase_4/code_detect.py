from __future__ import annotations

import re

_ICD_LINE = re.compile(
    r"^\s*\d+\.\s+.+\s-\s[A-TV-Z]\d{2}\.\d+[A-Z0-9]*",
    re.MULTILINE | re.IGNORECASE,
)
_CPT_CODE = re.compile(r"\b\d{5}\b")
_VISIT_CODE = re.compile(r"\b992\d{2}\b")
_LAB_PANEL_HEADER = re.compile(
    r"\|\s*Name\s*\|\s*Value\s*\|\s*Reference Range\s*\|",
    re.IGNORECASE,
)


def is_code_like(text: str) -> bool:
    """
    Heuristic detection of structured code blocks (ICD/CPT/billing/lab panels).
    Conservative: prefer false negatives over splitting clinical narrative.
    """
    text = (text or "").strip()
    if not text:
        return False

    if _is_icd_list(text):
        return True
    if _is_cpt_block(text):
        return True
    if _is_visit_billing_block(text):
        return True
    if _is_lab_panel(text):
        return True
    return False


def _is_icd_list(text: str) -> bool:
    matches = _ICD_LINE.findall(text)
    return len(matches) >= 3


def _is_cpt_block(text: str) -> bool:
    if "procedure codes" not in text.lower():
        return False
    return len(_CPT_CODE.findall(text)) >= 1


def _is_visit_billing_block(text: str) -> bool:
    lowered = text.lower()
    if "visit code" not in lowered and "billing information" not in lowered:
        return False
    if _VISIT_CODE.search(text):
        return True
    return "office visit" in lowered and len(text) < 400


def _is_lab_panel(text: str) -> bool:
    if _LAB_PANEL_HEADER.search(text):
        return True
    pipe_lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(pipe_lines) >= 3 and len(pipe_lines) / max(len(text.splitlines()), 1) >= 0.5:
        return True
    return False
