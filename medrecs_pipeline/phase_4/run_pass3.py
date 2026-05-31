#!/usr/bin/env python3
"""
Phase-4 Pass 3: atomic structured-data preservation.

Reads:  medrecs_pipeline/data/output_phase_4/semantic_groups/*_semantic_groups.json
        + linked Phase-2 extracted_units JSON
Writes: medrecs_pipeline/data/output_phase_4/atomic_groups/*_atomic_groups.json

Run from repo root:
  ./.venv/bin/python -m medrecs_pipeline.phase_4.run_pass3
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from dotenv import load_dotenv

from .atomic_pass3 import (
    AtomicPass3Config,
    assert_pass3_shape,
    build_atomic_groups_corpus,
    summarize_atomic_groups,
)
from .load_semantic_groups import (
    discover_semantic_groups_files,
    load_semantic_groups,
    resolve_extracted_units_path_from_semantic,
)
from .load_units import load_extracted_units


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_corpus(semantic_path: Path, *, output_root: Path) -> None:
    started = time.perf_counter()
    print(f"\n[pass3] input: {semantic_path.name}", flush=True)

    semantic = load_semantic_groups(semantic_path)
    pipeline_root = Path(__file__).resolve().parent.parent
    units_fallback = pipeline_root / "data" / "output_phase_2" / "extracted_units"
    units_path = resolve_extracted_units_path_from_semantic(
        semantic, fallback_dir=units_fallback
    )

    units_corpus = load_extracted_units(units_path)
    units_map = {u.unit_id: u for u in units_corpus.units}

    print(
        f"[pass3] doc_id={semantic.doc_id} | semantic_groups={len(semantic.groups)} "
        f"| units={len(units_map)}",
        flush=True,
    )

    config = AtomicPass3Config.from_env()
    result = build_atomic_groups_corpus(
        semantic,
        units_map,
        config=config,
        source_semantic_path=str(semantic_path),
        source_units_path=str(units_path),
    )

    errors = assert_pass3_shape(
        result.groups, semantic.groups, max_chunk_tokens=config.max_chunk_tokens
    )
    if errors:
        raise RuntimeError(
            "Pass-3 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    out_path = output_root / "atomic_groups" / f"{semantic.doc_id}_atomic_groups.json"
    _write_json(out_path, result.model_dump(mode="json"))

    stats = summarize_atomic_groups(result.groups)
    elapsed = time.perf_counter() - started
    print(
        f"[pass3] atomic_groups={stats['group_count']} | "
        f"mixed_split={result.meta.get('mixed_groups_split')} | "
        f"passthrough={stats.get('passthrough', 0)} | "
        f"table_extract={stats.get('table_extract', 0)} | "
        f"code_extract={stats.get('code_extract', 0)} | "
        f"table_row_split={stats.get('table_row_split', 0)}",
        flush=True,
    )
    print(
        f"[pass3] prose={stats.get('prose', 0)} | table={stats.get('table', 0)} | "
        f"code={stats.get('code', 0)} | broken_tables={stats.get('broken_table_groups', 0)} | "
        f"largest_tokens={stats.get('largest_group_tokens', 0)}",
        flush=True,
    )
    print(f"[pass3] saved → {out_path} | elapsed_s={elapsed:.2f}", flush=True)

    for g in result.groups[:5]:
        path_str = " / ".join(g.section_path)
        preview = (g.text[:80] + "...") if len(g.text) > 80 else g.text.replace("\n", " ")
        print(
            f"  [{g.atomic_id}] kind={g.atomic_kind} | "
            f"tokens={g.token_count} | method={g.split_method} | "
            f"path={path_str!r} | preview={preview!r}",
            flush=True,
        )
    if len(result.groups) > 5:
        print(f"  ... and {len(result.groups) - 5} more groups", flush=True)


def main() -> int:
    load_dotenv()
    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_4" / "semantic_groups"
    output_dir = pipeline_root / "data" / "output_phase_4"

    files = discover_semantic_groups_files(input_dir)
    print(
        f"Phase-4 Pass-3 start | {len(files)} semantic corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'atomic_groups'}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir)

    print("\nPhase-4 Pass-3 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
