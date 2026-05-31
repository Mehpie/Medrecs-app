#!/usr/bin/env python3
"""
Phase-4 Pass 4: overlap insertion and final chunk assembly.

Reads:  medrecs_pipeline/data/output_phase_4/atomic_groups/*_atomic_groups.json
Writes: medrecs_pipeline/data/output_phase_4/overlapped_groups/*_overlapped_groups.json
        medrecs_pipeline/data/output_phase_4/chunks/*_chunks.json

Run from repo root:
  ./.venv/bin/python -m medrecs_pipeline.phase_4.run_pass4
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from dotenv import load_dotenv

from .build_chunks import build_chunks_corpus, summarize_chunks
from .load_atomic_groups import discover_atomic_groups_files, load_atomic_groups
from .overlap_pass4 import (
    OverlapPass4Config,
    assert_pass4_shape,
    build_overlapped_corpus,
    summarize_overlapped_groups,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_corpus(atomic_path: Path, *, output_root: Path) -> None:
    started = time.perf_counter()
    print(f"\n[pass4] input: {atomic_path.name}", flush=True)

    atomic = load_atomic_groups(atomic_path)
    print(
        f"[pass4] doc_id={atomic.doc_id} | atomic_groups={len(atomic.groups)}",
        flush=True,
    )

    config = OverlapPass4Config.from_env()
    overlapped = build_overlapped_corpus(
        atomic, config=config, source_atomic_path=str(atomic_path)
    )

    errors = assert_pass4_shape(overlapped.groups, atomic.groups, config=config)
    if errors:
        raise RuntimeError(
            "Pass-4 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    overlapped_path = (
        output_root / "overlapped_groups" / f"{atomic.doc_id}_overlapped_groups.json"
    )
    _write_json(overlapped_path, overlapped.model_dump(mode="json"))

    chunks = build_chunks_corpus(
        overlapped, source_overlapped_path=str(overlapped_path)
    )
    chunks_path = output_root / "chunks" / f"{atomic.doc_id}_chunks.json"
    _write_json(chunks_path, chunks.model_dump(mode="json"))

    ostats = summarize_overlapped_groups(overlapped.groups)
    cstats = summarize_chunks(chunks.groups)
    elapsed = time.perf_counter() - started

    print(
        f"[pass4] overlapped={ostats['group_count']} | "
        f"with_prefix={ostats.get('groups_with_prefix', 0)} | "
        f"overlap_tokens={config.overlap_tokens}",
        flush=True,
    )
    print(
        f"[pass4] chunks={cstats['chunk_count']} | "
        f"largest_tokens={cstats.get('largest_chunk_tokens', 0)} | "
        f"prose={cstats.get('prose', 0)} | table={cstats.get('table', 0)} | "
        f"code={cstats.get('code', 0)}",
        flush=True,
    )
    print(
        f"[pass4] saved → {overlapped_path}\n"
        f"[pass4] saved → {chunks_path} | elapsed_s={elapsed:.2f}",
        flush=True,
    )

    for g in overlapped.groups[:5]:
        path_str = " / ".join(g.section_path)
        preview = (g.text[:80] + "...") if len(g.text) > 80 else g.text.replace("\n", " ")
        print(
            f"  [{g.overlapped_id}] kind={g.atomic_kind} | "
            f"tokens={g.token_count} | prefix_tok={g.overlap_prefix_tokens} | "
            f"path={path_str!r} | preview={preview!r}",
            flush=True,
        )
    if len(overlapped.groups) > 5:
        print(f"  ... and {len(overlapped.groups) - 5} more groups", flush=True)


def main() -> int:
    load_dotenv()
    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_4" / "atomic_groups"
    output_dir = pipeline_root / "data" / "output_phase_4"

    files = discover_atomic_groups_files(input_dir)
    print(
        f"Phase-4 Pass-4 start | {len(files)} atomic corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'overlapped_groups'}, {output_dir / 'chunks'}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir)

    print("\nPhase-4 Pass-4 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
