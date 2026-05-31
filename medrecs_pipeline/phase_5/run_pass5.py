#!/usr/bin/env python3
"""
Phase-5 Pass 5: dual-domain entity tagging via Gemini + rule tagger.

Reads:  medrecs_pipeline/data/output_phase_4/chunks/*_chunks.json
Writes: medrecs_pipeline/data/output_phase_5/tagged_chunks/*_tagged_chunks.json

Run from repo root:
  ./.venv/bin/python -m medrecs_pipeline.phase_5.run_pass5
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .load_chunks import discover_chunks_files, load_chunks
from .tag_pass5 import (
    Pass5Config,
    assert_pass5_shape,
    summarize_tagged,
    tag_corpus,
)

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level_name = __import__("os").getenv("PHASE5_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_corpus(chunks_path: Path, *, output_root: Path, config: Pass5Config) -> None:
    started = time.perf_counter()
    print(f"\n[pass5] input: {chunks_path.name}", flush=True)

    corpus = load_chunks(chunks_path)
    print(
        f"[pass5] doc_id={corpus.doc_id} | chunks={len(corpus.groups)}",
        flush=True,
    )

    tagged, stats = tag_corpus(
        corpus, config=config, source_chunks_path=str(chunks_path)
    )

    errors = assert_pass5_shape(corpus, tagged)
    if errors:
        raise RuntimeError(
            "Pass-5 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    out_path = output_root / "tagged_chunks" / f"{corpus.doc_id}_tagged_chunks.json"
    _write_json(out_path, tagged.model_dump(mode="json"))

    summary = summarize_tagged(tagged.groups)
    elapsed = time.perf_counter() - started

    print(
        f"[pass5] gemini_calls={stats.gemini_calls} | rules={stats.rules_chunks} | "
        f"skipped={stats.skipped_chunks} | api_failures={stats.api_failures} | "
        f"parse_fallbacks={stats.parse_fallbacks} | retries_ok={stats.retries_succeeded}",
        flush=True,
    )
    print(
        f"[pass5] tags clinical={summary['clinical_tags']} | "
        f"legal={summary['legal_tags']} | uncertain={summary['uncertain_tags']}",
        flush=True,
    )
    print(
        f"[pass5] saved → {out_path} | elapsed_s={elapsed:.2f}",
        flush=True,
    )

    for g in tagged.groups[:5]:
        path_str = " / ".join(g.section_path)
        n_c = len(g.clinical_tags)
        n_l = len(g.legal_tags)
        preview = (g.body_text[:60] + "...") if len(g.body_text) > 60 else g.body_text
        preview = preview.replace("\n", " ")
        print(
            f"  [{g.chunk_id[:8]}…] method={g.tagging_method} | "
            f"c={n_c} l={n_l} | path={path_str!r} | {preview!r}",
            flush=True,
        )
    if len(tagged.groups) > 5:
        print(f"  ... and {len(tagged.groups) - 5} more chunks", flush=True)


def main() -> int:
    load_dotenv()
    _configure_logging()
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_4" / "chunks"
    output_dir = pipeline_root / "data" / "output_phase_5"
    config = Pass5Config.from_env()

    files = discover_chunks_files(input_dir)
    print(
        f"Phase-5 Pass-5 start | {len(files)} chunk corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'tagged_chunks'}\n"
        f"  concurrency={config.concurrency}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir, config=config)

    print("\nPhase-5 Pass-5 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
