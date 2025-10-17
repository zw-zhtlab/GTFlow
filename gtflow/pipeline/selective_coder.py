from __future__ import annotations

from typing import Dict, List

from pydantic import TypeAdapter

from ..models.schemas import AxialTriple, Theory
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json


def build_prompt(triples: List[AxialTriple]) -> List[Dict[str, str]]:
    lines: List[str] = []
    for triple in triples[:40]:
        evidence = ",".join(triple.evidence[:5])
        lines.append(
            f"- ({triple.condition}) -> ({triple.action}) -> ({triple.result}); evidence: {evidence}"
        )
    txt = "\n".join(lines) if lines else "(no triples yet)"
    example = '{"core_category":"...","rationale":"...","storyline":"..."}'
    return [
        {
            "role": "system",
            "content": (
                "You are a qualitative methods expert. Summarise the triples into a selective-coding theory: "
                "identify the core category, provide a rationale, and draft a storyline. Output JSON only."
            ),
        },
        {
            "role": "user",
            "content": f"Triples:\n{txt}\nReturn: {example}",
        },
    ]


def build_theory(provider: LLMProvider, triples: List[AxialTriple]) -> Theory:
    messages = build_prompt(triples)
    raw = provider.generate_text(
        messages,
        response_format={"type": "json_object"}
        if getattr(provider.conf, "structured", True)
        else None,
    )
    data = try_parse_json(raw)
    adapter = TypeAdapter(Theory)
    return adapter.validate_python(data)
