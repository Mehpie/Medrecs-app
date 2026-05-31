from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

from .schemas import Tag
from .vocab import is_clinical_class, is_legal_class


@dataclass(frozen=True)
class ThresholdConfig:
    tau_clinical: float = 0.7
    tau_legal: float = 0.6
    tau_uncertain_low: float = 0.4

    @classmethod
    def from_env(cls) -> "ThresholdConfig":
        return cls(
            tau_clinical=float(os.getenv("PHASE5_TAU_CLINICAL", "0.7")),
            tau_legal=float(os.getenv("PHASE5_TAU_LEGAL", "0.6")),
            tau_uncertain_low=float(os.getenv("PHASE5_TAU_UNCERTAIN_LOW", "0.4")),
        )


def apply_thresholds(
    clinical_tags: List[Tag],
    legal_tags: List[Tag],
    *,
    config: ThresholdConfig | None = None,
) -> Tuple[List[Tag], List[Tag], List[Tag], int]:
    """
    Bucket tags into clinical_tags, legal_tags, uncertain_tags.
    Returns (clinical, legal, uncertain, dropped_invalid_class_count).
    """
    cfg = config or ThresholdConfig.from_env()
    out_clinical: List[Tag] = []
    out_legal: List[Tag] = []
    out_uncertain: List[Tag] = []
    dropped = 0

    for tag in clinical_tags:
        if not is_clinical_class(tag.tag_class):
            dropped += 1
            continue
        if tag.confidence >= cfg.tau_clinical:
            out_clinical.append(tag)
        elif tag.confidence >= cfg.tau_uncertain_low:
            out_uncertain.append(tag)

    for tag in legal_tags:
        if not is_legal_class(tag.tag_class):
            dropped += 1
            continue
        if tag.confidence >= cfg.tau_legal:
            out_legal.append(tag)
        elif tag.confidence >= cfg.tau_uncertain_low:
            out_uncertain.append(tag)

    return out_clinical, out_legal, out_uncertain, dropped
