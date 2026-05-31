"""Build structured comparison rows from patent_review.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PARA_ID_RE = re.compile(r"\[(\d{4})\]")


@dataclass(frozen=True)
class ComparisonRow:
    id_label: str
    status: str
    original: str
    rewritten: str
    section_id: str = ""
    section_title: str = ""


def split_by_paragraph_ids(text: str) -> dict[str, str]:
    if not text or not text.strip():
        return {}
    matches = list(PARA_ID_RE.finditer(text))
    if not matches:
        return {"__full__": text.strip()}
    out: dict[str, str] = {}
    for i, match in enumerate(matches):
        pid = f"[{match.group(1)}]"
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[pid] = text[start:end].strip()
    return out


def paragraph_order(section: dict[str, Any]) -> list[str]:
    declared = section.get("paragraph_ids") or []
    original_map = split_by_paragraph_ids(section.get("original_text", ""))
    rewritten_map = split_by_paragraph_ids(section.get("rewritten_text", ""))
    ordered: list[str] = []
    seen: set[str] = set()
    for pid in declared:
        if pid not in seen:
            ordered.append(pid)
            seen.add(pid)
    extra_ids = (set(original_map) | set(rewritten_map)) - seen - {"__full__"}
    extras = sorted(extra_ids, key=lambda x: int(x.strip("[]")))
    ordered.extend(extras)
    if "__full__" in original_map or "__full__" in rewritten_map:
        ordered.append("__full__")
    return ordered


def status_for_text(left: str, right: str) -> str:
    if not left and right:
        return "ADDED"
    if left and not right:
        return "REMOVED"
    if " ".join(left.split()) == " ".join(right.split()):
        return "UNCHANGED"
    return "CHANGED"


def load_comparison_rows(json_path: Path) -> tuple[list[ComparisonRow], list[ComparisonRow]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    per_claim: list[dict[str, Any]] = data.get("per_claim", [])
    per_dd_section: list[dict[str, Any]] = data.get("per_dd_section", [])

    claim_rows: list[ComparisonRow] = []
    for claim in sorted(per_claim, key=lambda c: c["claim_number"]):
        num = claim["claim_number"]
        ctype = claim.get("claim_type", "")
        parent = claim.get("parent_claim")
        parent_note = f" (parent claim {parent})" if parent else ""
        header = f"Claim {num} — {ctype}{parent_note}"
        original = (claim.get("original_text") or "").strip()
        rewritten = (claim.get("rewritten_text") or "").strip()
        claim_rows.append(
            ComparisonRow(
                id_label=header,
                status=status_for_text(original, rewritten),
                original=original,
                rewritten=rewritten,
            )
        )

    section_rows: list[ComparisonRow] = []
    for section in per_dd_section:
        section_id = section.get("section_id", "")
        section_title = section.get("section_title", section_id)
        original_map = split_by_paragraph_ids(section.get("original_text", ""))
        rewritten_map = split_by_paragraph_ids(section.get("rewritten_text", ""))
        order = paragraph_order(section)

        if not order:
            left = (section.get("original_text") or "").strip()
            right = (section.get("rewritten_text") or "").strip()
            section_rows.append(
                ComparisonRow(
                    id_label=section_id,
                    status=status_for_text(left, right),
                    original=left,
                    rewritten=right,
                    section_id=section_id,
                    section_title=section_title,
                )
            )
            continue

        for pid in order:
            if pid == "__full__":
                id_label = f"{section_id} (full section)"
            else:
                id_label = pid
            left = original_map.get(pid, "").strip()
            right = rewritten_map.get(pid, "").strip()
            section_rows.append(
                ComparisonRow(
                    id_label=id_label,
                    status=status_for_text(left, right),
                    original=left,
                    rewritten=right,
                    section_id=section_id,
                    section_title=section_title,
                )
            )

    return claim_rows, section_rows
