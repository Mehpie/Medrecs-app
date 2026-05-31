#!/usr/bin/env python3
"""Smoke test for 04_patent_review.ipynb (OpenRouter, LIMIT_ITEMS=2)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "04_patent_review.ipynb"
NOTEBOOKS = ROOT / "notebooks"


def main() -> int:
    nb = json.loads(NB.read_text())
    chunks: list[str] = [
        "from __future__ import annotations\n",
        f"import os\nos.chdir({str(NOTEBOOKS)!r})\n",
    ]

    stop_markers = (
        "PATENT REVIEW COMPLETE",
        "Wrote ",
        "smoke test complete",
    )
    skip_ids = {"7adc1678"}  # empty trailing cell

    t0 = time.time()
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        cid = cell.get("id", "")
        if cid in skip_ids:
            continue
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        lines = [ln for ln in src.split("\n") if not ln.strip().startswith("from __future__ import")]
        chunks.append(f"\n# --- cell {i} id={cid} ---\n" + "\n".join(lines) + "\n")

    code = "\n".join(chunks)
    code_path = ROOT / "data" / "outputs" / "_smoke_test_exec.py"
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text(code, encoding="utf-8")

    print(f"Executing smoke pipeline ({len(code):,} chars compiled)…")
    print(f"  Notebook: {NB}")
    print(f"  LIMIT_ITEMS should be 2 in Cell 3\n")

    g = {"__name__": "__main__", "__file__": str(code_path)}
    try:
        exec(compile(code, str(code_path), "exec"), g)  # noqa: S102
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc!r}")
        import traceback

        traceback.print_exc()
        return 1

    elapsed = time.time() - t0
    stats = g.get("call_stats", lambda: {})()
    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)
    print(f"Elapsed:        {elapsed:.1f}s")
    print(f"API calls:      {stats.get('calls', '?')}")
    print(f"Input tokens:   {stats.get('approx_input_tokens', '?')}")
    print(f"Output tokens:  {stats.get('approx_output_tokens', '?')}")
    print(f"Model:          {g.get('MODEL', '?')}")

    out = ROOT / "data" / "outputs"
    for name in ("patent_review_report.md", "patent_review.json", "rewritten_patent_application.txt"):
        p = out / name
        print(f"  {name}: {'OK' if p.exists() else 'MISSING'} ({p.stat().st_size if p.exists() else 0:,} bytes)")

    if stats.get("calls", 0) < 1:
        print("\nWARN: zero API calls recorded")
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
