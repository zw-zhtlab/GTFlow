from __future__ import annotations

import json
import time
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import TypeAdapter

from ..models.schemas import OpenCodingItem
from ..providers.base import LLMProvider
from ..utils.json_utils import try_parse_json
from ..utils.jsonl_utils import append_jsonl


def _should_relax_format(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(token in msg for token in ("rate limit", "429", "timeout", "temporarily unavailable")):
        return False
    return any(token in msg for token in ("response_format", "schema", "json", "bad request", "400"))


def _is_context_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "context length",
            "maximum context length",
            "max context length",
            "too many tokens",
            "tokens exceed",
            "too long",
            "overloaded input",
            "length limit",
        )
    )


def build_prompt(segments: List[Dict[str, str]], output_language: str = "English") -> List[Dict[str, str]]:
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
                f"Respond in {output_language} and return JSON only."
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
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
) -> str:
    err: Exception | None = None
    toggled_endpoint = False
    original_use_responses = getattr(provider, "use_responses", None)
    try:
        for i in range(max_retries):
            try:
                if rate_limiter:
                    rate_limiter.acquire()
                return provider.generate_text(
                    messages,
                    response_format=response_format,
                    timeout=timeout_sec,
                )
            except Exception as exc:
                err = exc
                if response_format is not None and _should_relax_format(exc):
                    response_format = None
                if hasattr(provider, "use_responses") and provider.use_responses is False and _should_relax_format(exc):
                    provider.use_responses = True
                    toggled_endpoint = True
                # If the request is already too long, retrying with the same payload only wastes time.
                if _is_context_error(exc):
                    break
                time.sleep(backoff_base**i)
    finally:
        if toggled_endpoint and original_use_responses is not None:
            try:
                provider.use_responses = original_use_responses
            except Exception:
                pass
    raise RuntimeError(f"Open coding request failed after {max_retries} attempts: {err}")


def run_open_coding(
    provider: LLMProvider,
    segments: Iterable[Dict[str, Any]],
    batch_size: int = 10,
    max_prompt_chars: Optional[int] = None,
    max_retries: int = 3,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    max_concurrency: int = 1,
    output_language: str = "English",
) -> List[OpenCodingItem]:
    adapter = TypeAdapter(List[OpenCodingItem])
    results: List[OpenCodingItem] = []

    if max_concurrency and max_concurrency > 1 and isinstance(segments, list):
        batches = list(_yield_batches(segments, batch_size, max_prompt_chars, output_language))
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            future_map = {
                executor.submit(
                    _run_batch,
                    provider,
                    adapter,
                    batch,
                    max_retries,
                    timeout_sec,
                    rate_limiter,
                    max_prompt_chars,
                    output_language,
                ): idx
                for idx, batch in enumerate(batches)
            }
            ordered: Dict[int, List[OpenCodingItem]] = {}
            for future in as_completed(future_map):
                idx = future_map[future]
                ordered[idx] = future.result()
            for idx in sorted(ordered.keys()):
                results.extend(ordered[idx])
    else:
        for batch in _yield_batches(segments, batch_size, max_prompt_chars, output_language):
            results.extend(
                _run_batch(
                    provider,
                    adapter,
                    batch,
                    max_retries,
                    timeout_sec,
                    rate_limiter,
                    max_prompt_chars,
                    output_language,
                )
            )
    return results


def run_open_coding_streaming(
    provider: LLMProvider,
    segments: Iterable[Dict[str, Any]],
    output_path: str,
    batch_size: int = 10,
    max_prompt_chars: Optional[int] = None,
    max_retries: int = 3,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    sample_limit: int = 50,
    output_language: str = "English",
) -> Tuple[int, List[OpenCodingItem]]:
    from ..utils.file_io import ensure_dir

    adapter = TypeAdapter(List[OpenCodingItem])
    ensure_dir(os.path.dirname(output_path) or ".")
    total = 0
    sample: List[OpenCodingItem] = []

    for batch in _yield_batches(segments, batch_size, max_prompt_chars, output_language):
        items = _run_batch(
            provider, adapter, batch, max_retries, timeout_sec, rate_limiter, max_prompt_chars, output_language
        )
        append_jsonl(output_path, [x.model_dump() for x in items])
        total += len(items)
        if len(sample) < sample_limit:
            remaining = sample_limit - len(sample)
            sample.extend(items[:remaining])
    return total, sample


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
        normalized = _normalize_open_items(data)
        return adapter.validate_python(normalized)
    return None


