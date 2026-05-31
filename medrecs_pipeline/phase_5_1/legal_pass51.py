from __future__ import annotations

import logging
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from medrecs_pipeline.phase_5.schemas import TaggedChunk, TaggedChunksCorpus
from medrecs_pipeline.phase_5.span_utils import llm_tags_to_tags
from medrecs_pipeline.phase_5.thresholds import ThresholdConfig

from .legal_gemini_tagger import extract_legal_with_gemini
from .legal_router import LegalRouterConfig, has_pi_phrase, should_route_legal
from .legal_rule_tagger import tag_legal_phrases
from .merge_legal import assert_clinical_unchanged, merge_legal_into_chunk

logger = logging.getLogger(__name__)


@dataclass
class Pass51Config:
    concurrency: int = 8
    enable_rules: bool = True
    retry_failed: bool = True
    retry_concurrency: int = 2
    log_every: int = 15
    router: LegalRouterConfig = field(default_factory=LegalRouterConfig.from_env)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig.from_env)

    @classmethod
    def from_env(cls) -> "Pass51Config":
        return cls(
            concurrency=int(os.getenv("PHASE5_1_CONCURRENCY", "8")),
            enable_rules=os.getenv("PHASE5_1_ENABLE_RULES", "true").lower()
            not in {"0", "false", "no"},
            retry_failed=os.getenv("PHASE5_1_RETRY_FAILED", "true").lower()
            not in {"0", "false", "no"},
            retry_concurrency=int(os.getenv("PHASE5_1_RETRY_CONCURRENCY", "2")),
            log_every=int(os.getenv("PHASE5_1_LOG_EVERY", "15")),
            router=LegalRouterConfig.from_env(),
            thresholds=ThresholdConfig.from_env(),
        )


@dataclass
class Pass51Stats:
    chunks_routed: int = 0
    gemini_calls: int = 0
    rule_hits: int = 0
    legal_added: int = 0
    parse_fallbacks: int = 0
    api_failures: int = 0
    retries_succeeded: int = 0
    invalid_class_dropped: int = 0
    pi_gap_before: int = 0
    pi_gap_after: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ChunkFailure:
    chunk_id: str
    section_path: str
    token_count: int
    error: str


def _log_failure(chunk: TaggedChunk, exc: Exception) -> ChunkFailure:
    section = " / ".join(chunk.section_path) if chunk.section_path else "UNSPECIFIED"
    err = f"{type(exc).__name__}: {exc}"
    logger.error(
        "[pass51] GEMINI FAIL chunk_id=%s section=%r tokens=%d err=%s",
        chunk.chunk_id,
        section,
        chunk.token_count,
        err,
    )
    logger.debug("[pass51] traceback chunk_id=%s\n%s", chunk.chunk_id, traceback.format_exc())
    return ChunkFailure(
        chunk_id=chunk.chunk_id,
        section_path=section,
        token_count=chunk.token_count,
        error=err,
    )


def _process_one(
    chunk: TaggedChunk,
    config: Pass51Config,
    *,
    gemini_tags: List | None = None,
) -> Tuple[TaggedChunk, Pass51Stats]:
    stats = Pass51Stats(chunks_routed=1)
    rule_tags = tag_legal_phrases(chunk.body_text) if config.enable_rules else []
    stats.rule_hits = len(rule_tags)

    if gemini_tags is None:
        try:
            extraction, usage = extract_legal_with_gemini(chunk)
            gemini_parsed, span_stats = llm_tags_to_tags(
                extraction.legal_tags, chunk.body_text
            )
            stats.gemini_calls = 1
            stats.prompt_tokens = int(usage.get("prompt_tokens") or 0)
            stats.output_tokens = int(usage.get("candidates_tokens") or 0)
            if usage.get("parse_mode") != "structured":
                stats.parse_fallbacks = 1
        except Exception as exc:
            _log_failure(chunk, exc)
            stats.api_failures = 1
            gemini_parsed = []
    else:
        gemini_parsed = gemini_tags

    updated, added, dropped = merge_legal_into_chunk(
        chunk,
        rule_tags=rule_tags,
        gemini_tags=gemini_parsed,
        config=config.thresholds,
    )
    stats.legal_added = added
    stats.invalid_class_dropped = dropped

    if not assert_clinical_unchanged(chunk, updated):
        raise RuntimeError(f"clinical_tags mutated for chunk {chunk.chunk_id}")

    return updated, stats


def _is_legal_failure(chunk: TaggedChunk, config: Pass51Config) -> bool:
    return should_route_legal(chunk, config.router) and not chunk.legal_tags


def _run_gemini_batch(
    chunks: List[TaggedChunk],
    indices: List[int],
    config: Pass51Config,
    *,
    label: str,
) -> Tuple[Dict[int, TaggedChunk], Pass51Stats, List[ChunkFailure]]:
    stats = Pass51Stats()
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
            pool.submit(_process_one, chunks[i], config): i for i in indices
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                tagged, delta = fut.result()
            except Exception as exc:
                failure = _log_failure(chunks[idx], exc)
                failures.append(failure)
                tagged = chunks[idx]
                delta = Pass51Stats(chunks_routed=1, api_failures=1)
            results[idx] = tagged
            for field_name in stats.__dataclass_fields__:
                setattr(
                    stats,
                    field_name,
                    getattr(stats, field_name) + getattr(delta, field_name),
                )
            completed += 1
            if completed == 1 or completed % config.log_every == 0 or completed == total:
                elapsed = time.perf_counter() - started
                logger.info(
                    "[pass51] %s progress %d/%d (%.1fs) failures=%d",
                    label,
                    completed,
                    total,
                    elapsed,
                    stats.api_failures,
                )

    return results, stats, failures


