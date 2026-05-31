#!/usr/bin/env python3
"""
Phase-4 Pass 2: semantic splitting of Pass-1 structural groups.

Reads:  medrecs_pipeline/data/output_phase_4/structural_groups/*_structural_groups.json
        + linked Phase-2 extracted_units JSON
Writes: medrecs_pipeline/data/output_phase_4/semantic_groups/*_semantic_groups.json

Run from repo root:
  ./.venv/bin/python -m medrecs_pipeline.phase_4.run_pass2
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from dotenv import load_dotenv

from .embeddings import OpenRouterEmbeddingClient
from .load_groups import (
    discover_structural_groups_files,
    load_structural_groups,
    resolve_extracted_units_path,
)
from .load_units import load_extracted_units
from .semantic_pass2 import (
    SemanticPass2Config,
    assert_pass2_shape,
    build_semantic_groups_corpus,
    summarize_semantic_groups,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_corpus(structural_path: Path, *, output_root: Path) -> None:
    started = time.perf_counter()
    print(f"\n[pass2] input: {structural_path.name}", flush=True)

    structural = load_structural_groups(structural_path)
    pipeline_root = Path(__file__).resolve().parent.parent
    units_fallback = pipeline_root / "data" / "output_phase_2" / "extracted_units"
    units_path = resolve_extracted_units_path(structural, fallback_dir=units_fallback)

    units_corpus = load_extracted_units(units_path)
    units_map = {u.unit_id: u for u in units_corpus.units}

    print(
        f"[pass2] doc_id={structural.doc_id} | structural_groups={len(structural.groups)} "
        f"| units={len(units_map)}",
        flush=True,
    )

    config = SemanticPass2Config.from_env()
    embed_client = OpenRouterEmbeddingClient()

    result = build_semantic_groups_corpus(
        structural,
        units_map,
        embed_client=embed_client,
        config=config,
        source_structural_path=str(structural_path),
        source_units_path=str(units_path),
    )

    errors = assert_pass2_shape(result.groups, structural.groups)
    if errors:
        raise RuntimeError(
            "Pass-2 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    out_path = output_root / "semantic_groups" / f"{structural.doc_id}_semantic_groups.json"
    _write_json(out_path, result.model_dump(mode="json"))

    stats = summarize_semantic_groups(result.groups)
    elapsed = time.perf_counter() - started
    print(
        f"[pass2] semantic_groups={stats['group_count']} | "
        f"parents_split={result.meta.get('parents_split')} | "
        f"passthrough={stats.get('passthrough', 0)} | "
        f"token_fallback={stats.get('token_fallback', 0)}",
        flush=True,
    )
    print(
        f"[pass2] largest_tokens={stats['largest_group_tokens']} | "
        f"embed_api_calls={result.meta.get('embed_api_calls')} | "
        f"model={config.embedding_model}",
        flush=True,
    )
    print(
        f"[pass2] empty_unit_ids={stats.get('empty_unit_id_groups', 0)} | "
        f"micro_chunks_lt32={stats.get('micro_chunk_count', 0)} | "
        f"below_min_tokens={stats.get('groups_below_min_tokens', 0)} | "
        f"min_chunk_tokens={config.min_chunk_tokens}",
        flush=True,
    )
    print(f"[pass2] saved → {out_path} | elapsed_s={elapsed:.2f}", flush=True)

    for g in result.groups[:5]:
        path_str = " / ".join(g.section_path)
        preview = (g.text[:80] + "...") if len(g.text) > 80 else g.text.replace("\n", " ")
        print(
            f"  [{g.semantic_id}] parent={g.parent_group_id} | "
            f"tokens={g.token_count} | method={g.split_method} | "
            f"path={path_str!r} | preview={preview!r}",
            flush=True,
        )
    if len(result.groups) > 5:
        print(f"  ... and {len(result.groups) - 5} more groups", flush=True)


def main() -> int:
    load_dotenv()
    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_4" / "structural_groups"
    output_dir = pipeline_root / "data" / "output_phase_4"

    files = discover_structural_groups_files(input_dir)
    print(
        f"Phase-4 Pass-2 start | {len(files)} structural corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'semantic_groups'}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir)

    print("\nPhase-4 Pass-2 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
