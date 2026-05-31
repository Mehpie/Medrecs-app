from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Literal, Sequence

from .code_detect import is_code_like
from .schemas import (
    AtomicGroup,
    AtomicGroupsCorpus,
    ExtractedUnit,
    SemanticGroup,
    SemanticGroupsCorpus,
)
from .table_split import split_table_by_rows, validate_table_rows
from .token_utils import count_tokens

UnitKind = Literal["prose", "table", "code"]


@dataclass(frozen=True)
class AtomicPass3Config:
    max_chunk_tokens: int = 768

    @classmethod
    def from_env(cls) -> AtomicPass3Config:
        return cls(
            max_chunk_tokens=int(os.getenv("PHASE4_MAX_CHUNK_TOKENS", "768")),
        )


def classify_unit(unit: ExtractedUnit) -> UnitKind:
    if unit.is_table:
        return "table"
    if is_code_like(unit.text):
        return "code"
    return "prose"


def _join_unit_texts(units: Sequence[ExtractedUnit]) -> str:
    parts = [(u.text or "").strip() for u in units if (u.text or "").strip()]
    return "\n\n".join(parts)


def _group_had_kind(units: Sequence[ExtractedUnit], kind: UnitKind) -> bool:
    return any(classify_unit(u) == kind for u in units)


def _prose_split_method(units: Sequence[ExtractedUnit]) -> str:
    if _group_had_kind(units, "table"):
        return "table_extract"
    if _group_had_kind(units, "code"):
        return "code_extract"
    return "atomic_passthrough"


def _build_atomic_group(
    *,
    semantic: SemanticGroup,
    atomic_id: str,
    units: Sequence[ExtractedUnit],
    atomic_kind: UnitKind,
    split_method: str,
    text: str,
) -> AtomicGroup:
    unit_ids = [u.unit_id for u in units]
    page_nos = [u.page_no for u in units] or [semantic.page_start]
    confidences = [u.confidence for u in units]

    return AtomicGroup(
        atomic_id=atomic_id,
        source_semantic_id=semantic.semantic_id,
        semantic_id=semantic.semantic_id,
        parent_group_id=semantic.parent_group_id,
        doc_id=semantic.doc_id,
        section_path=list(semantic.section_path),
        page_start=min(page_nos),
        page_end=max(page_nos),
        unit_ids=unit_ids,
        text=text,
        unit_count=len(unit_ids),
        char_count=len(text),
        token_count=count_tokens(text),
        contains_table=atomic_kind == "table",
        contains_handwriting=any(u.is_handwritten for u in units),
        extraction_confidence_min=(
            min(confidences) if confidences else semantic.extraction_confidence_min
        ),
        split_method=split_method,
        atomic_kind=atomic_kind,
    )


def _emit_table_chunks(
    semantic: SemanticGroup,
    unit: ExtractedUnit,
    *,
    config: AtomicPass3Config,
    all_units: Sequence[ExtractedUnit],
    index: int,
) -> tuple[List[AtomicGroup], int]:
    text = (unit.text or "").strip()
    if not text:
        return [], index

    sub_texts = split_table_by_rows(text, max_tokens=config.max_chunk_tokens)
    row_split = len(sub_texts) > 1
    method = "table_row_split" if row_split else "table_extract"
    if len(all_units) == 1 and classify_unit(unit) == "table":
        method = "atomic_passthrough" if not row_split else "table_row_split"

    groups: List[AtomicGroup] = []
    for part in sub_texts:
        index += 1
        groups.append(
            _build_atomic_group(
                semantic=semantic,
                atomic_id=f"{semantic.semantic_id}_atom_{index:02d}",
                units=[unit],
                atomic_kind="table",
                split_method=method,
                text=part,
            )
        )
    return groups, index


