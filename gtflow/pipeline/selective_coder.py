from __future__ import annotations

from typing import Dict, List, Optional, Any

from pydantic import TypeAdapter

from ..models.schemas import AxialTriple, Theory
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json
from .retry_utils import call_with_retry


def build_prompt(triples: List[AxialTriple], output_language: str = "English") -> List[Dict[str, str]]:
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
                "identify the core category, provide a rationale, and draft a storyline. Output JSON only. "
                f"Respond in {output_language}."
            ),
        },
        {
            "role": "user",
            "content": f"Triples:\n{txt}\nReturn: {example}",
        },
    ]


def build_theory(
    provider: LLMProvider,
    triples: List[AxialTriple],
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    max_retries: int = 3,
    output_language: str = "English",
) -> Theory:
    messages = build_prompt(triples, output_language=output_language)
    raw = call_with_retry(
        provider,
        messages,
        response_format={"type": "json_object"} if getattr(provider.conf, "structured", True) else None,
        timeout_sec=timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=max_retries,
    )
    data = try_parse_json(raw)
    adapter = TypeAdapter(Theory)
    return adapter.validate_python(data)
