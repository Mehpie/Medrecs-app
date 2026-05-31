from __future__ import annotations

import json
from pathlib import Path

from medrecs_pipeline.phase_5.schemas import TaggedChunksCorpus


def load_tagged_chunks(path: Path) -> TaggedChunksCorpus:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TaggedChunksCorpus.model_validate(raw)


def discover_tagged_chunks_files(input_dir: Path) -> list[Path]:
    input_dir = Path(input_dir)
    if not input_dir.exists():
        raise FileNotFoundError(f"tagged_chunks folder not found: {input_dir}")
    files = sorted(input_dir.glob("*_tagged_chunks.json"))
    if not files:
        raise FileNotFoundError(f"No *_tagged_chunks.json in {input_dir}")
    return files
