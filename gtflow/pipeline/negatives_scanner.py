from __future__ import annotations

from typing import Dict, List, Any, Optional

from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json
from .retry_utils import call_with_retry


def scan_negatives(
    provider: LLMProvider,
    segments: List[Dict],
    theory_storyline: str,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    max_retries: int = 3,
    max_segments_per_request: int = 50,
    max_prompt_chars: int = 6000,
    output_language: str = "English",
) -> List[Dict]:
    def _scan_batch(batch: List[Dict]) -> List[Dict]:
        overview = "\n".join(
            f"{segment['seg_id']}: {segment.get('text','')[:120]}" for segment in batch
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant. Identify segments that contradict the storyline. "
                    "Return a JSON array of {seg_id, conflict_type, explanation, boundary_condition}. "
                    f"Respond in {output_language}."
                ),
            },
            {
                "role": "user",
                "content": f"Storyline:\n{theory_storyline}\nSegment overview:\n{overview}",
            },
        ]
        raw = call_with_retry(
            provider,
            messages,
            response_format=_negatives_response_format() if getattr(provider.conf, "structured", True) else None,
            timeout_sec=timeout_sec,
            rate_limiter=rate_limiter,
            max_retries=max_retries,
            operation_name="Negative case request",
        )
        data = try_parse_json(raw)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if isinstance(data, list):
            return data
        return []

    results: List[Dict] = []
    batch: List[Dict] = []
    current_chars = 0
    for segment in segments:
        preview = f"{segment.get('seg_id','')}: {segment.get('text','')[:120]}"
        line_len = len(preview) + 1
        if batch and (len(batch) >= max_segments_per_request or current_chars + line_len > max_prompt_chars):
            results.extend(_scan_batch(batch))
            batch = []
            current_chars = 0
        batch.append(segment)
        current_chars += line_len

    if batch:
        results.extend(_scan_batch(batch))

    return results


def _negatives_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "negative_cases",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "seg_id": {"type": "string"},
                        "conflict_type": {"type": "string"},
                        "explanation": {"type": "string"},
                        "boundary_condition": {"type": "string"},
                    },
                    "required": ["seg_id"],
                    "additionalProperties": True,
                },
            },
            "strict": True,
        },
    }
