from __future__ import annotations

import logging
import os
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from medrecs_pipeline.phase_4.code_detect import _LAB_PANEL_HEADER
from medrecs_pipeline.phase_4.schemas import Chunk, ChunksCorpus

from .gemini_tagger import extract_tags_with_gemini
from .rule_tagger import tag_code_chunk
from .schemas import TaggedChunk, TaggedChunksCorpus
from .span_utils import SpanRepairStats, llm_tags_to_tags, validate_and_repair_tags
from .thresholds import ThresholdConfig, apply_thresholds

logger = logging.getLogger(__name__)

_HEADER_ONLY = re.compile(r"^[\w\s]+:\s*$", re.MULTILINE)


@dataclass
class Pass5Config:
    concurrency: int = 10
    skip_tiny_headers: bool = False
    retry_failed: bool = True
    retry_concurrency: int = 2
    log_every: int = 20
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig.from_env)

    @classmethod
    def from_env(cls) -> "Pass5Config":
        return cls(
            concurrency=int(os.getenv("PHASE5_CONCURRENCY", "10")),
            skip_tiny_headers=os.getenv("PHASE5_SKIP_TINY_HEADERS", "false").lower()
            in {"1", "true", "yes"},
            retry_failed=os.getenv("PHASE5_RETRY_FAILED", "true").lower()
            not in {"0", "false", "no"},
            retry_concurrency=int(os.getenv("PHASE5_RETRY_CONCURRENCY", "2")),
            log_every=int(os.getenv("PHASE5_LOG_EVERY", "20")),
            thresholds=ThresholdConfig.from_env(),
        )


@dataclass
class Pass5Stats:
    gemini_calls: int = 0
    rules_chunks: int = 0
    skipped_chunks: int = 0
    span_repairs: int = 0
    span_dropped: int = 0
    llm_rows_dropped: int = 0
    invalid_class_dropped: int = 0
    api_failures: int = 0
    parse_fallbacks: int = 0
    retries_succeeded: int = 0
    total_clinical: int = 0
    total_legal: int = 0
    total_uncertain: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ChunkFailure:
    chunk_id: str
    section_path: str
    token_count: int
    error: str


def is_nav_toc_table(body_text: str) -> bool:
    lowered = body_text.lower()
    return "page(s)" in lowered and "total pages" in lowered


def is_clinical_table(body_text: str) -> bool:
    if _LAB_PANEL_HEADER.search(body_text):
        return True
    pipe_lines = [ln for ln in body_text.splitlines() if ln.strip().startswith("|")]
    if len(pipe_lines) >= 3:
        header_joined = " ".join(pipe_lines[0].lower().split())
        if any(k in header_joined for k in ("value", "result", "reference", "range")):
            return True
    return False


def should_skip_chunk(chunk: Chunk, config: Pass5Config) -> bool:
    if chunk.atomic_kind == "table" and is_nav_toc_table(chunk.body_text):
        return True
    if config.skip_tiny_headers and chunk.token_count < 8:
        stripped = chunk.body_text.strip()
        if _HEADER_ONLY.fullmatch(stripped):
            return True
    return False


def route_tagging_method(chunk: Chunk) -> str:
    if chunk.atomic_kind == "code":
        return "rules"
    if chunk.atomic_kind == "table":
        if is_nav_toc_table(chunk.body_text):
            return "skipped"
        return "gemini"
    return "gemini"


def _chunk_to_tagged(
    chunk: Chunk,
    *,
    clinical: List,
    legal: List,
    uncertain: List,
    tagging_method: str,
) -> TaggedChunk:
    data = chunk.model_dump()
    data.update(
        {
            "clinical_tags": clinical,
            "legal_tags": legal,
            "uncertain_tags": uncertain,
            "tagging_method": tagging_method,
        }
    )
    return TaggedChunk.model_validate(data)


