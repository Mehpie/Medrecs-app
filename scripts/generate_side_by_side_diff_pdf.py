#!/usr/bin/env python3
"""Generate a structured side-by-side PDF from patent_review.json."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PARA_ID_RE = re.compile(r"\[(\d{4})\]")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\t", "    ")
    )


def _split_by_paragraph_ids(text: str) -> dict[str, str]:
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


def _paragraph_order(section: dict[str, Any]) -> list[str]:
    declared = section.get("paragraph_ids") or []
    original_map = _split_by_paragraph_ids(section.get("original_text", ""))
    rewritten_map = _split_by_paragraph_ids(section.get("rewritten_text", ""))
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


def _status_for_text(left: str, right: str) -> str:
    if not left and right:
        return "ADDED"
    if left and not right:
        return "REMOVED"
    if " ".join(left.split()) == " ".join(right.split()):
        return "UNCHANGED"
    return "CHANGED"


def _inline_diff_html(left: str, right: str) -> tuple[str, str]:
    """Return escaped HTML fragments with highlight tags for each side."""
    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens and not right_tokens:
        return "&nbsp;", "&nbsp;"

    matcher = difflib.SequenceMatcher(None, left_tokens, right_tokens, autojunk=False)
    left_parts: list[str] = []
    right_parts: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            l_chunk = " ".join(left_tokens[i1:i2])
            r_chunk = " ".join(right_tokens[j1:j2])
            if l_chunk:
                left_parts.append(_escape(l_chunk))
            if r_chunk:
                right_parts.append(_escape(r_chunk))
        elif tag == "replace":
            l_chunk = " ".join(left_tokens[i1:i2])
            r_chunk = " ".join(right_tokens[j1:j2])
            if l_chunk:
                left_parts.append(f'<font backColor="#FFD6D6">{_escape(l_chunk)}</font>')
            if r_chunk:
                right_parts.append(f'<font backColor="#C9F2C9">{_escape(r_chunk)}</font>')
        elif tag == "delete":
            l_chunk = " ".join(left_tokens[i1:i2])
            if l_chunk:
                left_parts.append(f'<font backColor="#FFD6D6">{_escape(l_chunk)}</font>')
        elif tag == "insert":
            r_chunk = " ".join(right_tokens[j1:j2])
            if r_chunk:
                right_parts.append(f'<font backColor="#C9F2C9">{_escape(r_chunk)}</font>')

    left_html = " ".join(left_parts) if left_parts else "&nbsp;"
    right_html = " ".join(right_parts) if right_parts else "&nbsp;"
    return left_html, right_html


def _make_styles():
    styles = getSampleStyleSheet()
    return {
        "title": styles["Heading1"],
        "h2": styles["Heading2"],
        "h3": ParagraphStyle(
            "H3",
            parent=styles["Heading3"],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
        ),
    }


def _add_comparison_table(
    story: list,
    rows: list[tuple[str, str, str, str]],
    styles: dict,
    col_widths: tuple[float, float, float, float],
) -> None:
    """rows: (id_label, status, original_html, rewritten_html)"""
    table_data = [
        [
            Paragraph("ID", styles["label"]),
            Paragraph("Status", styles["label"]),
            Paragraph("Original", styles["label"]),
            Paragraph("Rewritten", styles["label"]),
        ]
    ]
    for id_label, status, left_html, right_html in rows:
        table_data.append(
            [
                Paragraph(_escape(id_label), styles["body"]),
                Paragraph(status, styles["body"]),
                Paragraph(left_html, styles["body"]),
                Paragraph(right_html, styles["body"]),
            ]
        )

    table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    tbl_style = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    for row_idx, (_, status, _, _) in enumerate(rows, start=1):
        if status == "UNCHANGED":
            continue
        if status == "CHANGED":
            bg = colors.HexColor("#FFF4CC")
        elif status == "ADDED":
            bg = colors.HexColor("#D9F2D9")
        else:
            bg = colors.HexColor("#FFD9D9")
        tbl_style.add("BACKGROUND", (0, row_idx), (-1, row_idx), bg)

    table.setStyle(tbl_style)
    story.append(table)
    story.append(Spacer(1, 6))


def build_pdf_from_json(json_path: Path, output_pdf: Path) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    per_claim: list[dict[str, Any]] = data.get("per_claim", [])
    per_dd_section: list[dict[str, Any]] = data.get("per_dd_section", [])

    styles = _make_styles()
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=landscape(A4),
        leftMargin=16,
        rightMargin=16,
        topMargin=16,
        bottomMargin=16,
        title="Patent Review Structured Comparison",
    )

    story: list = []
    col_widths = (52, 48, 335, 335)

    # --- Claims ---
    story.append(Paragraph("Part A — Claims (matched by claim number)", styles["h2"]))
    claim_rows: list[tuple[str, str, str, str]] = []
    for claim in sorted(per_claim, key=lambda c: c["claim_number"]):
        num = claim["claim_number"]
        ctype = claim.get("claim_type", "")
        parent = claim.get("parent_claim")
        parent_note = f" (parent claim {parent})" if parent else ""
        label = f"Claim {num}"
        header = f"{label} — {ctype}{parent_note}"

        original = (claim.get("original_text") or "").strip()
        rewritten = (claim.get("rewritten_text") or "").strip()
        status = _status_for_text(original, rewritten)
        left_html, right_html = _inline_diff_html(original, rewritten)
        claim_rows.append((header, status, left_html, right_html))

    _add_comparison_table(story, claim_rows, styles, col_widths)
    story.append(PageBreak())

    # --- DD / spec sections ---
    story.append(Paragraph("Part B — Specification & Detailed Description (matched by paragraph ID)", styles["h2"]))

    for section in per_dd_section:
        section_id = section.get("section_id", "")
        section_title = section.get("section_title", section_id)
        story.append(
            Paragraph(
                f"Section: {section_id} — {_escape(section_title)}",
                styles["h3"],
            )
        )

        original_map = _split_by_paragraph_ids(section.get("original_text", ""))
        rewritten_map = _split_by_paragraph_ids(section.get("rewritten_text", ""))
        order = _paragraph_order(section)

        section_rows: list[tuple[str, str, str, str]] = []
        if not order:
            left = (section.get("original_text") or "").strip()
            right = (section.get("rewritten_text") or "").strip()
            status = _status_for_text(left, right)
            l_html, r_html = _inline_diff_html(left, right)
            section_rows.append((section_id, status, l_html, r_html))
        else:
            for pid in order:
                if pid == "__full__":
                    id_label = f"{section_id} (full section)"
                else:
                    id_label = pid
                left = original_map.get(pid, "").strip()
                right = rewritten_map.get(pid, "").strip()
                status = _status_for_text(left, right)
                l_html, r_html = _inline_diff_html(left, right)
                section_rows.append((id_label, status, l_html, r_html))

        _add_comparison_table(story, section_rows, styles, col_widths)

    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate structured side-by-side diff PDF from patent_review.json"
    )
    parser.add_argument(
        "--json",
        default="data/outputs/patent_review.json",
        help="Path to patent_review.json",
    )
    parser.add_argument(
        "--output",
        default="data/outputs/patent_changes_side_by_side.pdf",
        help="Output PDF path",
    )
    args = parser.parse_args()

    json_path = Path(args.json).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    build_pdf_from_json(json_path, output_path)
    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
