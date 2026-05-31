from __future__ import annotations

import json
from pathlib import Path

from medrecs_pipeline.phase_4.schemas import ChunksCorpus


def load_chunks(path: Path) -> ChunksCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ChunksCorpus.model_validate(raw)


def discover_chunks_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"chunks folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_chunks.json"))
    if not files:
        raise FileNotFoundError(f"No *_chunks.json in {input_dir}")
    return files
