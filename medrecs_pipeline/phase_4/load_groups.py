from __future__ import annotations

import json
from pathlib import Path

from .schemas import StructuralGroupsCorpus


def load_structural_groups(path: Path) -> StructuralGroupsCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return StructuralGroupsCorpus.model_validate(raw)


def discover_structural_groups_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"structural_groups folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_structural_groups.json"))
    if not files:
        raise FileNotFoundError(f"No *_structural_groups.json in {input_dir}")
    return files


def resolve_extracted_units_path(
    structural: StructuralGroupsCorpus,
    *,
    fallback_dir: Path | None = None,
) -> Path:
    """
    Resolve Phase-2 extracted_units JSON from Pass-1 source path or fallback dir.
    """
    if structural.source_extracted_units:
        src = Path(structural.source_extracted_units)
        if src.exists():
            return src

    if fallback_dir is not None:
        candidate = fallback_dir / f"{structural.doc_id}_extracted_units.json"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Cannot resolve extracted_units for doc_id={structural.doc_id!r}; "
        f"source_extracted_units={structural.source_extracted_units!r}"
    )