def atomic_pass3_decompose(
    semantic: SemanticGroup,
    units_map: Dict[str, ExtractedUnit],
    *,
    config: AtomicPass3Config,
) -> List[AtomicGroup]:
    units = [units_map[uid] for uid in semantic.unit_ids if uid in units_map]
    if not units:
        return []

    kinds = {classify_unit(u) for u in units}
    single_kind = len(kinds) == 1

    if single_kind and kinds.pop() == "prose" and not _group_had_kind(units, "code"):
        text = _join_unit_texts(units)
        if not text.strip():
            return []
        return [
            _build_atomic_group(
                semantic=semantic,
                atomic_id=f"{semantic.semantic_id}_atom_01",
                units=units,
                atomic_kind="prose",
                split_method="atomic_passthrough",
                text=text,
            )
        ]

    if single_kind and len(units) == 1:
        unit = units[0]
        kind = classify_unit(unit)
        if kind == "table":
            groups, _ = _emit_table_chunks(
                semantic, unit, config=config, all_units=units, index=0
            )
            return groups
        if kind == "code":
            text = (unit.text or "").strip()
            return [
                _build_atomic_group(
                    semantic=semantic,
                    atomic_id=f"{semantic.semantic_id}_atom_01",
                    units=[unit],
                    atomic_kind="code",
                    split_method="atomic_passthrough",
                    text=text,
                )
            ]

    out: List[AtomicGroup] = []
    prose_buffer: List[ExtractedUnit] = []
    index = 0

    def flush_prose() -> None:
        nonlocal index
        if not prose_buffer:
            return
        text = _join_unit_texts(prose_buffer)
        if not text.strip():
            prose_buffer.clear()
            return
        index += 1
        out.append(
            _build_atomic_group(
                semantic=semantic,
                atomic_id=f"{semantic.semantic_id}_atom_{index:02d}",
                units=list(prose_buffer),
                atomic_kind="prose",
                split_method=_prose_split_method(units),
                text=text,
            )
        )
        prose_buffer.clear()

    for unit in units:
        kind = classify_unit(unit)
        if kind == "prose":
            prose_buffer.append(unit)
            continue
        flush_prose()
        if kind == "table":
            table_groups, index = _emit_table_chunks(
                semantic, unit, config=config, all_units=units, index=index
            )
            out.extend(table_groups)
        elif kind == "code":
            text = (unit.text or "").strip()
            if text:
                index += 1
                out.append(
                    _build_atomic_group(
                        semantic=semantic,
                        atomic_id=f"{semantic.semantic_id}_atom_{index:02d}",
                        units=[unit],
                        atomic_kind="code",
                        split_method="code_extract",
                        text=text,
                    )
                )

    flush_prose()
    return out


def build_atomic_groups_corpus(
    semantic_corpus: SemanticGroupsCorpus,
    units_map: Dict[str, ExtractedUnit],
    *,
    config: AtomicPass3Config | None = None,
    source_semantic_path: str = "",
    source_units_path: str = "",
) -> AtomicGroupsCorpus:
    if config is None:
        config = AtomicPass3Config.from_env()

    all_groups: List[AtomicGroup] = []
    mixed_split = 0

    for semantic in semantic_corpus.groups:
        children = atomic_pass3_decompose(semantic, units_map, config=config)
        if len(children) > 1:
            mixed_split += 1
        all_groups.extend(children)

    passthrough = sum(1 for g in all_groups if g.split_method == "atomic_passthrough")
    table_extract = sum(1 for g in all_groups if g.split_method == "table_extract")
    code_extract = sum(1 for g in all_groups if g.split_method == "code_extract")
    table_row_split = sum(1 for g in all_groups if g.split_method == "table_row_split")

    return AtomicGroupsCorpus(
        doc_id=semantic_corpus.doc_id,
        total_pages=semantic_corpus.total_pages,
        source_semantic_groups=source_semantic_path,
        source_extracted_units=source_units_path,
        groups=all_groups,
        meta={
            "pass": "atomic_pass3",
            "semantic_group_count": len(semantic_corpus.groups),
            "atomic_group_count": len(all_groups),
            "mixed_groups_split": mixed_split,
            "passthrough_count": passthrough,
            "table_extract_count": table_extract,
            "code_extract_count": code_extract,
            "table_row_split_count": table_row_split,
            "max_chunk_tokens": config.max_chunk_tokens,
        },
    )


