from __future__ import annotations

CLINICAL_CLASSES: frozenset[str] = frozenset(
    {
        "SYMPTOM",
        "DIAGNOSIS",
        "FINDING",
        "MEDICATION",
        "DOSAGE",
        "FREQUENCY",
        "ROUTE",
        "PROCEDURE",
        "ANATOMY",
        "IMAGING_FINDING",
        "LAB_RESULT",
        "TEMPORAL_MARKER",
        "SEVERITY",
        "NEGATION",
        "FAMILY_HISTORY",
        "SOCIAL_HISTORY",
        "INFECTIOUS_DISEASE",
        "COGNITIVE_DEFICIT",
        "MOTOR_DEFICIT",
        "VESTIBULAR_DEFICIT",
        "AUTONOMIC_DEFICIT",
    }
)

LEGAL_CLASSES: frozenset[str] = frozenset(
    {
        "INJURY_EVENT",
        "CAUSATION_CLAIM",
        "FUNCTIONAL_LIMITATION",
        "DAILY_LIFE_IMPACT",
        "ECONOMIC_LOSS",
        "LOSS_OF_CONSORTIUM",
        "MITIGATING_FACTOR",
        "AGGRAVATING_FACTOR",
        "PRE_EXISTING_CONDITION",
        "ALLEGED_NEGLIGENCE",
    }
)

ALL_TAG_CLASSES: frozenset[str] = CLINICAL_CLASSES | LEGAL_CLASSES


def clinical_classes_prompt() -> str:
    return ", ".join(sorted(CLINICAL_CLASSES))


def legal_classes_prompt() -> str:
    return ", ".join(sorted(LEGAL_CLASSES))


def is_clinical_class(tag_class: str) -> bool:
    return tag_class in CLINICAL_CLASSES


def is_legal_class(tag_class: str) -> bool:
    return tag_class in LEGAL_CLASSES
