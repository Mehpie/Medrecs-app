"""Dehyphenate patent prose (matches rewritten_patent_application.txt cleanup)."""

from __future__ import annotations

import re

COMPOUNDS = [
    "Cache-Augmented Generation",
    "Cache-Augmented",
    "Retrieval-Augmented Generation",
    "Retrieval-Augmented",
    "computer-implemented",
    "non-transitory",
    "cache-augmented",
    "multi-document",
    "cross-document",
    "cross-modal",
    "cross-disciplinary",
    "cross-temporal",
    "Cross-Temporal",
    "causal-candidate",
    "vector-space",
    "page-level",
    "page-provenance",
    "page-attribution",
    "domain-specific",
    "section-specific",
    "document-type",
    "entity-tag",
    "date-of-documentation",
    "source-document",
    "dual-domain",
    "medical-legal",
    "Medical-Legal",
    "third-party",
    "pre-defined",
    "citation-enriched",
    "Citation-Enriched",
    "forced-tag",
    "Forced-Tag",
    "controlled-vocabulary-validated",
    "controlled-vocabulary",
    "RAG-based",
    "base-model-plus-prompting",
    "causation-anchored",
    "fragment-based",
    "metadata-text",
    "associated-extracted",
    "post-COVID-19",
    "COVID-19",
    "Vector-Space",
    "Page-Level",
    "hard-coded",
    "quota-check",
    "context-aware",
    "surface-level",
    "distance-based",
    "catalog-style",
    "cross-reference",
    "cross record",
    "general-purpose",
    "Off-the-shelf",
    "off-the-shelf",
    "AI-generated",
    "multi-variable",
    "entity-relationship",
    "re-prompts",
    "re-invoke",
    "re-prompt",
    "per-organization",
    "prepay",
    "postpay",
]

SKIP_VALUE_RE = [
    re.compile(r"^\d{4}-\d{2}-\d{2}T"),  # ISO timestamps
    re.compile(r"^[a-f0-9]{64}$", re.I),  # sha256
]

# provider/model-version slugs (OpenRouter, etc.)
MODEL_SLUG_RE = re.compile(
    r"\b(?:anthropic|google|openai|meta)/[a-z0-9][a-z0-9._-]*\b", re.I
)


def _should_skip_value(key: str, value: str) -> bool:
    if key in {"model", "patent_sha256", "context_sha256", "started_at_utc", "finished_at_utc"}:
        return True
    return any(p.match(value) for p in SKIP_VALUE_RE)


def dehyphenate_text(text: str) -> str:
    if not text or _should_skip_value("", text):
        return text

    protected: list[str] = []

    def _protect_model(m: re.Match[str]) -> str:
        protected.append(m.group(0))
        return f"__MODELSLUG_{len(protected) - 1}__"

    text = MODEL_SLUG_RE.sub(_protect_model, text)

    # Markdown list markers (executive summary)
    text = re.sub(r"(?m)^- ", "* ", text)

    # Section headers in embedded markdown
    if text.startswith("### "):
        text = text.replace("\u2014", ": ").replace(" — ", ": ")
    else:
        text = text.replace("\u2014", ", ")
    text = text.replace("\u2013", " to ")

    text = re.sub(r"\bFigs\.\s*(\d+)\s*-\s*(\d+)\b", r"Figs. \1 to \2", text)
    text = re.sub(r"\bFIG\.\s*(\d+)\s*-\s*(\d+)\b", r"FIG. \1 to \2", text)
    text = re.sub(r"\((FIG\.\s*\d+)\s*-\s*(\d+)\)", r"(\1 to \2)", text)
    text = re.sub(r"(\d{2,})-(\d)", r"\1 to \2", text)

    for old in COMPOUNDS:
        if "-" in old:
            text = text.replace(old, old.replace("-", " "))

    if "legal.case.analyze" not in text:
        text = re.sub(r"(?<=[a-zA-Z])-(?=[a-zA-Z])", " ", text)

    text = re.sub(r" : ", ": ", text)

    for i, slug in enumerate(protected):
        text = text.replace(f"__MODELSLUG_{i}__", slug)

    return text


def dehyphenate_obj(obj, key: str = "") -> object:
    if isinstance(obj, str):
        if _should_skip_value(key, obj):
            return obj
        return dehyphenate_text(obj)
    if isinstance(obj, list):
        return [dehyphenate_obj(v, key) for v in obj]
    if isinstance(obj, dict):
        return {k: dehyphenate_obj(v, k) for k, v in obj.items()}
    return obj