def _merge_stats(total: Pass51Stats, delta: Pass51Stats) -> None:
    for field_name in total.__dataclass_fields__:
        setattr(total, field_name, getattr(total, field_name) + getattr(delta, field_name))


def augment_corpus(
    corpus: TaggedChunksCorpus,
    *,
    config: Pass51Config | None = None,
    source_tagged_path: str = "",
) -> Tuple[TaggedChunksCorpus, Pass51Stats]:
    cfg = config or Pass51Config.from_env()
    stats = Pass51Stats()
    chunks = corpus.groups
    all_failures: List[ChunkFailure] = []

    legal_before = sum(len(c.legal_tags) for c in chunks)
    pi_gap_before = sum(
        1 for c in chunks if has_pi_phrase(c.body_text) and not c.legal_tags
    )
    stats.pi_gap_before = pi_gap_before

    routed_indices: List[int] = []
    results: Dict[int, TaggedChunk] = {}

    for i, chunk in enumerate(chunks):
        if should_route_legal(chunk, cfg.router):
            routed_indices.append(i)
        else:
            results[i] = chunk

    logger.info(
        "[pass51] doc_id=%s routed=%d passthrough=%d concurrency=%d",
        corpus.doc_id,
        len(routed_indices),
        len(results),
        cfg.concurrency,
    )

    batch_results, batch_stats, batch_failures = _run_gemini_batch(
        chunks, routed_indices, cfg, label="legal51"
    )
    results.update(batch_results)
    _merge_stats(stats, batch_stats)
    all_failures.extend(batch_failures)

    if cfg.retry_failed:
        retry_indices = [
            i
            for i in routed_indices
            if i in results and _is_legal_failure(results[i], cfg)
        ]
        if retry_indices:
            logger.warning(
                "[pass51] retrying %d empty legal chunk(s) at concurrency=%d",
                len(retry_indices),
                cfg.retry_concurrency,
            )
            time.sleep(2)
            retry_cfg = Pass51Config(
                concurrency=cfg.retry_concurrency,
                enable_rules=cfg.enable_rules,
                retry_failed=False,
                retry_concurrency=cfg.retry_concurrency,
                log_every=cfg.log_every,
                router=cfg.router,
                thresholds=cfg.thresholds,
            )
            retry_results, retry_stats, retry_failures = _run_gemini_batch(
                chunks, retry_indices, retry_cfg, label="legal51-retry"
            )
            for idx, tagged in retry_results.items():
                prev = results.get(idx)
                if prev and _is_legal_failure(prev, cfg) and tagged.legal_tags:
                    stats.retries_succeeded += 1
                    logger.info(
                        "[pass51] retry OK chunk_id=%s legal=%d",
                        tagged.chunk_id,
                        len(tagged.legal_tags),
                    )
                results[idx] = tagged
            _merge_stats(stats, retry_stats)
            all_failures.extend(retry_failures)

    out_groups = [results[i] for i in range(len(chunks))]
    legal_after = sum(len(c.legal_tags) for c in out_groups)
    pi_gap_after = sum(
        1 for c in out_groups if has_pi_phrase(c.body_text) and not c.legal_tags
    )
    stats.pi_gap_after = pi_gap_after
    stats.chunks_routed = len(routed_indices)

    out = TaggedChunksCorpus(
        doc_id=corpus.doc_id,
        total_pages=corpus.total_pages,
        source_chunks=corpus.source_chunks,
        groups=out_groups,
        meta={
            **corpus.meta,
            "legal_pass": "phase_5_1",
            "source_tagged_chunks": source_tagged_path,
            "legal51_chunks_routed": stats.chunks_routed,
            "legal51_gemini_calls": stats.gemini_calls,
            "legal51_rule_hits": stats.rule_hits,
            "legal51_legal_added": stats.legal_added,
            "legal51_api_failures": stats.api_failures,
            "legal51_parse_fallbacks": stats.parse_fallbacks,
            "legal51_retries_succeeded": stats.retries_succeeded,
            "total_legal_tags_before": legal_before,
            "total_legal_tags_after": legal_after,
            "pi_gap_before": pi_gap_before,
            "pi_gap_after": pi_gap_after,
            "failure_samples": [f.__dict__ for f in all_failures[:10]],
            "prompt_tokens": stats.prompt_tokens,
            "output_tokens": stats.output_tokens,
        },
    )

    if stats.api_failures:
        logger.error(
            "[pass51] finished with api_failures=%d (see meta.failure_samples)",
            stats.api_failures,
        )

    return out, stats


def assert_pass51_shape(
    input_corpus: TaggedChunksCorpus,
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
        if not assert_clinical_unchanged(src, dst):
            errors.append(f"clinical_tags changed for chunk {src.chunk_id}")

        body_len = len(dst.body_text)
        for bucket in ("legal_tags", "uncertain_tags"):
            for tag in getattr(dst, bucket):
                if tag.start < 0 or tag.end > body_len or tag.start >= tag.end:
                    errors.append(
                        f"invalid span in {bucket} chunk {dst.chunk_id}: "
                        f"[{tag.start},{tag.end}) len={body_len}"
                    )
    return errors


def summarize_legal(groups: List[TaggedChunk]) -> dict:
    return {
        "chunk_count": len(groups),
        "clinical_tags": sum(len(g.clinical_tags) for g in groups),
        "legal_tags": sum(len(g.legal_tags) for g in groups),
        "uncertain_tags": sum(len(g.uncertain_tags) for g in groups),
        "chunks_with_legal": sum(1 for g in groups if g.legal_tags),
    }
