from __future__ import annotations

from typing import Any, Dict, List

from pydantic import TypeAdapter

from ..models.schemas import AxialTriple, Codebook
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json


def build_prompt(codebook: Codebook) -> List[Dict[str, str]]:
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
                "condition->action->result triples, include supporting seg_id evidence, and output JSON only."
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


def build_axial(provider: LLMProvider, codebook: Codebook) -> List[AxialTriple]:
    messages = build_prompt(codebook)
    raw = provider.generate_text(
        messages,
        response_format={"type": "json_object"}
        if getattr(provider.conf, "structured", True)
        else None,
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