def _log_chunk_failure(chunk: Chunk, exc: Exception) -> ChunkFailure:
    section = " / ".join(chunk.section_path) if chunk.section_path else "UNSPECIFIED"
    err = f"{type(exc).__name__}: {exc}"
    logger.error(
        "[pass5] GEMINI FAIL chunk_id=%s section=%r tokens=%d kind=%s err=%s",
        chunk.chunk_id,
        section,
        chunk.token_count,
        chunk.atomic_kind,
        err,
    )
    logger.debug("[pass5] traceback chunk_id=%s\n%s", chunk.chunk_id, traceback.format_exc())
    return ChunkFailure(
        chunk_id=chunk.chunk_id,
        section_path=section,
        token_count=chunk.token_count,
        error=err,
    )


def _process_rules_chunk(chunk: Chunk, config: Pass5Config) -> Tuple[TaggedChunk, Pass5Stats]:
    raw_tags = tag_code_chunk(chunk.body_text)
    repaired, span_stats = validate_and_repair_tags(raw_tags, chunk.body_text)
    clinical, legal, uncertain, dropped = apply_thresholds(
        repaired, [], config=config.thresholds
    )
    delta = Pass5Stats(
        rules_chunks=1,
        span_repairs=span_stats.repaired,
        span_dropped=span_stats.dropped,
        invalid_class_dropped=dropped,
        total_clinical=len(clinical),
        total_legal=len(legal),
        total_uncertain=len(uncertain),
    )
    return (
        _chunk_to_tagged(
            chunk,
            clinical=clinical,
            legal=legal,
            uncertain=uncertain,
            tagging_method="rules",
        ),
        delta,
    )


def _process_skipped_chunk(chunk: Chunk) -> Tuple[TaggedChunk, Pass5Stats]:
    return (
        _chunk_to_tagged(
            chunk,
            clinical=[],
            legal=[],
            uncertain=[],
            tagging_method="skipped",
        ),
        Pass5Stats(skipped_chunks=1),
    )


def _process_gemini_chunk(chunk: Chunk, config: Pass5Config) -> Tuple[TaggedChunk, Pass5Stats]:
    extraction, usage = extract_tags_with_gemini(chunk)
    clinical_raw, span_c = llm_tags_to_tags(extraction.clinical_tags, chunk.body_text)
    legal_raw, span_l = llm_tags_to_tags(extraction.legal_tags, chunk.body_text)
    clinical, legal, uncertain, dropped = apply_thresholds(
        clinical_raw, legal_raw, config=config.thresholds
    )
    parse_mode = usage.get("parse_mode", "structured")
    delta = Pass5Stats(
        gemini_calls=1,
        span_repairs=span_c.repaired + span_l.repaired,
        span_dropped=span_c.dropped + span_l.dropped,
        llm_rows_dropped=span_c.llm_rows_dropped + span_l.llm_rows_dropped,
        invalid_class_dropped=dropped,
        total_clinical=len(clinical),
        total_legal=len(legal),
        total_uncertain=len(uncertain),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("candidates_tokens") or 0),
        parse_fallbacks=1 if parse_mode != "structured" else 0,
    )
    logger.debug(
        "[pass5] chunk_id=%s parse=%s clinical=%d legal=%d uncertain=%d",
        chunk.chunk_id,
        parse_mode,
        len(clinical),
        len(legal),
        len(uncertain),
    )
    return (
        _chunk_to_tagged(
            chunk,
            clinical=clinical,
            legal=legal,
            uncertain=uncertain,
            tagging_method="gemini",
        ),
        delta,
    )


def _merge_stats(total: Pass5Stats, delta: Pass5Stats) -> None:
    for field_name in total.__dataclass_fields__:
        setattr(total, field_name, getattr(total, field_name) + getattr(delta, field_name))


def _is_gemini_failure(tagged: TaggedChunk) -> bool:
    return (
        tagged.tagging_method == "gemini"
        and not tagged.clinical_tags
        and not tagged.legal_tags
        and not tagged.uncertain_tags
    )


def tag_one_chunk(chunk: Chunk, config: Pass5Config) -> Tuple[TaggedChunk, Pass5Stats]:
    method = route_tagging_method(chunk)
    if should_skip_chunk(chunk, config) and method != "rules":
        return _process_skipped_chunk(chunk)
    if method == "rules":
        return _process_rules_chunk(chunk, config)
    if method == "skipped":
        return _process_skipped_chunk(chunk)
    try:
        return _process_gemini_chunk(chunk, config)
    except Exception as exc:
        _log_chunk_failure(chunk, exc)
        tagged = _chunk_to_tagged(
            chunk,
            clinical=[],
            legal=[],
            uncertain=[],
            tagging_method="gemini",
        )
        return tagged, Pass5Stats(gemini_calls=1, api_failures=1)