def summarize_atomic_groups(groups: List[AtomicGroup]) -> dict:
    if not groups:
        return {"group_count": 0, "total_tokens": 0, "largest_group_tokens": 0}
    return {
        "group_count": len(groups),
        "total_tokens": sum(g.token_count for g in groups),
        "largest_group_tokens": max(g.token_count for g in groups),
        "prose": sum(1 for g in groups if g.atomic_kind == "prose"),
        "table": sum(1 for g in groups if g.atomic_kind == "table"),
        "code": sum(1 for g in groups if g.atomic_kind == "code"),
        "passthrough": sum(1 for g in groups if g.split_method == "atomic_passthrough"),
        "table_extract": sum(1 for g in groups if g.split_method == "table_extract"),
        "code_extract": sum(1 for g in groups if g.split_method == "code_extract"),
        "table_row_split": sum(1 for g in groups if g.split_method == "table_row_split"),
        "broken_table_groups": sum(
            1 for g in groups if g.atomic_kind == "table" and not validate_table_rows(g.text)
        ),
        "over_token_cap": sum(
            1 for g in groups if g.token_count > 768
        ),
    }


def assert_pass3_shape(
    atomic_groups: List[AtomicGroup],
    semantic_groups: List[SemanticGroup],
    *,
    max_chunk_tokens: int = 768,
) -> List[str]:
    errors: List[str] = []
    semantic_by_id = {g.semantic_id: g for g in semantic_groups}

    if not atomic_groups and semantic_groups:
        errors.append("semantic groups present but no atomic groups produced")

    seen_atomic: set[str] = set()
    children_by_semantic: dict[str, List[AtomicGroup]] = {}

    for ag in atomic_groups:
        if ag.atomic_id in seen_atomic:
            errors.append(f"duplicate atomic_id: {ag.atomic_id}")
        seen_atomic.add(ag.atomic_id)

        if ag.source_semantic_id not in semantic_by_id:
            errors.append(f"{ag.atomic_id}: unknown source {ag.source_semantic_id}")
        if not ag.section_path:
            errors.append(f"{ag.atomic_id}: empty section_path")
        if ag.page_start > ag.page_end:
            errors.append(f"{ag.atomic_id}: page_start > page_end")
        if ag.unit_count != len(ag.unit_ids):
            errors.append(f"{ag.atomic_id}: unit_count != len(unit_ids)")
        if (ag.text or "").strip() and not ag.unit_ids:
            errors.append(f"{ag.atomic_id}: non-empty text but empty unit_ids")
        if ag.atomic_kind not in ("prose", "table", "code"):
            errors.append(f"{ag.atomic_id}: invalid atomic_kind {ag.atomic_kind!r}")
        if ag.atomic_kind == "table" and not ag.contains_table:
            errors.append(f"{ag.atomic_id}: table kind but contains_table=false")
        if ag.atomic_kind != "table" and ag.contains_table:
            errors.append(f"{ag.atomic_id}: non-table kind but contains_table=true")
        if ag.token_count > max_chunk_tokens:
            errors.append(
                f"{ag.atomic_id}: token_count {ag.token_count} > {max_chunk_tokens}"
            )
        if ag.atomic_kind == "table" and not validate_table_rows(ag.text):
            errors.append(f"{ag.atomic_id}: broken markdown table rows")

        children_by_semantic.setdefault(ag.source_semantic_id, []).append(ag)

    for semantic in semantic_groups:
        if not (semantic.text or "").strip():
            continue
        children = children_by_semantic.get(semantic.semantic_id, [])
        if not children:
            errors.append(f"{semantic.semantic_id}: no atomic children produced")

        child_unit_set: set[str] = set()
        for child in children:
            child_unit_set.update(child.unit_ids)

        if child_unit_set != set(semantic.unit_ids):
            errors.append(
                f"{semantic.semantic_id}: unit coverage mismatch "
                f"expected={sorted(set(semantic.unit_ids))} "
                f"got={sorted(child_unit_set)}"
            )

    all_semantic_units: set[str] = set()
    all_atomic_units: set[str] = set()
    for semantic in semantic_groups:
        if (semantic.text or "").strip():
            all_semantic_units.update(semantic.unit_ids)
    for ag in atomic_groups:
        all_atomic_units.update(ag.unit_ids)

    if all_semantic_units != all_atomic_units:
        errors.append(
            f"document unit coverage mismatch: "
            f"semantic={len(all_semantic_units)} atomic={len(all_atomic_units)}"
        )

    return errors
