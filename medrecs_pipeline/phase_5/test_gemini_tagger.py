from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from medrecs_pipeline.phase_5.gemini_tagger import _invoke_once


def test_invoke_once_json_repair_fallback() -> None:
    payload = {
        "clinical_tags": [
            {
                "tag_class": "SYMPTOM",
                "surface": "pain",
                "start": 0,
                "end": 4,
                "confidence": 0.9,
            }
        ],
        "legal_tags": [],
    }
    raw = MagicMock()
    raw.content = json.dumps(payload)

    fake_out = {"parsed": None, "raw": raw}

    with patch("medrecs_pipeline.phase_5.gemini_tagger.get_chat_model") as mock_get:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.invoke.return_value = fake_out
        mock_get.return_value = mock_llm

        extraction, usage = _invoke_once(
            "gemini-test",
            "system",
            "user",
            chunk_id="chunk_test",
        )

    assert len(extraction.clinical_tags) == 1
    assert extraction.clinical_tags[0].surface == "pain"
    assert usage["parse_mode"] in {"json", "json_repair"}
