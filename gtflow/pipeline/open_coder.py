from __future__ import annotations

import json
import time
import os
import re
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
    err: Optional[Exception] = None
    force_responses = False

    for i in range(max_retries):
        try:
            if rate_limiter:
                rate_limiter.acquire()
            return provider.generate_text(
                messages,
                response_format=response_format,
                timeout=timeout_sec,
                force_responses=force_responses,
            )
        except Exception as exc:
            err = exc
            if response_format is not None and _should_relax_format(exc):
                response_format = None
            if hasattr(provider, "use_responses") and getattr(provider, "use_responses") is False and _should_relax_format(exc):
                force_responses = True
            # If the request is already too long, retrying with the same payload only wastes time.
            if _is_context_error(exc):
                break
            time.sleep(backoff_base**i)
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
    # Start a fresh stream for each run; callers rely on reruns/--force to overwrite artifacts.
    with open(output_path, "w", encoding="utf-8"):
        pass
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
    candidates = _collect_parse_candidates(raw)
    best: Optional[List[OpenCodingItem]] = None

    for candidate in candidates:
        data = _try_parse_any(candidate)
        parsed = _coerce_and_validate(data, adapter)
        if parsed is not None:
            if _has_any_seg_id(parsed):
                return parsed
            best = best or parsed

    line_items = _parse_json_lines(candidates)
    if line_items:
        parsed = _coerce_and_validate(line_items, adapter)
        if parsed is not None and _has_any_seg_id(parsed):
            return parsed

    for candidate in candidates:
        extracted = _extract_json_objects(candidate)
        if extracted:
            parsed = _coerce_and_validate(extracted, adapter)
            if parsed is not None and _has_any_seg_id(parsed):
                return parsed

    kv_items = _parse_key_value_blocks(raw)
    if kv_items:
        parsed = _coerce_and_validate(kv_items, adapter)
        if parsed is not None and _has_any_seg_id(parsed):
            return parsed

    if best is not None:
        return best
    raise ValueError("Unable to parse response as OpenCodingItem list")


def _extract_json_objects(raw: str) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    in_string = False
    escape = False
    depth = 0
    start_idx: Optional[int] = None

    for i, ch in enumerate(raw):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_text = raw[start_idx : i + 1]
                    obj: Any = None
                    try:
                        obj = try_parse_json(obj_text)
                    except Exception:
                        try:
                            obj = json.loads(obj_text)
                        except Exception:
                            obj = None
                    if isinstance(obj, dict):
                        objects.append(obj)
                    start_idx = None
    return objects


def _collect_parse_candidates(raw: str) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()

    def _add(value: Optional[str]) -> None:
        if not value:
            return
        if value not in seen:
            seen.add(value)
            candidates.append(value)

    _add(raw)
    _add(_sanitize_json_text(raw))
    _add(_normalize_key_value_syntax(raw))

    for block in _extract_code_fences(raw):
        _add(block)
        _add(_sanitize_json_text(block))
        _add(_normalize_key_value_syntax(block))

    bracketed = _extract_bracket_substring(raw)
    _add(bracketed)
    return candidates


