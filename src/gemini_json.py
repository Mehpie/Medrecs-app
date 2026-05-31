"""Backward-compatible alias — all AI calls go through LangChain (src.llm)."""
from src.llm import DEFAULT_MODEL, generate_json, generate_json_vision, get_chat_model

__all__ = [
    "DEFAULT_MODEL",
    "generate_json",
    "generate_json_vision",
    "get_chat_model",
]
