from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence

from .embeddings import OpenRouterEmbeddingClient, cosine_distance
from .schemas import (
    ExtractedUnit,
    SemanticGroup,
    SemanticGroupsCorpus,
    StructuralGroup,
    StructuralGroupsCorpus,
)
from .sentence_split import SentenceSpan, sentence_split
from .token_utils import count_tokens, split_text_by_token_budget


@dataclass(frozen=True)
class SemanticPass2Config:
    embedding_model: str = "baai/bge-m3"
    tau_b: float = 0.35
    min_sentences: int = 3
    target_chunk_tokens: int = 384
    max_chunk_tokens: int = 768
    min_chunk_tokens: int = 64
    embed_batch_size: int = 64
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> SemanticPass2Config:
        return cls(
            embedding_model=os.getenv("OPENROUTER_EMBEDDING_MODEL", "baai/bge-m3"),
            tau_b=float(os.getenv("PHASE4_TAU_B", "0.35")),
            min_sentences=int(os.getenv("PHASE4_MIN_SENTENCES", "3")),
            target_chunk_tokens=int(os.getenv("PHASE4_TARGET_CHUNK_TOKENS", "384")),
            max_chunk_tokens=int(os.getenv("PHASE4_MAX_CHUNK_TOKENS", "768")),
            min_chunk_tokens=int(os.getenv("PHASE4_MIN_CHUNK_TOKENS", "64")),
            embed_batch_size=int(os.getenv("PHASE4_EMBED_BATCH_SIZE", "64")),
            max_retries=int(os.getenv("PHASE4_EMBED_MAX_RETRIES", "3")),
        )


@dataclass
class _Segment:
    text: str
    unit_ids: tuple[str, ...]
    is_atomic: bool


@dataclass
class _SentenceChunk:
    sentences: List[SentenceSpan] = field(default_factory=list)

    def text(self, separator: str = "\n\n") -> str:
        parts = [s.text.strip() for s in self.sentences if s.text.strip()]
        return separator.join(parts)

    def unit_ids(self) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for sent in self.sentences:
            for uid in sent.unit_ids:
                if uid not in seen:
                    seen.add(uid)
                    ordered.append(uid)
        return ordered


def build_segments(
    unit_ids: Sequence[str],
    units_map: Dict[str, ExtractedUnit],
) -> List[_Segment]:
    segments: List[_Segment] = []
    for uid in unit_ids:
        unit = units_map.get(uid)
        if unit is None:
            continue
        text = (unit.text or "").strip()
        if not text:
            continue
        segments.append(
            _Segment(
                text=text,
                unit_ids=(uid,),
                is_atomic=unit.is_table,
            )
        )
    return segments


def build_sentence_spans(segments: List[_Segment]) -> List[SentenceSpan]:
    spans: List[SentenceSpan] = []
    for seg in segments:
        if seg.is_atomic:
            spans.append(SentenceSpan(text=seg.text, unit_ids=seg.unit_ids, atomic=True))
        else:
            for sent in sentence_split(seg.text):
                spans.append(
                    SentenceSpan(text=sent, unit_ids=seg.unit_ids, atomic=False)
                )
    return spans


def find_split_points(
    scores: Sequence[float],
    *,
    tau_b: float,
    min_distance: int,
) -> List[int]:
    """
    Return indices i where a split occurs AFTER sentence i (0-based in score array).
    score[i] compares sentence i and i+1.
    """
    if not scores:
        return []

    n = len(scores)
    candidates: List[tuple[float, int]] = []
    for i, score in enumerate(scores):
        if score <= tau_b:
            continue
        left = max(0, i - min_distance)
        right = min(n - 1, i + min_distance)
        window = scores[left : right + 1]
        if score == max(window):
            candidates.append((score, i))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    chosen: List[int] = []
    for _, idx in candidates:
        if all(abs(idx - c) >= min_distance for c in chosen):
            chosen.append(idx)
    return sorted(chosen)


def _prose_runs(spans: List[SentenceSpan]) -> List[tuple[int, int]]:
    """Inclusive (start, end) indices of consecutive non-atomic prose runs."""
    runs: List[tuple[int, int]] = []
    start: int | None = None
    for i, span in enumerate(spans):
        if span.atomic:
            if start is not None:
                runs.append((start, i - 1))
                start = None
            continue
        if start is None:
            start = i
    if start is not None:
        runs.append((start, len(spans) - 1))
    return runs