def _extract_code_fences(raw: str) -> List[str]:
    blocks: List[str] = []
    pattern = re.compile(r"```(?:json|jsonl|yaml|yml)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(raw):
        block = match.group(1).strip()
        if block:
            blocks.append(block)
    return blocks


def _extract_bracket_substring(raw: str) -> Optional[str]:
    first_brace = raw.find("{")
    first_bracket = raw.find("[")
    starts = [x for x in (first_brace, first_bracket) if x != -1]
    if not starts:
        return None
    start = min(starts)
    end_brace = raw.rfind("}")
    end_bracket = raw.rfind("]")
    end = max(end_brace, end_bracket)
    if end != -1 and end > start:
        return raw[start : end + 1]
    return None


def _try_parse_any(text: str) -> Any:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return try_parse_json(text)
    except Exception:
        pass
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        import yaml
    except Exception:
        return None
    try:
        return yaml.safe_load(text)
    except Exception:
        return None


def _parse_json_lines(candidates: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for text in candidates:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue
            cleaned = line.rstrip(",")
            data = _try_parse_any(cleaned)
            if isinstance(data, dict):
                items.append(data)
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        items.append(entry)
    return items


def _normalize_key_value_syntax(raw: str) -> str:
    if not isinstance(raw, str) or "=" not in raw:
        return raw
    pattern = re.compile(r"(?m)^(\s*[-*•]?\s*)([A-Za-z_][\w ]*)\s*=\s*")
    return pattern.sub(r"\1\2: ", raw)


def _parse_key_value_blocks(raw: str) -> List[Dict[str, Any]]:
    seg_pattern = re.compile(r"(?:^|\n)\s*(seg_id|segment id|seg id)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE)
    matches = list(seg_pattern.finditer(raw))
    if not matches:
        return []

    blocks: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        block_text = raw[start:end]
        seg_id = match.group(2).strip().strip("\"'")
        if not seg_id:
            continue
        block_lines = [line.strip() for line in block_text.splitlines() if line.strip()]
        in_vivo = _extract_list_section(block_lines, ("in_vivo_phrases", "in vivo", "invivo", "in_vivo"))
        codes = _extract_code_section(block_lines)
        memo = _extract_single_line(block_lines, ("quick_memo", "memo", "note"))
        blocks.append(
            {
                "seg_id": seg_id,
                "in_vivo_phrases": in_vivo,
                "initial_codes": codes,
                "quick_memo": memo,
            }
        )
    return blocks


def _extract_list_section(lines: List[str], headers: Tuple[str, ...]) -> List[str]:
    header_set = {h.lower() for h in headers}
    start_idx = None
    for i, line in enumerate(lines):
        for header in header_set:
            if line.lower().startswith(header):
                start_idx = i + 1
                break
        if start_idx is not None:
            break
    if start_idx is None:
        return []
    out: List[str] = []
    for line in lines[start_idx:]:
        lowered = line.lower()
        if any(lowered.startswith(h) for h in ("seg_id", "segment id", "seg id", "initial_codes", "codes", "quick_memo", "memo")):
            break
        value = _strip_bullet(line)
        if value:
            out.append(value)
    return out


def _extract_code_section(lines: List[str]) -> List[Dict[str, Any]]:
    start_idx = None
    for i, line in enumerate(lines):
        lowered = line.lower()
        if lowered.startswith("initial_codes") or lowered.startswith("codes") or lowered.startswith("open codes"):
            start_idx = i + 1
            break
    if start_idx is None:
        return []
    codes: List[Dict[str, Any]] = []
    for line in lines[start_idx:]:
        lowered = line.lower()
        if any(lowered.startswith(h) for h in ("seg_id", "segment id", "seg id", "in_vivo", "in vivo", "quick_memo", "memo")):
            break
        value = _strip_bullet(line)
        if not value:
            continue
        code, definition, evidence = _parse_code_line(value)
        codes.append({"code": code, "definition": definition, "evidence_span": evidence})
    return codes


def _parse_code_line(line: str) -> Tuple[str, Optional[str], Optional[str]]:
    if "code" in line.lower():
        code_match = re.search(r"code\s*[:=]\s*([^;|,]+)", line, re.IGNORECASE)
        def_match = re.search(r"definition\s*[:=]\s*([^;|,]+)", line, re.IGNORECASE)
        ev_match = re.search(r"(evidence_span|evidence)\s*[:=]\s*(.+)$", line, re.IGNORECASE)
        code = code_match.group(1).strip() if code_match else line.strip()
        definition = def_match.group(1).strip() if def_match else None
        evidence = ev_match.group(2).strip() if ev_match else None
        return code, definition, evidence
    return line.strip(), None, None


def _extract_single_line(lines: List[str], headers: Tuple[str, ...]) -> Optional[str]:
    header_set = {h.lower() for h in headers}
    for line in lines:
        lowered = line.lower()
        for header in header_set:
            if lowered.startswith(header):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*[-*•]\s*", "", line).strip()


def _has_any_seg_id(items: List[OpenCodingItem]) -> bool:
    return any(getattr(item, "seg_id", "") for item in items)
def _sanitize_json_text(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        return raw
    out: List[str] = []
    in_string = False
    escape = False
    for ch in raw:
        if in_string:
            if escape:
                escape = False
                out.append(ch)
                continue
            if ch == "\\":
                escape = True
                out.append(ch)
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            if ch in ("\r", "\n"):
                out.append("\\n")
                continue
            if 0 <= ord(ch) < 0x20:
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            continue
        if 0 <= ord(ch) < 0x20 and ch not in ("\r", "\n", "\t"):
            continue
        out.append(ch)
    return "".join(out)


def _coerce_and_validate(data: Any, adapter: TypeAdapter[List[OpenCodingItem]]) -> Optional[List[OpenCodingItem]]:
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

        def _normalize_code_entry(entry: Any) -> Optional[Dict[str, Any]]:
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


def _expected_seg_ids(batch: List[Dict[str, Any]]) -> List[str]:
    return [str(seg.get("seg_id") or "") for seg in batch if seg.get("seg_id") is not None]


def _dedupe_and_order_items(
    items: List[OpenCodingItem],
    expected_ids: List[str],
) -> Tuple[List[OpenCodingItem], List[str]]:
    expected_set = set(expected_ids)
    by_id: Dict[str, OpenCodingItem] = {}
    for item in items:
        seg_id = getattr(item, "seg_id", None)
        if not seg_id or seg_id not in expected_set:
            continue
        if seg_id not in by_id:
            by_id[seg_id] = item
    ordered = [by_id[seg_id] for seg_id in expected_ids if seg_id in by_id]
    missing = [seg_id for seg_id in expected_ids if seg_id not in by_id]
    return ordered, missing


def _make_placeholder_items(missing_ids: List[str]) -> List[OpenCodingItem]:
    return [OpenCodingItem(seg_id=seg_id) for seg_id in missing_ids if seg_id]


def _run_single_request(
    provider: LLMProvider,
    adapter: TypeAdapter[List[OpenCodingItem]],
    batch: List[Dict[str, Any]],
    max_retries: int,
    timeout_sec: int,
    rate_limiter: Optional[Any],
    output_language: str,
) -> List[OpenCodingItem]:
    messages = build_prompt(batch, output_language=output_language)
    response_format = (
        _open_coding_response_format()
        if getattr(provider.conf, "structured", True)
        else None
    )
    raw = _call_with_retry(
        provider,
        messages,
        response_format=response_format,
        max_retries=max_retries,
        timeout_sec=timeout_sec,
        rate_limiter=rate_limiter,
    )
    try:
        return _parse_items(raw, adapter)
    except Exception:
        return []


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
    expected_ids = _expected_seg_ids(batch)
    items = _run_single_request(
        provider,
        adapter,
        batch,
        max_retries,
        timeout_sec,
        rate_limiter,
        output_language,
    )
    ordered, missing = _dedupe_and_order_items(items, expected_ids)

    if missing and len(missing) == len(expected_ids) and len(batch) > 1:
        mid = len(batch) // 2
        left = _run_batch(
            provider,
            adapter,
            batch[:mid],
            max_retries,
            timeout_sec,
            rate_limiter,
            max_prompt_chars,
            output_language,
        )
        right = _run_batch(
            provider,
            adapter,
            batch[mid:],
            max_retries,
            timeout_sec,
            rate_limiter,
            max_prompt_chars,
            output_language,
        )
        return left + right

    if missing:
        missing_segs = [seg for seg in batch if str(seg.get("seg_id") or "") in set(missing)]
        retry_items = _run_single_request(
            provider,
            adapter,
            missing_segs,
            max_retries,
            timeout_sec,
            rate_limiter,
            output_language,
        )
        ordered_retry, missing_retry = _dedupe_and_order_items(retry_items, missing)
        ordered.extend(ordered_retry)
        missing = missing_retry

    if missing:
        filled = _make_placeholder_items(missing)
        ordered.extend(filled)

    return ordered
