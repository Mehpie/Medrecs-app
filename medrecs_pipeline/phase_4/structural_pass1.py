from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .schemas import ExtractedUnit, StructuralGroup, StructuralGroupsCorpus


def section_path_key(path: List[str]) -> tuple[str, ...]:
    """Hashable key for comparing section_path lists."""
    return tuple(path)


def _join_unit_texts(units: List[ExtractedUnit], separator: str = "\n\n") -> str:
    parts = [u.text.strip() for u in units if (u.text or "").strip()]
    return separator.join(parts)


@dataclass
class _GroupBuilder:
    doc_id: str
    section_path: List[str]
    units: List[ExtractedUnit] = field(default_factory=list)

    def add(self, unit: ExtractedUnit) -> None:
        self.units.append(unit)

    def finalize(self, group_index: int) -> StructuralGroup:
        page_nos = [u.page_no for u in self.units]
        confidences = [u.confidence for u in self.units]
        text = _join_unit_texts(self.units)
        return StructuralGroup(
            group_id=f"sg_{group_index:04d}",
            doc_id=self.doc_id,
            section_path=list(self.section_path),
            page_start=min(page_nos),
            page_end=max(page_nos),
            unit_ids=[u.unit_id for u in self.units],
            text=text,
            unit_count=len(self.units),
            char_count=len(text),
            contains_table=any(u.is_table for u in self.units),
            contains_handwriting=any(u.is_handwritten for u in self.units),
            extraction_confidence_min=min(confidences) if confidences else 1.0,
        )


def structural_pass1_group(
    units: List[ExtractedUnit],
    *,
    doc_id: str,
) -> List[StructuralGroup]:
    """
    Stage-4 Pass 1: group consecutive units with the same section_path (same document).

    Units must already be sorted by (page_no, block_idx).
    """
    if not units:
        return []

    groups: List[StructuralGroup] = []
    current: _GroupBuilder | None = None
    group_index = 0

    for unit in units:
        if unit.doc_id != doc_id:
            raise ValueError(
                f"unit {unit.unit_id} has doc_id={unit.doc_id}, expected {doc_id}"
            )

        if current is None:
            current = _GroupBuilder(doc_id=doc_id, section_path=list(unit.section_path))
            current.add(unit)
            continue

        if section_path_key(unit.section_path) == section_path_key(current.section_path):
            current.add(unit)
        else:
            group_index += 1
            groups.append(current.finalize(group_index))
            current = _GroupBuilder(doc_id=doc_id, section_path=list(unit.section_path))
            current.add(unit)

    if current is not None:
        group_index += 1
        groups.append(current.finalize(group_index))

    return groups


def build_structural_groups_corpus(
    corpus_units: list[ExtractedUnit],
    *,
    doc_id: str,
    total_pages: int,
    source_path: str = "",
) -> StructuralGroupsCorpus:
    sorted_units = sorted(corpus_units, key=lambda u: (u.page_no, u.block_idx))
    groups = structural_pass1_group(sorted_units, doc_id=doc_id)

    path_counts: dict[tuple[str, ...], int] = {}
    for g in groups:
        key = section_path_key(g.section_path)
        path_counts[key] = path_counts.get(key, 0) + 1

    return StructuralGroupsCorpus(
        doc_id=doc_id,
        total_pages=total_pages,
        source_extracted_units=source_path,
        groups=groups,
        meta={
            "pass": "structural_pass1",
            "unit_count": len(sorted_units),
            "group_count": len(groups),
            "unique_section_paths": len(path_counts),
        },
    )


def summarize_groups(groups: List[StructuralGroup]) -> dict:
    if not groups:
        return {
            "group_count": 0,
            "total_units": 0,
            "total_chars": 0,
            "largest_group_units": 0,
            "largest_group_chars": 0,
        }
    return {
        "group_count": len(groups),
        "total_units": sum(g.unit_count for g in groups),
        "total_chars": sum(g.char_count for g in groups),
        "largest_group_units": max(g.unit_count for g in groups),
        "largest_group_chars": max(g.char_count for g in groups),
        "groups_with_tables": sum(1 for g in groups if g.contains_table),
        "multi_page_groups": sum(1 for g in groups if g.page_end > g.page_start),
    }


def assert_pass1_shape(groups: List[StructuralGroup], units: List[ExtractedUnit]) -> List[str]:
    errors: List[str] = []
    if not groups and units:
        errors.append("units present but no groups produced")
        return errors

    covered = []
    for g in groups:
        if g.unit_count != len(g.unit_ids):
            errors.append(f"{g.group_id}: unit_count != len(unit_ids)")
        if g.page_start > g.page_end:
            errors.append(f"{g.group_id}: page_start > page_end")
        if not g.section_path:
            errors.append(f"{g.group_id}: empty section_path")
        covered.extend(g.unit_ids)

    if len(covered) != len(units):
        errors.append(f"unit coverage mismatch: covered={len(covered)} total={len(units)}")

    if len(covered) != len(set(covered)):
        errors.append("duplicate unit_id across groups")

    return errors
