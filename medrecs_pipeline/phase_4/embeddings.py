from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List

from langchain_openai import OpenAIEmbeddings


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class EmbeddingClientConfig:
    model: str = "baai/bge-m3"
    batch_size: int = 64
    max_retries: int = 3
    base_url: str = "https://openrouter.ai/api/v1"

    @classmethod
    def from_env(cls) -> EmbeddingClientConfig:
        return cls(
            model=os.getenv("OPENROUTER_EMBEDDING_MODEL", "baai/bge-m3"),
            batch_size=int(os.getenv("PHASE4_EMBED_BATCH_SIZE", "64")),
            max_retries=int(os.getenv("PHASE4_EMBED_MAX_RETRIES", "3")),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )


class OpenRouterEmbeddingClient:
    """Batch embedder via OpenRouter OpenAI-compatible /embeddings API."""

    def __init__(self, config: EmbeddingClientConfig | None = None) -> None:
        if config is None:
            config = EmbeddingClientConfig.from_env()
        self.config = config
        self.api_calls = 0
        self._llm = OpenAIEmbeddings(
            model=config.model,
            api_key=_require_env("OPENROUTER_API_KEY"),
            base_url=config.base_url,
            tiktoken_enabled=False,
            check_embedding_ctx_length=False,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://localhost"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "medrecs-pipeline"),
            },
        )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        out: List[List[float]] = []
        batch_size = max(1, self.config.batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors = self._embed_batch_with_retry(batch)
            out.extend(vectors)
        return out

    def _embed_batch_with_retry(self, batch: List[str]) -> List[List[float]]:
        last_err: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                self.api_calls += 1
                return self._llm.embed_documents(batch)
            except Exception as exc:  # pragma: no cover - network
                last_err = exc
                if attempt < self.config.max_retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(
            f"Embedding batch failed after {self.config.max_retries} attempt(s)"
        ) from last_err


def cosine_distance(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))
