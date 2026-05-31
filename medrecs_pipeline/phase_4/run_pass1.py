#!/usr/bin/env python3
"""
Phase-4 Pass 1: structural grouping of Phase-2 extracted units by section_path.

Reads:  medrecs_pipeline/data/output_phase_2/extracted_units/*_extracted_units.json
Writes: medrecs_pipeline/data/output_phase_4/structural_groups/*_structural_groups.json

Run from repo root:
  python3 -m medrecs_pipeline.phase_4.run_pass1
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .load_units import discover_extracted_units_files, load_extracted_units
from .load_units import sort_units_reading_order
from .structural_pass1 import (
    assert_pass1_shape,
    build_structural_groups_corpus,
    summarize_groups,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_one_corpus(extracted_path: Path, *, output_root: Path) -> None:
    started = time.perf_counter()
    print(f"\n[pass1] input: {extracted_path.name}", flush=True)

    corpus = load_extracted_units(extracted_path)
    units = sort_units_reading_order(corpus.units)
    print(
        f"[pass1] doc_id={corpus.doc_id} | units={len(units)} | pages={corpus.total_pages}",
        flush=True,
    )

    result = build_structural_groups_corpus(
        units,
        doc_id=corpus.doc_id,
        total_pages=corpus.total_pages,
        source_path=str(extracted_path),
    )

    errors = assert_pass1_shape(result.groups, units)
    if errors:
        raise RuntimeError(
            "Pass-1 validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    out_path = output_root / "structural_groups" / f"{corpus.doc_id}_structural_groups.json"
    _write_json(out_path, result.model_dump(mode="json"))

    stats = summarize_groups(result.groups)
    elapsed = time.perf_counter() - started
    print(f"[pass1] groups={stats['group_count']} | unique_section_paths={result.meta.get('unique_section_paths')}", flush=True)
    print(
        f"[pass1] largest_group: units={stats['largest_group_units']} chars={stats['largest_group_chars']}",
        flush=True,
    )
    print(
        f"[pass1] multi_page_groups={stats['multi_page_groups']} | tables_in_groups={stats['groups_with_tables']}",
        flush=True,
    )
    print(f"[pass1] saved → {out_path} | elapsed_s={elapsed:.2f}", flush=True)

    # Log first few groups for quick sanity check
    for g in result.groups[:5]:
        path_str = " / ".join(g.section_path)
        preview = (g.text[:80] + "...") if len(g.text) > 80 else g.text.replace("\n", " ")
        print(
            f"  [{g.group_id}] pages {g.page_start}-{g.page_end} | "
            f"units={g.unit_count} | path={path_str!r} | preview={preview!r}",
            flush=True,
        )
    if len(result.groups) > 5:
        print(f"  ... and {len(result.groups) - 5} more groups", flush=True)


def main() -> int:
    pipeline_root = Path(__file__).resolve().parent.parent
    input_dir = pipeline_root / "data" / "output_phase_2" / "extracted_units"
    output_dir = pipeline_root / "data" / "output_phase_4"

    files = discover_extracted_units_files(input_dir)
    print(
        f"Phase-4 Pass-1 start | {len(files)} corpus file(s)\n"
        f"  input:  {input_dir}\n"
        f"  output: {output_dir / 'structural_groups'}",
        flush=True,
    )

    for path in files:
        run_one_corpus(path, output_root=output_dir)

    print("\nPhase-4 Pass-1 complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