def _run_gemini_batch(
    chunks: List[Chunk],
    indices: List[int],
    config: Pass5Config,
    *,
    label: str,
) -> Tuple[Dict[int, TaggedChunk], Pass5Stats, List[ChunkFailure]]:
    stats = Pass5Stats()
    results: Dict[int, TaggedChunk] = {}
    failures: List[ChunkFailure] = []
    if not indices:
        return results, stats, failures

    workers = max(1, min(config.concurrency, len(indices)))
    completed = 0
    total = len(indices)
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_process_gemini_chunk, chunks[i], config): i for i in indices
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            chunk = chunks[idx]
            try:
                tagged, delta = fut.result()
            except Exception as exc:
                failure = _log_chunk_failure(chunk, exc)
                failures.append(failure)
                tagged = _chunk_to_tagged(
                    chunk,
                    clinical=[],
                    legal=[],
                    uncertain=[],
                    tagging_method="gemini",
                )
                delta = Pass5Stats(gemini_calls=1, api_failures=1)
            results[idx] = tagged
            _merge_stats(stats, delta)
            completed += 1
            if completed == 1 or completed % config.log_every == 0 or completed == total:
                elapsed = time.perf_counter() - started
                logger.info(
                    "[pass5] %s progress %d/%d (%.1fs) failures=%d",
                    label,
                    completed,
                    total,
                    elapsed,
                    stats.api_failures,
                )

    return results, stats, failures


def tag_corpus(
    corpus: ChunksCorpus,
    *,
    config: Pass5Config | None = None,
    source_chunks_path: str = "",
) -> Tuple[TaggedChunksCorpus, Pass5Stats]:
    cfg = config or Pass5Config.from_env()
    stats = Pass5Stats()
    chunks = corpus.groups
    all_failures: List[ChunkFailure] = []

    gemini_indices: List[int] = []
    results: Dict[int, TaggedChunk] = {}

    for i, chunk in enumerate(chunks):
        method = route_tagging_method(chunk)
        if should_skip_chunk(chunk, cfg) and method != "rules":
            tagged, delta = _process_skipped_chunk(chunk)
            results[i] = tagged
            _merge_stats(stats, delta)
        elif method == "rules":
            tagged, delta = _process_rules_chunk(chunk, cfg)
            results[i] = tagged
            _merge_stats(stats, delta)
        elif method == "skipped":
            tagged, delta = _process_skipped_chunk(chunk)
            results[i] = tagged
            _merge_stats(stats, delta)
        else:
            gemini_indices.append(i)

    logger.info(
        "[pass5] doc_id=%s gemini_queue=%d rules/skip already done=%d concurrency=%d",
        corpus.doc_id,
        len(gemini_indices),
        len(results),
        cfg.concurrency,
    )

    batch_results, batch_stats, batch_failures = _run_gemini_batch(
        chunks, gemini_indices, cfg, label="gemini"
    )
    results.update(batch_results)
    _merge_stats(stats, batch_stats)
    all_failures.extend(batch_failures)

    if cfg.retry_failed:
        retry_indices = [
            i
            for i in gemini_indices
            if i in results and _is_gemini_failure(results[i])
        ]
        if retry_indices:
            logger.warning(
                "[pass5] retrying %d empty/failed gemini chunk(s) at concurrency=%d",
                len(retry_indices),
                cfg.retry_concurrency,
            )
            retry_cfg = Pass5Config(
                concurrency=cfg.retry_concurrency,
                skip_tiny_headers=cfg.skip_tiny_headers,
                retry_failed=False,
                retry_concurrency=cfg.retry_concurrency,
                log_every=cfg.log_every,
                thresholds=cfg.thresholds,
            )
            time.sleep(2)
            retry_results, retry_stats, retry_failures = _run_gemini_batch(
                chunks, retry_indices, retry_cfg, label="gemini-retry"
            )
            for idx, tagged in retry_results.items():
                prev = results.get(idx)
                if prev and _is_gemini_failure(prev) and not _is_gemini_failure(tagged):
                    stats.retries_succeeded += 1
                    logger.info(
                        "[pass5] retry OK chunk_id=%s clinical=%d legal=%d",
                        tagged.chunk_id,
                        len(tagged.clinical_tags),
                        len(tagged.legal_tags),
                    )
                results[idx] = tagged
            _merge_stats(stats, retry_stats)
            all_failures.extend(retry_failures)

    tagged_groups = [results[i] for i in range(len(chunks))]
    out = TaggedChunksCorpus(
        doc_id=corpus.doc_id,
        total_pages=corpus.total_pages,
        source_chunks=source_chunks_path,
        groups=tagged_groups,
        meta={
            "pass": "dual_domain_tagging",
            "tagging_backend": "gemini_v1",
            "chunk_count": len(tagged_groups),
            "gemini_calls": stats.gemini_calls,
            "rules_chunks": stats.rules_chunks,
            "skipped_chunks": stats.skipped_chunks,
            "api_failures": stats.api_failures,
            "parse_fallbacks": stats.parse_fallbacks,
            "retries_succeeded": stats.retries_succeeded,
            "failure_samples": [f.__dict__ for f in all_failures[:10]],
            "tau_clinical": cfg.thresholds.tau_clinical,
            "tau_legal": cfg.thresholds.tau_legal,
            "tau_uncertain_low": cfg.thresholds.tau_uncertain_low,
            "total_clinical_tags": stats.total_clinical,
            "total_legal_tags": stats.total_legal,
            "total_uncertain_tags": stats.total_uncertain,
            "span_repairs": stats.span_repairs,
            "span_dropped": stats.span_dropped,
            "llm_rows_dropped": stats.llm_rows_dropped,
            "invalid_class_dropped": stats.invalid_class_dropped,
            "prompt_tokens": stats.prompt_tokens,
            "output_tokens": stats.output_tokens,
        },
    )
    if stats.api_failures:
        logger.error(
            "[pass5] finished with api_failures=%d (see meta.failure_samples)",
            stats.api_failures,
        )
    return out, stats


