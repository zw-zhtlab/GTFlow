from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from pydantic import TypeAdapter

from ..models.schemas import OpenCodingItem
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json


def build_prompt(segments: List[Dict[str, str]]) -> List[Dict[str, str]]:
    lines: List[str] = []
    for segment in segments:
        speaker = (
            f" ({segment.get('speaker', '').strip()})"
            if segment.get("speaker")
            else ""
        )
        lines.append(f"seg_id={segment['seg_id']}{speaker}: {segment['text']}")
    user = "\n".join(lines)
    return [
        {
            "role": "system",
            "content": (
                "You are a qualitative research assistant specialising in grounded theory. "
                "Respond in Chinese and return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "Open-code the following segments. For each seg_id provide:\n"
                "- in_vivo_phrases (verbatim excerpts)\n"
                "- initial_codes [{code, definition, evidence_span}]\n"
                "- quick_memo\n"
                f"Segments:\n{user}\nStrictly return a JSON array."
            ),
        },
    ]


def _call_with_retry(
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    response_format: Any,
    max_retries: int = 3,
    backoff_base: float = 1.5,
) -> str:
    err: Exception | None = None
    for i in range(max_retries):
        try:
            return provider.generate_text(messages, response_format=response_format)
        except Exception as exc:
            err = exc
            time.sleep(backoff_base**i)
    raise RuntimeError(f"Open coding request failed after {max_retries} attempts: {err}")


def run_open_coding(
    provider: LLMProvider,
    segments: List[Dict[str, Any]],
    batch_size: int = 10,
    max_retries: int = 3,
) -> List[OpenCodingItem]:
    adapter = TypeAdapter(List[OpenCodingItem])
    results: List[OpenCodingItem] = []
    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        messages = build_prompt(batch)
        raw = _call_with_retry(
            provider,
            messages,
            response_format={"type": "json_object"}
            if getattr(provider.conf, "structured", True)
            else None,
            max_retries=max_retries,
        )
        try:
            results.extend(_parse_items(raw, adapter))
        except Exception as exc:
            raise RuntimeError(
                f"Open coding parse failed: {exc}\nModel raw (first 800 chars): {raw[:800]}"
            )
    return results


def _parse_items(raw: str, adapter: TypeAdapter[List[OpenCodingItem]]) -> List[OpenCodingItem]:
    data = try_parse_json(raw)
    parsed = _coerce_and_validate(data, adapter)
    if parsed is not None:
        return parsed
    # fallback to plain json loads
    data = json.loads(raw)
    parsed = _coerce_and_validate(data, adapter)
    if parsed is not None:
        return parsed
    raise ValueError("Unable to parse response as OpenCodingItem list")


def _coerce_and_validate(data: Any, adapter: TypeAdapter[List[OpenCodingItem]]) -> List[OpenCodingItem] | None:
    if isinstance(data, dict):
        if "items" in data:
            data = data["items"]
        else:
            data = [data]
    if isinstance(data, list):
        return adapter.validate_python(data)
    return None
