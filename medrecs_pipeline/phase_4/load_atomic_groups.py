from __future__ import annotations

import json
from pathlib import Path

from .schemas import AtomicGroupsCorpus


def load_atomic_groups(path: Path) -> AtomicGroupsCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AtomicGroupsCorpus.model_validate(raw)


def discover_atomic_groups_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"atomic_groups folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_atomic_groups.json"))
    if not files:
        raise FileNotFoundError(f"No *_atomic_groups.json in {input_dir}")
    return files