def assert_pass5_shape(
    input_corpus: ChunksCorpus,
    output_corpus: TaggedChunksCorpus,
) -> List[str]:
    errors: List[str] = []
    if len(input_corpus.groups) != len(output_corpus.groups):
        errors.append(
            f"chunk count mismatch: input={len(input_corpus.groups)} "
            f"output={len(output_corpus.groups)}"
        )
        return errors

    for i, (src, dst) in enumerate(zip(input_corpus.groups, output_corpus.groups)):
        if src.chunk_id != dst.chunk_id:
            errors.append(
                f"chunk_id mismatch at index {i}: {src.chunk_id!r} vs {dst.chunk_id!r}"
            )
        body_len = len(dst.body_text)
        for bucket_name in ("clinical_tags", "legal_tags", "uncertain_tags"):
            for tag in getattr(dst, bucket_name):
                if tag.start < 0 or tag.end > body_len or tag.start >= tag.end:
                    errors.append(
                        f"invalid span in {bucket_name} chunk {dst.chunk_id}: "
                        f"[{tag.start},{tag.end}) len={body_len}"
                    )
                if not (0.0 <= tag.confidence <= 1.0):
                    errors.append(
                        f"invalid confidence in {bucket_name} chunk {dst.chunk_id}: "
                        f"{tag.confidence}"
                    )
    return errors


def summarize_tagged(groups: List[TaggedChunk]) -> dict:
    return {
        "chunk_count": len(groups),
        "clinical_tags": sum(len(g.clinical_tags) for g in groups),
        "legal_tags": sum(len(g.legal_tags) for g in groups),
        "uncertain_tags": sum(len(g.uncertain_tags) for g in groups),
        "gemini": sum(1 for g in groups if g.tagging_method == "gemini"),
        "rules": sum(1 for g in groups if g.tagging_method == "rules"),
        "skipped": sum(1 for g in groups if g.tagging_method == "skipped"),
    }
