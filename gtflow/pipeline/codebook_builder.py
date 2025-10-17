from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pydantic import TypeAdapter

from ..models.schemas import Codebook, OpenCodingItem
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json


def _summarize_codes(open_items: List[OpenCodingItem]) -> Tuple[str, int]:
    counts: Dict[str, int] = {}
    descriptions: Dict[str, str] = {}
    for item in open_items:
        for initial in item.initial_codes:
            code = (initial.code or "").strip()
            if not code:
                continue
            counts[code] = counts.get(code, 0) + 1
            if code not in descriptions and initial.definition:
                descriptions[code] = initial.definition.strip()

    if not counts:
        return "(no initial codes)", 0

    sorted_codes = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    lines = []
    for code, freq in sorted_codes[:40]:
        desc = descriptions.get(code, "")
        desc_suffix = f" · {desc}" if desc else ""
        lines.append(f"- {code} (x{freq}){desc_suffix}")
    return "\n".join(lines), len(counts)


def build_prompt(open_items: List[OpenCodingItem]) -> List[Dict[str, str]]:
    code_summary, unique_codes = _summarize_codes(open_items)
    header = f"Unique initial codes collected: {unique_codes}"
    schema_hint = (
        "Return JSON with the following structure:\n"
        "{\n"
        '  "entries": [\n'
        '    {\n'
        '      "code": "...",\n'
        '      "definition": "...",\n'
        '      "include": ["..."],\n'
        '      "exclude": ["..."],\n'
        '      "positive_examples": ["..."],\n'
        '      "near_miss": ["..."],\n'
        '      "aliases": ["..."]\n'
        "    }\n"
        "  ],\n"
        '  "second_order_themes": {"Theme A": ["code1", "code2"]},\n'
        '  "aggregate_dimensions": {"Dimension X": ["Theme A", "Theme B"]}\n'
        "}"
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a qualitative research consultant. Review the supplied open-coding results, "
                "merge semantically similar initial codes, and produce a structured codebook "
                "(include/exclude guidance, examples, higher-order groupings). Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{header}\n"
                f"Summary of frequent codes:\n{code_summary}\n\n"
                "Produce a JSON codebook with entries, second_order_themes, and aggregate_dimensions.\n"
                f"{schema_hint}"
            ),
        },
    ]


def build_codebook(
    provider: LLMProvider, open_items: List[OpenCodingItem]
) -> Codebook:
    messages = build_prompt(open_items)
    raw = provider.generate_text(
        messages,
        response_format={"type": "json_object"}
        if getattr(provider.conf, "structured", True)
        else None,
    )
    adapter = TypeAdapter(Codebook)

    try:
        data = try_parse_json(raw)
        normalized = _normalize_codebook_payload(data)
        return adapter.validate_python(normalized)
    except Exception as exc:
        try:
            data = _normalize_codebook_payload(raw if isinstance(raw, dict) else try_parse_json(raw))
            return adapter.validate_python(data)
        except Exception:
            pass
    try:
        data = _normalize_codebook_payload(raw)
        return adapter.validate_python(data)
    except Exception as exc:
        raise RuntimeError(
            f"Codebook parse failed: {exc}\nModel raw (first 800 chars): {raw[:800]}"
        )


def _normalize_codebook_payload(data: Any) -> Dict[str, Any]:
    if isinstance(data, str):
        data = try_parse_json(data)

    if isinstance(data, list):
        data = {"entries": data}

    if not isinstance(data, dict):
        return {"entries": []}

    result: Dict[str, Any] = {}

    # entries / codebook list
    entries = (
        data.get("entries")
        or data.get("codebook")
        or data.get("items")
        or data.get("codes")
    )
    result["entries"] = _normalize_entries(entries)

    # second order themes
    result["second_order_themes"] = _normalize_mapping(
        data.get("second_order_themes"), key_field=("theme", "name"), value_field=("codes", "items")
    )

    # aggregate dimensions
    result["aggregate_dimensions"] = _normalize_mapping(
        data.get("aggregate_dimensions"),
        key_field=("dimension", "name"),
        value_field=("themes", "items"),
    )

    return result


def _normalize_entries(entries: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not isinstance(entries, list):
        entries = [entries] if isinstance(entries, dict) else []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = entry.get("code") or entry.get("name") or entry.get("label")
        if not code:
            continue
        defn = entry.get("definition") or entry.get("description") or ""
        normalized.append(
            {
                "code": str(code).strip(),
                "definition": str(defn).strip(),
                "include": _ensure_list(entry.get("include") or entry.get("should_include")),
                "exclude": _ensure_list(entry.get("exclude") or entry.get("should_exclude")),
                "positive_examples": _ensure_list(entry.get("positive_examples") or entry.get("examples")),
                "near_miss": _ensure_list(entry.get("near_miss") or entry.get("boundary_cases")),
                "aliases": _ensure_list(entry.get("aliases") or entry.get("synonyms")),
            }
        )
    return normalized


def _normalize_mapping(value: Any, key_field: Tuple[str, ...], value_field: Tuple[str, ...]) -> Dict[str, List[str]]:
    if isinstance(value, dict):
        # already mapping -> ensure list of str
        return {str(k): _ensure_list(v) for k, v in value.items()}
    if isinstance(value, list):
        mapping: Dict[str, List[str]] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            key = None
            for field in key_field:
                if field in item and item[field]:
                    key = str(item[field])
                    break
            if not key:
                continue
            values = None
            for field in value_field:
                if field in item and item[field]:
                    values = _ensure_list(item[field])
                    break
            mapping[key] = values or []
        return mapping
    return {}


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, bool):
        return []
    if isinstance(value, dict):
        return [str(k).strip() for k, v in value.items() if v] or []
    return []