def _normalize_open_items(items: List[Any]) -> List[Dict[str, Any]]:
    """Normalize LLM outputs into the expected OpenCodingItem shape."""
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            # If the model returned a bare value, skip it.
            continue
        seg_id = item.get("seg_id") or item.get("id") or ""

        def _as_str_list(value: Any) -> List[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(x) for x in value if x is not None]
            return [str(value)]

        def _normalize_code_entry(entry: Any) -> Dict[str, Any] | None:
            if isinstance(entry, dict):
                code_val = entry.get("code") or entry.get("name") or entry.get("label")
                if not code_val:
                    return None
                return {
                    "code": str(code_val),
                    "definition": entry.get("definition") or entry.get("desc") or entry.get("description"),
                    "evidence_span": entry.get("evidence_span") or entry.get("evidence"),
                }
            if entry is None:
                return None
            return {"code": str(entry), "definition": None, "evidence_span": None}

        in_vivo = _as_str_list(item.get("in_vivo_phrases"))

        raw_codes = item.get("initial_codes")
        codes_list: List[Dict[str, Any]] = []
        if isinstance(raw_codes, list):
            for entry in raw_codes:
                norm = _normalize_code_entry(entry)
                if norm:
                    codes_list.append(norm)
        elif raw_codes is not None:
            norm = _normalize_code_entry(raw_codes)
            if norm:
                codes_list.append(norm)

        quick_memo = item.get("quick_memo")
        if quick_memo is not None and not isinstance(quick_memo, str):
            quick_memo = str(quick_memo)

        normalized.append(
            {
                "seg_id": seg_id,
                "in_vivo_phrases": in_vivo,
                "initial_codes": codes_list,
                "quick_memo": quick_memo,
            }
        )
    return normalized


def _safe_len(value: Any) -> int:
    """Len helper that tolerates None/non-strings."""
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    return len(str(value))


def _open_coding_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "open_coding_items",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "seg_id": {"type": "string"},
                        "in_vivo_phrases": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "initial_codes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string"},
                                    "definition": {"type": "string"},
                                    "evidence_span": {"type": "string"},
                                },
                                "required": ["code"],
                                "additionalProperties": True,
                            },
                        },
                        "quick_memo": {"type": "string"},
                    },
                    "required": ["seg_id"],
                    "additionalProperties": True,
                },
            },
            "strict": True,
        },
    }


def _segment_prompt_length(seg: Dict[str, Any]) -> int:
    seg_id = seg.get("seg_id") or ""
    text = seg.get("text") or ""
    speaker = seg.get("speaker") or ""
    return _safe_len(seg_id) + _safe_len(text) + _safe_len(speaker) + 16


def _prompt_overhead_chars(output_language: str) -> int:
    return len(
        "You are a qualitative research assistant specialising in grounded theory. "
        f"Respond in {output_language} and return JSON only. Open-code the following segments. "
        "For each seg_id provide: in_vivo_phrases, initial_codes, quick_memo."
    )


def _yield_batches(
    segments: Iterable[Dict[str, Any]],
    batch_size: int,
    max_prompt_chars: Optional[int],
    output_language: str,
) -> Iterable[List[Dict[str, Any]]]:
    batch: List[Dict[str, Any]] = []
    current_chars = 0
    overhead_chars = _prompt_overhead_chars(output_language) if max_prompt_chars else 0
    for seg in segments:
        seg_len = _segment_prompt_length(seg)
        # If the segment itself exceeds the budget, truncate its text to fit the ceiling.
        if max_prompt_chars:
            available_for_text = max_prompt_chars - overhead_chars - 32
            if seg_len > available_for_text and available_for_text > 0:
                truncated = dict(seg)
                text = truncated.get("text", "")
                truncated["text"] = text[: max(0, available_for_text - len(truncated.get("seg_id", "")))]
                seg = truncated
                seg_len = _segment_prompt_length(seg)
            if batch and current_chars + seg_len + overhead_chars > max_prompt_chars:
                yield batch
                batch = []
                current_chars = 0
        batch.append(seg)
        current_chars += seg_len
        if len(batch) >= batch_size:
            yield batch
            batch = []
            current_chars = 0
    if batch:
        yield batch


def _run_batch(
    provider: LLMProvider,
    adapter: TypeAdapter[List[OpenCodingItem]],
    batch: List[Dict[str, Any]],
    max_retries: int,
    timeout_sec: int,
    rate_limiter: Optional[Any],
    max_prompt_chars: Optional[int],
    output_language: str,
) -> List[OpenCodingItem]:
    messages = build_prompt(batch, output_language=output_language)
    raw = _call_with_retry(
        provider,
        messages,
        response_format=_open_coding_response_format()
        if getattr(provider.conf, "structured", True)
        else None,
        max_retries=max_retries,
        timeout_sec=timeout_sec,
        rate_limiter=rate_limiter,
    )
    try:
        return _parse_items(raw, adapter)
    except Exception as exc:
        raise RuntimeError(
            f"Open coding parse failed: {exc}\nModel raw (first 800 chars): {raw[:800]}"
        )
