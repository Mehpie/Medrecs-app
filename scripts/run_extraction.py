#!/usr/bin/env python3
"""Re-run PDF extraction (cells: config, schemas, functions, check, extract, save)."""
import json
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "extractjson.ipynb"
CELL_INDICES = [1, 2, 3, 4, 5, 6]


def main() -> int:
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(
        nb,
        timeout=900,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT / "notebooks")}},
    )
    with client.setup_kernel():
        for idx in CELL_INDICES:
            print(f"Executing cell {idx}...", flush=True)
            client.execute_cell(nb.cells[idx], idx)
    out_path = ROOT / "data" / "outputs" / "structured_document.json"
    if not out_path.exists():
        print("ERROR: structured_document.json not written", file=sys.stderr)
        return 1
    data = json.loads(out_path.read_text(encoding="utf-8"))
    print(
        f"Done: {len(data['elements'])} elements, "
        f"{data['total_pages']} pages → {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
