#!/usr/bin/env python3
"""
Phase-5.1: legal-only augmentation on Phase 5 tagged chunks.

Reads:  medrecs_pipeline/data/output_phase_5/tagged_chunks/*_tagged_chunks.json
Writes: medrecs_pipeline/data/output_phase_5_1/tagged_chunks/*_tagged_chunks.json

Run from repo root:
  ./.venv/bin/python -m medrecs_pipeline.phase_5_1.run_pass5_1
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .legal_pass51 import Pass51Config, assert_pass51_shape, augment_corpus, summarize_legal
from .load_tagged_chunks import discover_tagged_chunks_files, load_tagged_chunks

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level_name = os.getenv("PHASE5_1_LOG_LEVEL", os.getenv("PHASE5_LOG_LEVEL", "INFO")).upper()
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


def run_one_corpus(input_path: Path, *, output_root: Path, config: Pass51Config) -> None:
    started = time.perf_counter()
    print(f"\n[pass51] input: {input_path.name}", flush=True)

    corpus = load_tagged_chunks(input_path)
    before = summarize_legal(corpus.groups)
    print(
        f"[pass51] doc_id={corpus.doc_id} | chunks={before['chunk_count']} | "
        f"legal={before['legal_tags']} | with_legal={before['chunks_with_legal']}",
        flush=True,
    )

    augmented, stats = augment_corpus(
        corpus, config=config, source_tagged_path=str(input_path)
    )

    errors = assert_pass51_shape(corpus, augmented)
    if errors:
        raise RuntimeError(
            "Pass-5.1 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    out_path = output_root / "tagged_chunks" / f"{corpus.doc_id}_tagged_chunks.json"
    _write_json(out_path, augmented.model_dump(mode="json"))

    after = summarize_legal(augmented.groups)
    elapsed = time.perf_counter() - started

    print(
        f"[pass51] routed={stats.chunks_routed} | gemini_calls={stats.gemini_calls} | "
        f"rule_hits={stats.rule_hits} | api_failures={stats.api_failures} | "
        f"retries_ok={stats.retries_succeeded}",
        flush=True,
    )
    print(
        f"[pass51] legal before={before['legal_tags']} after={after['legal_tags']} | "
        f"chunks_with_legal {before['chunks_with_legal']}→{after['chunks_with_legal']} | "
        f"pi_gap {stats.pi_gap_before}→{stats.pi_gap_after}",
        flush=True,
    )
    print(
        f"[pass51] clinical unchanged={before['clinical_tags']} | "
        f"saved → {out_path} | elapsed_s={elapsed:.2f}",
        flush=True,
    )


def main() -> int:
    load_dotenv()
    _configure_logging()

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_5" / "tagged_chunks"
    output_dir = pipeline_root / "data" / "output_phase_5_1"
    config = Pass51Config.from_env()

    files = discover_tagged_chunks_files(input_dir)
    print(
        f"Phase-5.1 start | {len(files)} tagged corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'tagged_chunks'}\n"
        f"  concurrency={config.concurrency} rules={config.enable_rules}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir, config=config)

    print("\nPhase-5.1 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
