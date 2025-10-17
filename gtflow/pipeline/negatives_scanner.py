from __future__ import annotations

from typing import Dict, List

from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json


def scan_negatives(
    provider: LLMProvider, segments: List[Dict], theory_storyline: str
) -> List[Dict]:
    overview = "\n".join(
        f"{segment['seg_id']}: {segment['text'][:120]}" for segment in segments
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a research assistant. Identify segments that contradict the storyline. "
                "Return a JSON array of {seg_id, conflict_type, explanation, boundary_condition}."
            ),
        },
        {
            "role": "user",
            "content": f"Storyline:\n{theory_storyline}\nSegment overview:\n{overview}",
        },
    ]
    raw = provider.generate_text(
        messages,
        response_format={"type": "json_object"}
        if getattr(provider.conf, "structured", True)
        else None,
    )
    data = try_parse_json(raw)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if isinstance(data, list):
        return data
    return []
