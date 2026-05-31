"""LangChain + Google Gemini helpers for structured JSON and vision."""
import base64
import os
import time
from typing import Any, Callable, Type, TypeVar

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
DEFAULT_MODEL_RETRY = os.getenv("GEMINI_MODEL_RETRY", "gemini-3.1-pro-preview")
MAX_EXTRACTION_RETRIES = int(os.getenv("MAX_EXTRACTION_RETRIES", "3"))

T = TypeVar("T", bound=BaseModel)


def _api_key() -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return key


def get_chat_model(model_name: str | None = None, temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name or DEFAULT_MODEL,
        google_api_key=_api_key(),
        temperature=temperature,
        max_output_tokens=8192,
    )


def model_attempt_sequence(max_retries: int | None = None) -> list[str]:
    """Primary model first, then retry model for remaining attempts."""
    n = max_retries if max_retries is not None else MAX_EXTRACTION_RETRIES
    return [DEFAULT_MODEL] + [DEFAULT_MODEL_RETRY] * max(0, n - 1)


def invoke_with_model_retries(
    invoke_fn: Callable[[str], tuple[T, dict]],
    *,
    max_retries: int | None = None,
    label: str = "request",
) -> tuple[T, dict]:
    models = model_attempt_sequence(max_retries)
    last_err: Exception | None = None
    for attempt, model_name in enumerate(models, start=1):
        try:
            result, usage = invoke_fn(model_name)
            usage["model"] = model_name
            if attempt > 1:
                usage["retry_attempt"] = attempt
            return result, usage
        except Exception as exc:
            last_err = exc
            if attempt < len(models):
                time.sleep(2 * attempt)
    raise RuntimeError(f"{label} failed after {len(models)} attempt(s)") from last_err


def usage_from_response(response: Any) -> dict:
    meta = getattr(response, "response_metadata", None) or {}
    usage = meta.get("usage_metadata") or meta.get("token_usage") or {}
    if not usage:
        return {}
    return {
        "prompt_tokens": usage.get("prompt_token_count") or usage.get("input_tokens"),
        "candidates_tokens": usage.get("candidates_token_count") or usage.get("output_tokens"),
        "total_tokens": usage.get("total_token_count") or usage.get("total_tokens"),
    }


def _parse_structured_result(parsed: Any, response_model: Type[T]) -> T:
    if isinstance(parsed, response_model):
        return parsed
    if isinstance(parsed, dict) and "parsed" in parsed:
        inner = parsed["parsed"]
        if isinstance(inner, response_model):
            return inner
        return response_model.model_validate(inner)
    return response_model.model_validate(parsed)


def generate_json(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    model_name: str | None = None,
) -> tuple[T, dict]:
    llm = get_chat_model(model_name).with_structured_output(
        response_model, include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    out = llm.invoke(messages)
    usage = usage_from_response(out.get("raw")) if isinstance(out, dict) else {}
    return _parse_structured_result(out, response_model), usage


def generate_json_vision(
    system_prompt: str,
    user_prompt: str,
    image_png_bytes: bytes,
    response_model: Type[T],
    model_name: str | None = None,
) -> tuple[T, dict]:
    b64 = base64.standard_b64encode(image_png_bytes).decode("ascii")
    llm = get_chat_model(model_name).with_structured_output(
        response_model, include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=[
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ]
        ),
    ]
    out = llm.invoke(messages)
    usage = usage_from_response(out.get("raw")) if isinstance(out, dict) else {}
    return _parse_structured_result(out, response_model), usage
