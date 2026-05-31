from __future__ import annotations

import json
from pathlib import Path

from .schemas import ExtractedUnit, ExtractedUnitsCorpus


def load_extracted_units(path: Path) -> ExtractedUnitsCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ExtractedUnitsCorpus.model_validate(raw)


def sort_units_reading_order(units: list[ExtractedUnit]) -> list[ExtractedUnit]:
    return sorted(units, key=lambda u: (u.page_no, u.block_idx))


def discover_extracted_units_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"Phase-2 extracted_units folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_extracted_units.json"))
    if not files:
        raise FileNotFoundError(f"No *_extracted_units.json in {input_dir}")
    return files