def _split_points_for_run(
    spans: List[SentenceSpan],
    run: tuple[int, int],
    embed_fn: Callable[[List[str]], List[List[float]]],
    config: SemanticPass2Config,
) -> List[int]:
    start, end = run
    prose = spans[start : end + 1]
    if len(prose) <= config.min_sentences:
        return []

    texts = [p.text for p in prose]
    vectors = embed_fn(texts)
    scores = [cosine_distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
    local_cuts = find_split_points(
        scores, tau_b=config.tau_b, min_distance=config.min_sentences
    )
    return [start + idx for idx in local_cuts]


def _assemble_by_cuts(spans: List[SentenceSpan], cut_after: set[int]) -> List[_SentenceChunk]:
    if not spans:
        return []

    chunks: List[_SentenceChunk] = []
    current = _SentenceChunk()
    for i, span in enumerate(spans):
        current.sentences.append(span)
        if i in cut_after:
            chunks.append(current)
            current = _SentenceChunk()
    if current.sentences:
        chunks.append(current)
    return chunks


def _merge_small_chunks(
    chunks: List[_SentenceChunk],
    *,
    min_tokens: int,
) -> List[_SentenceChunk]:
    """Merge undersized chunks with adjacent siblings to enforce a token floor."""
    if not chunks or min_tokens <= 0:
        return chunks

    merged: List[_SentenceChunk] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        while count_tokens(current.text()) < min_tokens and i + 1 < len(chunks):
            nxt = chunks[i + 1]
            current = _SentenceChunk(sentences=current.sentences + nxt.sentences)
            i += 1
        merged.append(current)
        i += 1

    if len(merged) >= 2 and count_tokens(merged[-1].text()) < min_tokens:
        tail = merged.pop()
        merged[-1] = _SentenceChunk(sentences=merged[-1].sentences + tail.sentences)

    return merged


def _hard_cut_indices(spans: List[SentenceSpan]) -> set[int]:
    """Force splits after every atomic (table) block."""
    cuts: set[int] = set()
    for i, span in enumerate(spans):
        if span.atomic:
            if i > 0:
                cuts.add(i - 1)
            if i < len(spans) - 1:
                cuts.add(i)
    return cuts


def enforce_max_tokens(
    chunks: List[_SentenceChunk],
    *,
    max_chunk_tokens: int,
) -> tuple[List[_SentenceChunk], bool]:
    """Split any chunk exceeding max_chunk_tokens via token-budget fallback."""
    used_fallback = False
    out: List[_SentenceChunk] = []

    for chunk in chunks:
        text = chunk.text()
        if count_tokens(text) <= max_chunk_tokens:
            out.append(chunk)
            continue

        used_fallback = True
        sub_texts = split_text_by_token_budget(text, max_chunk_tokens)
        if not sub_texts:
            out.append(chunk)
            continue

        unit_ids = chunk.unit_ids()
        for sub in sub_texts:
            out.append(
                _SentenceChunk(
                    sentences=[
                        SentenceSpan(
                            text=sub,
                            unit_ids=tuple(unit_ids),
                            atomic=False,
                        )
                    ]
                )
            )
    return out, used_fallback


def _finalize_semantic_group(
    *,
    semantic_id: str,
    parent: StructuralGroup,
    chunk: _SentenceChunk,
    units_map: Dict[str, ExtractedUnit],
    split_method: str,
    sem_index: int,
) -> SemanticGroup:
    text = chunk.text()
    unit_ids = chunk.unit_ids()
    units = [units_map[uid] for uid in unit_ids if uid in units_map]
    page_nos = [u.page_no for u in units] or [parent.page_start]
    confidences = [u.confidence for u in units]

    return SemanticGroup(
        semantic_id=semantic_id,
        parent_group_id=parent.group_id,
        doc_id=parent.doc_id,
        section_path=list(parent.section_path),
        page_start=min(page_nos),
        page_end=max(page_nos),
        unit_ids=unit_ids,
        text=text,
        unit_count=len(unit_ids),
        char_count=len(text),
        token_count=count_tokens(text),
        contains_table=any(u.is_table for u in units),
        contains_handwriting=any(u.is_handwritten for u in units),
        extraction_confidence_min=min(confidences) if confidences else parent.extraction_confidence_min,
        split_method=split_method,
    )


def _passthrough_group(
    parent: StructuralGroup,
    *,
    sem_index: int,
    units_map: Dict[str, ExtractedUnit],
) -> SemanticGroup:
    chunk = _SentenceChunk(
        sentences=[
            SentenceSpan(text=parent.text, unit_ids=tuple(parent.unit_ids), atomic=False)
        ]
    )
    return _finalize_semantic_group(
        semantic_id=f"{parent.group_id}_sem_{sem_index:02d}",
        parent=parent,
        chunk=chunk,
        units_map=units_map,
        split_method="passthrough",
        sem_index=sem_index,
    )


def semantic_pass2_split(
    parent: StructuralGroup,
    units_map: Dict[str, ExtractedUnit],
    *,
    embed_fn: Callable[[List[str]], List[List[float]]],
    config: SemanticPass2Config,
) -> tuple[List[SemanticGroup], List[str]]:
    warnings: List[str] = []
    text = (parent.text or "").strip()

    if not text:
        warnings.append(f"{parent.group_id}: empty text; skipping")
        return [], warnings

    token_total = count_tokens(text)
    if token_total <= config.target_chunk_tokens or parent.unit_count <= 1:
        return [_passthrough_group(parent, sem_index=1, units_map=units_map)], warnings

    segments = build_segments(parent.unit_ids, units_map)
    if not segments:
        warnings.append(f"{parent.group_id}: no non-empty segments; skipping")
        return [], warnings

    spans = build_sentence_spans(segments)
    if len(spans) <= config.min_sentences:
        return [_passthrough_group(parent, sem_index=1, units_map=units_map)], warnings

    cut_after: set[int] = _hard_cut_indices(spans)
    for run in _prose_runs(spans):
        for idx in _split_points_for_run(spans, run, embed_fn, config):
            cut_after.add(idx)

    raw_chunks = _assemble_by_cuts(spans, cut_after)
    if not raw_chunks:
        return [_passthrough_group(parent, sem_index=1, units_map=units_map)], warnings

    merged_chunks = _merge_small_chunks(
        raw_chunks, min_tokens=config.min_chunk_tokens
    )
    final_chunks, used_fallback = enforce_max_tokens(
        merged_chunks, max_chunk_tokens=config.max_chunk_tokens
    )
    split_method = "token_fallback" if used_fallback else "semantic"
    if len(final_chunks) == 1 and token_total <= config.max_chunk_tokens:
        split_method = "passthrough"

    groups: List[SemanticGroup] = []
    for i, chunk in enumerate(final_chunks, start=1):
        groups.append(
            _finalize_semantic_group(
                semantic_id=f"{parent.group_id}_sem_{i:02d}",
                parent=parent,
                chunk=chunk,
                units_map=units_map,
                split_method=split_method,
                sem_index=i,
            )
        )
    coverage_warnings = _ensure_parent_coverage(groups, parent.unit_ids, parent.group_id)
    warnings.extend(coverage_warnings)
    return groups, warnings


def _ensure_parent_coverage(
    groups: List[SemanticGroup],
    parent_unit_ids: List[str],
    parent_group_id: str,
) -> List[str]:
    """Warn when parent units are missing from all semantic children."""
    if not groups:
        return []

    covered = {uid for g in groups for uid in g.unit_ids}
    expected = set(parent_unit_ids)
    missing = expected - covered
    if not missing:
        return []

    return [
        f"{parent_group_id}: parent units missing from semantic children: "
        f"{sorted(missing)}"
    ]


def build_semantic_groups_corpus(
    structural: StructuralGroupsCorpus,
    units_map: Dict[str, ExtractedUnit],
    *,
    embed_client: OpenRouterEmbeddingClient,
    config: SemanticPass2Config | None = None,
    source_structural_path: str = "",
    source_units_path: str = "",
) -> SemanticGroupsCorpus:
    if config is None:
        config = SemanticPass2Config.from_env()

    embed_fn = embed_client.embed_texts
    all_groups: List[SemanticGroup] = []
    all_warnings: List[str] = []
    parents_split = 0

    for parent in structural.groups:
        children, warnings = semantic_pass2_split(
            parent, units_map, embed_fn=embed_fn, config=config
        )
        all_warnings.extend(warnings)
        if len(children) > 1:
            parents_split += 1
        all_groups.extend(children)

    passthrough_count = sum(1 for g in all_groups if g.split_method == "passthrough")
    token_fallback_count = sum(1 for g in all_groups if g.split_method == "token_fallback")

    return SemanticGroupsCorpus(
        doc_id=structural.doc_id,
        total_pages=structural.total_pages,
        source_structural_groups=source_structural_path,
        source_extracted_units=source_units_path,
        groups=all_groups,
        meta={
            "pass": "semantic_pass2",
            "structural_group_count": len(structural.groups),
            "semantic_group_count": len(all_groups),
            "parents_split": parents_split,
            "passthrough_count": passthrough_count,
            "token_fallback_count": token_fallback_count,
            "embedding_model": config.embedding_model,
            "tau_b": config.tau_b,
            "min_sentences": config.min_sentences,
            "target_chunk_tokens": config.target_chunk_tokens,
            "max_chunk_tokens": config.max_chunk_tokens,
            "min_chunk_tokens": config.min_chunk_tokens,
            "embed_api_calls": embed_client.api_calls,
            "warnings": all_warnings,
        },
    )


def summarize_semantic_groups(groups: List[SemanticGroup]) -> dict:
    if not groups:
        return {
            "group_count": 0,
            "total_units": 0,
            "total_tokens": 0,
            "largest_group_tokens": 0,
        }
    return {
        "group_count": len(groups),
        "total_units": sum(g.unit_count for g in groups),
        "total_tokens": sum(g.token_count for g in groups),
        "largest_group_tokens": max(g.token_count for g in groups),
        "largest_group_chars": max(g.char_count for g in groups),
        "groups_with_tables": sum(1 for g in groups if g.contains_table),
        "multi_page_groups": sum(1 for g in groups if g.page_end > g.page_start),
        "passthrough": sum(1 for g in groups if g.split_method == "passthrough"),
        "semantic": sum(1 for g in groups if g.split_method == "semantic"),
        "token_fallback": sum(1 for g in groups if g.split_method == "token_fallback"),
        "empty_unit_id_groups": sum(
            1 for g in groups if (g.text or "").strip() and not g.unit_ids
        ),
        "micro_chunk_count": sum(1 for g in groups if g.token_count < 32),
        "groups_below_min_tokens": sum(
            1 for g in groups if 0 < g.token_count < 64
        ),
    }


def assert_pass2_shape(
    semantic_groups: List[SemanticGroup],
    structural_groups: List[StructuralGroup],
) -> List[str]:
    errors: List[str] = []
    structural_by_id = {g.group_id: g for g in structural_groups}

    if not semantic_groups and structural_groups:
        errors.append("structural groups present but no semantic groups produced")

    seen_semantic_ids: set[str] = set()
    for sg in semantic_groups:
        if sg.semantic_id in seen_semantic_ids:
            errors.append(f"duplicate semantic_id: {sg.semantic_id}")
        seen_semantic_ids.add(sg.semantic_id)

        if sg.parent_group_id not in structural_by_id:
            errors.append(f"{sg.semantic_id}: unknown parent {sg.parent_group_id}")
            continue
        if not sg.section_path:
            errors.append(f"{sg.semantic_id}: empty section_path")
        if sg.page_start > sg.page_end:
            errors.append(f"{sg.semantic_id}: page_start > page_end")
        if sg.unit_count != len(sg.unit_ids):
            errors.append(f"{sg.semantic_id}: unit_count != len(unit_ids)")
        if (sg.text or "").strip() and not sg.unit_ids:
            errors.append(f"{sg.semantic_id}: non-empty text but empty unit_ids")

    for parent in structural_groups:
        parent_ids = list(parent.unit_ids)
        if not (parent.text or "").strip():
            continue

        child_ids: List[str] = []
        for sg in semantic_groups:
            if sg.parent_group_id == parent.group_id:
                child_ids.extend(sg.unit_ids)

        if set(child_ids) != set(parent_ids):
            errors.append(
                f"{parent.group_id}: unit coverage mismatch "
                f"expected={sorted(set(parent_ids))} got={sorted(set(child_ids))}"
            )

    return errors
