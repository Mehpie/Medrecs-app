from __future__ import annotations

import json
from pathlib import Path

from .schemas import SemanticGroupsCorpus


def load_semantic_groups(path: Path) -> SemanticGroupsCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SemanticGroupsCorpus.model_validate(raw)


def discover_semantic_groups_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"semantic_groups folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_semantic_groups.json"))
    if not files:
        raise FileNotFoundError(f"No *_semantic_groups.json in {input_dir}")
    return files


def resolve_extracted_units_path_from_semantic(
    semantic: SemanticGroupsCorpus,
    *,
    fallback_dir: Path | None = None,
) -> Path:
    """Resolve Phase-2 extracted_units JSON from Pass-2 source path or fallback dir."""
    if semantic.source_extracted_units:
        src = Path(semantic.source_extracted_units)
        if src.exists():
            return src

    if fallback_dir is not None:
        candidate = fallback_dir / f"{semantic.doc_id}_extracted_units.json"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Cannot resolve extracted_units for doc_id={semantic.doc_id!r}; "
        f"source_extracted_units={semantic.source_extracted_units!r}"
    )
