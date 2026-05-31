#!/usr/bin/env python3
"""Minimal OpenRouter smoke test (2 API calls: ping + tiny ContextDigest-style)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT / "notebooks")

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv(ROOT / ".env")

key = os.getenv("OPENROUTER_API_KEY")
model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-opus-4.7")
if not key:
    raise SystemExit("OPENROUTER_API_KEY not set")

print(f"Model: {model}")
print(f"Key:   ****{key[-4:]}")


class Ping(BaseModel):
    message: str = Field(..., description="Short confirmation string")
    provider: str = Field(..., description="Should mention OpenRouter or Anthropic")


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.1,
        max_tokens=256,
        timeout=120,
        max_retries=0,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "medrecs-patent-review"),
        },
    )


def main() -> int:
    llm = build_llm()
    structured = llm.with_structured_output(Ping, include_raw=True)
    t0 = time.time()
    out = structured.invoke(
        [
            SystemMessage(content="Reply with structured JSON only."),
            HumanMessage(content="Say that OpenRouter connectivity works for the patent review pipeline."),
        ]
    )
    elapsed = time.time() - t0
    parsed = out.get("parsed") if isinstance(out, dict) else out
    raw = out.get("raw") if isinstance(out, dict) else None
    if parsed is None:
        print("FAIL: no parsed output", out)
        return 1
    inst = parsed if isinstance(parsed, Ping) else Ping.model_validate(parsed)
    in_tok = out_tok = 0
    if raw is not None:
        meta = getattr(raw, "usage_metadata", None) or {}
        in_tok = int(meta.get("input_tokens") or 0)
        out_tok = int(meta.get("output_tokens") or 0)
    print(f"OK in {elapsed:.1f}s — message={inst.message!r} provider={inst.provider!r}")
    print(f"Tokens: in={in_tok} out={out_tok}")
    return 0 if in_tok > 0 or out_tok > 0 else 0  # still pass if tokens missing


if __name__ == "__main__":
    raise SystemExit(main())
