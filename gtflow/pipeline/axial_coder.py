from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter

from ..models.schemas import AxialTriple, Codebook
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json
from .retry_utils import call_with_retry


def build_prompt(codebook: Codebook, output_language: str = "English") -> List[Dict[str, str]]:
    lines: List[str] = []
    for entry in codebook.entries[:60]:
        lines.append(f"- {entry.code}: {entry.definition}")
    txt = "\n".join(lines) if lines else "(no data)"
    example = '{"condition":"...","action":"...","result":"...","evidence":["0001"]}'
    return [
        {
            "role": "system",
            "content": (
                "You are a senior qualitative researcher. Perform axial coding, extract "
                "condition->action->result triples, include supporting seg_id evidence, and output JSON only. "
                f"Respond in {output_language}."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Reference codebook:\n{txt}\n"
                f"Return a JSON array where each element looks like: {example}."
            ),
        },
    ]


def build_axial(
    provider: LLMProvider,
    codebook: Codebook,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    max_retries: int = 3,
    output_language: str = "English",
) -> List[AxialTriple]:
    messages = build_prompt(codebook, output_language=output_language)
    raw = call_with_retry(
        provider,
        messages,
        response_format=_axial_response_format() if getattr(provider.conf, "structured", True) else None,
        timeout_sec=timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=max_retries,
        operation_name="Axial coding request",
    )
    data = try_parse_json(raw)
    adapter = TypeAdapter(List[AxialTriple])
    normalized = _normalize_axial_payload(data)
    try:
        return adapter.validate_python(normalized)
    except Exception as exc:
        snippet = raw[:800] if isinstance(raw, str) else str(raw)[:800]
        raise RuntimeError(
            f"Axial coding parse failed: {exc}\nModel raw (first 800 chars): {snippet}"
        )


def _normalize_axial_payload(data: Any) -> Any:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "triples", "data", "results", "output"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return data


def _axial_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "axial_triples",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {"type": "string"},
                        "action": {"type": "string"},
                        "result": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["condition", "action", "result"],
                    "additionalProperties": True,
                },
            },
            "strict": True,
        },
    }
