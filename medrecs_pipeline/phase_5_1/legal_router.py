from __future__ import annotations

import os
import re
from dataclasses import dataclass

from medrecs_pipeline.phase_5.schemas import TaggedChunk

LEGAL_SECTION_KEYWORDS = frozenset(
    {
        "hpi",
        "history of present illness",
        "subjective",
        "assessment",
        "assessments",
        "chief complaint",
        "chief complaints",
        "plan",
        "treatment",
        "voc",
        "social",
        "constitutional",
    }
)

_PI_PHRASE = re.compile(
    r"\b("
    r"mvc|mva|motor vehicle|rear-?ended|collision|accident|semi-?truck|"
    r"lost consciousness|out of work|unable to work|"
    r"following the|due to the accident"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LegalRouterConfig:
    all_prose: bool = False

    @classmethod
    def from_env(cls) -> "LegalRouterConfig":
        return cls(
            all_prose=os.getenv("PHASE5_1_ALL_PROSE", "false").lower() in {"1", "true", "yes"},
        )


def _section_blob(chunk: TaggedChunk) -> str:
    return " / ".join(chunk.section_path).lower() if chunk.section_path else "unspecified"


def matches_legal_section(chunk: TaggedChunk) -> bool:
    blob = _section_blob(chunk)
    return any(kw in blob for kw in LEGAL_SECTION_KEYWORDS)


def has_pi_phrase(body_text: str) -> bool:
    return bool(_PI_PHRASE.search(body_text or ""))


def should_route_legal(chunk: TaggedChunk, config: LegalRouterConfig) -> bool:
    if chunk.tagging_method == "skipped":
        return False
    if chunk.atomic_kind == "code":
        return False
    if chunk.atomic_kind != "prose":
        return False

    if config.all_prose:
        return True

    section_match = matches_legal_section(chunk)
    pi_signal = has_pi_phrase(chunk.body_text)

    if section_match and not chunk.legal_tags:
        return True
    if section_match:
        return True
    if pi_signal:
        return True

    if (
        chunk.token_count < 16
        and not pi_signal
        and _section_blob(chunk) == "unspecified"
    ):
        return False

    return False


def route_reason(chunk: TaggedChunk, config: LegalRouterConfig) -> str:
    if not should_route_legal(chunk, config):
        return "skip"
    if config.all_prose:
        return "all_prose"
    if matches_legal_section(chunk) and not chunk.legal_tags:
        return "section_empty_legal"
    if matches_legal_section(chunk):
        return "section"
    if has_pi_phrase(chunk.body_text):
        return "pi_phrase"
    return "prose"
