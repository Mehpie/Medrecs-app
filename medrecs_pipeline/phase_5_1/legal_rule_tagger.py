from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from medrecs_pipeline.phase_5.schemas import Tag

_RULE_CONFIDENCE = 0.92

# (pattern, tag_class) — conservative PI/med-legal phrase rules
_PATTERNS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(MVC|MVA)\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\bmotor vehicle\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\brear-?ended\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\bcollision\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\bcar accident\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\bsemi-?truck\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\blost consciousness\b", re.IGNORECASE), "INJURY_EVENT"),
    (re.compile(r"\bout of work\b", re.IGNORECASE), "ECONOMIC_LOSS"),
    (re.compile(r"\bunable to work\b", re.IGNORECASE), "FUNCTIONAL_LIMITATION"),
    (re.compile(r"\blost wages\b", re.IGNORECASE), "ECONOMIC_LOSS"),
    (
        re.compile(r"\bunable to (stand|walk|lift|work)\b", re.IGNORECASE),
        "FUNCTIONAL_LIMITATION",
    ),
    (
        re.compile(r"\bdifficulty (standing|walking|concentrating)\b", re.IGNORECASE),
        "FUNCTIONAL_LIMITATION",
    ),
    (
        re.compile(
            r"\b(following|due to|after) (the )?(MVC|MVA|accident|collision)\b",
            re.IGNORECASE,
        ),
        "CAUSATION_CLAIM",
    ),
    (re.compile(r"\bpre-?existing\b", re.IGNORECASE), "PRE_EXISTING_CONDITION"),
    (
        re.compile(r"\bprior to (the )?accident\b", re.IGNORECASE),
        "PRE_EXISTING_CONDITION",
    ),
    (re.compile(r"\baggravated by\b", re.IGNORECASE), "AGGRAVATING_FACTOR"),
    (
        re.compile(r"\bworse with (standing|lying)\b", re.IGNORECASE),
        "AGGRAVATING_FACTOR",
    ),
    (
        re.compile(r"\b(remains|patient remains) out of work\b", re.IGNORECASE),
        "DAILY_LIFE_IMPACT",
    ),
)


def _tags_from_match(match: re.Match[str], tag_class: str) -> Tag:
    return Tag(
        tag_class=tag_class,
        surface=match.group(0),
        start=match.start(),
        end=match.end(),
        confidence=_RULE_CONFIDENCE,
    )


def tag_legal_phrases(body_text: str) -> List[Tag]:
    """Extract legal tags from PI phrase regex rules."""
    text = body_text or ""
    tags: List[Tag] = []
    seen: set[Tuple[str, int, int]] = set()

    for pattern, tag_class in _PATTERNS:
        for match in pattern.finditer(text):
            key = (tag_class, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            tags.append(_tags_from_match(match, tag_class))

    # ECONOMIC_LOSS "out of work" also warrants FUNCTIONAL_LIMITATION on same span
    extra: List[Tag] = []
    for tag in tags:
        if tag.tag_class == "ECONOMIC_LOSS" and tag.surface.lower() == "out of work":
            extra.append(
                Tag(
                    tag_class="FUNCTIONAL_LIMITATION",
                    surface=tag.surface,
                    start=tag.start,
                    end=tag.end,
                    confidence=_RULE_CONFIDENCE,
                )
            )
    tags.extend(extra)
    return tags


def count_rule_hits(tags: Iterable[Tag]) -> int:
    return sum(1 for _ in tags)
