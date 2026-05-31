from __future__ import annotations

from typing import List

import pytest

from medrecs_pipeline.phase_4.atomic_pass3 import (
    AtomicPass3Config,
    assert_pass3_shape,
    atomic_pass3_decompose,
    build_atomic_groups_corpus,
)
from medrecs_pipeline.phase_4.code_detect import is_code_like
from medrecs_pipeline.phase_4.schemas import ExtractedUnit, SemanticGroup, SemanticGroupsCorpus
from medrecs_pipeline.phase_4.table_split import split_table_by_rows, validate_table_rows
from medrecs_pipeline.phase_4.token_utils import count_tokens


def _unit(
    unit_id: str,
    text: str,
    *,
    is_table: bool = False,
    page_no: int = 1,
) -> ExtractedUnit:
    return ExtractedUnit(
        unit_id=unit_id,
        doc_id="doc_test",
        page_no=page_no,
        block_idx=0,
        bbox=(0.0, 0.0, 1.0, 1.0),
        text=text,
        is_table=is_table,
    )


def _semantic(
    semantic_id: str,
    unit_ids: List[str],
    text: str,
    *,
    contains_table: bool = False,
) -> SemanticGroup:
    return SemanticGroup(
        semantic_id=semantic_id,
        parent_group_id="sg_test",
        doc_id="doc_test",
        section_path=["Test"],
        page_start=1,
        page_end=1,
        unit_ids=unit_ids,
        text=text,
        unit_count=len(unit_ids),
        char_count=len(text),
        token_count=count_tokens(text),
        contains_table=contains_table,
    )


def test_mixed_header_caption_table_splits_into_two_atomic_groups() -> None:
    header = _unit("u1", "Circular Smooth Pursuit")
    caption = _unit("u2", "Circular Smooth Pursuit gaze plot")
    table = _unit(
        "u3",
        "| Metrics | Right | Left |\n| :--- | :--- | :--- |\n| SP (%) | 91.43 | 88.77 |",
        is_table=True,
    )
    units_map = {u.unit_id: u for u in (header, caption, table)}
    combined = "\n\n".join(u.text for u in (header, caption, table))
    semantic = _semantic(
        "sg_0071_sem_01",
        ["u1", "u2", "u3"],
        combined,
        contains_table=True,
    )

    groups = atomic_pass3_decompose(
        semantic, units_map, config=AtomicPass3Config(max_chunk_tokens=768)
    )

    assert len(groups) == 2
    prose = next(g for g in groups if g.atomic_kind == "prose")
    tbl = next(g for g in groups if g.atomic_kind == "table")
    assert "gaze plot" in prose.text
    assert prose.text.startswith("Circular Smooth Pursuit")
    assert "| Metrics |" in tbl.text
    assert tbl.unit_ids == ["u3"]
    assert tbl.split_method == "table_extract"
    errors = assert_pass3_shape(groups, [semantic])
    assert errors == []


def test_icd_unit_classified_as_code() -> None:
    icd_text = (
        "1. Concussion with loss of consciousness of 30 minutes or less, "
        "initial encounter - S06.0X1A (Primary)\n"
        "2. Lumbar radiculitis - M54.16\n"
        "3. Cervical radiculitis - M54.12\n"
        "4. Myofascial muscle pain - M79.18\n"
        "5. Muscle spasm - M62.838"
    )
    assert is_code_like(icd_text)

    header = _unit("h1", "Assessment:")
    icd = _unit("c1", icd_text)
    plan = _unit("p1", "PLAN:\n- Continue conservative care.")
    units_map = {u.unit_id: u for u in (header, icd, plan)}
    combined = "\n\n".join(u.text for u in (header, icd, plan))
    semantic = _semantic("sg_0060_sem_01", ["h1", "c1", "p1"], combined)

    groups = atomic_pass3_decompose(
        semantic, units_map, config=AtomicPass3Config(max_chunk_tokens=768)
    )

    assert len(groups) == 3
    kinds = [g.atomic_kind for g in groups]
    assert kinds == ["prose", "code", "prose"]
    code = next(g for g in groups if g.atomic_kind == "code")
    assert "M54.16" in code.text
    assert code.split_method == "code_extract"


def test_pure_table_unit_passthrough() -> None:
    table_text = "| Name | Value |\n| :--- | :--- |\n| A | 1 |"
    table = _unit("t1", table_text, is_table=True)
    units_map = {"t1": table}
    semantic = _semantic("sg_pure", ["t1"], table_text, contains_table=True)

    groups = atomic_pass3_decompose(
        semantic, units_map, config=AtomicPass3Config(max_chunk_tokens=768)
    )

    assert len(groups) == 1
    assert groups[0].atomic_kind == "table"
    assert groups[0].split_method == "atomic_passthrough"


def test_oversized_table_row_split_with_repeated_header() -> None:
    header = "| Col | Value |"
    sep = "| :--- | :--- |"
    data_rows = [f"| row{i} | {'word ' * 40}|" for i in range(30)]
    table_text = "\n".join([header, sep, *data_rows])
    assert count_tokens(table_text) > 768

    parts = split_table_by_rows(table_text, max_tokens=200)
    assert len(parts) > 1
    for part in parts:
        assert validate_table_rows(part)
        assert part.startswith("| Col | Value |")
        assert "| :--- | :--- |" in part


def test_build_corpus_document_unit_coverage() -> None:
    u1 = _unit("u1", "Hello prose.")
    u2 = _unit(
        "u2",
        "| A | B |\n| :--- | :--- |\n| 1 | 2 |",
        is_table=True,
    )
    units_map = {u.unit_id: u for u in (u1, u2)}
    combined = f"{u1.text}\n\n{u2.text}"
    semantic = _semantic("sem1", ["u1", "u2"], combined, contains_table=True)
    corpus = SemanticGroupsCorpus(
        doc_id="doc_test",
        total_pages=1,
        groups=[semantic],
    )
    result = build_atomic_groups_corpus(corpus, units_map)
    errors = assert_pass3_shape(result.groups, corpus.groups)
    assert errors == []
    assert len(result.groups) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
