from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Tuple


def code_frequencies(open_items: Iterable[Any]) -> List[Dict[str, Any]]:
    counts: Counter[str] = Counter()
    for item in open_items:
        for code in _codes_for_item(item):
            counts[code] += 1
    return [{"code": code, "count": count} for code, count in counts.most_common()]


def negative_case_summary(negatives: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_type: Counter[str] = Counter()
    by_boundary: Counter[str] = Counter()
    for negative in negatives:
        conflict = str(negative.get("conflict_type") or "unspecified").strip() or "unspecified"
        boundary = str(negative.get("boundary_condition") or "unspecified").strip() or "unspecified"
        by_type[conflict] += 1
        by_boundary[boundary] += 1
    return {
        "by_conflict_type": _counter_rows(by_type, "conflict_type"),
        "by_boundary_condition": _counter_rows(by_boundary, "boundary_condition"),
    }


def negative_case_rows(
    negatives: Iterable[Dict[str, Any]],
    segments: Iterable[Any],
) -> List[Dict[str, Any]]:
    segment_by_id = {_segment_id(segment): segment for segment in segments}
    rows: List[Dict[str, Any]] = []
    for negative in negatives:
        seg_id = str(negative.get("seg_id") or "")
        segment = segment_by_id.get(seg_id)
        rows.append(
            {
                "seg_id": seg_id,
                "participant": _participant_for_segment(segment),
                "conflict_type": negative.get("conflict_type") or "",
                "boundary_condition": negative.get("boundary_condition") or "",
                "explanation": negative.get("explanation") or "",
            }
        )
    return rows


def participant_contrasts(
    segments: Iterable[Any],
    open_items: Iterable[Any],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    participant_by_seg = {_segment_id(segment): _participant_for_segment(segment) for segment in segments}
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"segments": 0, "open_codes": 0, "codes": Counter()})
    for participant in participant_by_seg.values():
        stats[participant]["segments"] += 1

    for item in open_items:
        participant = participant_by_seg.get(_item_seg_id(item), "unknown")
        codes = _codes_for_item(item)
        stats[participant]["open_codes"] += len(codes)
        stats[participant]["codes"].update(codes)

    rows: List[Dict[str, Any]] = []
    for participant, values in sorted(stats.items()):
        codes_counter: Counter[str] = values["codes"]
        rows.append(
            {
                "participant": participant,
                "segments": values["segments"],
                "open_codes": values["open_codes"],
                "unique_codes": len(codes_counter),
                "top_codes": ", ".join(code for code, _ in codes_counter.most_common(top_n)),
            }
        )
    return rows


def participant_code_matrix(
    segments: Iterable[Any],
    open_items: Iterable[Any],
    top_codes: int = 8,
) -> List[Dict[str, Any]]:
    frequencies = code_frequencies(open_items)
    selected = [row["code"] for row in frequencies[:top_codes]]
    participant_by_seg = {_segment_id(segment): _participant_for_segment(segment) for segment in segments}
    matrix: Dict[str, Counter[str]] = defaultdict(Counter)
    for item in open_items:
        participant = participant_by_seg.get(_item_seg_id(item), "unknown")
        matrix[participant].update(code for code in _codes_for_item(item) if code in selected)
    rows: List[Dict[str, Any]] = []
    for participant in sorted(matrix):
        row: Dict[str, Any] = {"participant": participant}
        row.update({code: matrix[participant].get(code, 0) for code in selected})
        rows.append(row)
    return rows


def build_analysis_bundle(
    segments: Iterable[Any],
    open_items: Iterable[Any],
    negatives: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    segments_list = list(segments)
    open_items_list = list(open_items)
    negatives_list = list(negatives)
    return {
        "code_frequencies": code_frequencies(open_items_list),
        "negative_cases": negative_case_summary(negatives_list),
        "negative_case_rows": negative_case_rows(negatives_list, segments_list),
        "participant_contrasts": participant_contrasts(segments_list, open_items_list),
        "participant_code_matrix": participant_code_matrix(segments_list, open_items_list),
    }


def _counter_rows(counter: Counter[str], key: str) -> List[Dict[str, Any]]:
    return [{key: name, "count": count} for name, count in counter.most_common()]


def _codes_for_item(item: Any) -> List[str]:
    raw_codes = getattr(item, "initial_codes", None)
    if raw_codes is None and isinstance(item, dict):
        raw_codes = item.get("initial_codes", [])
    codes: List[str] = []
    for raw in raw_codes or []:
        code = getattr(raw, "code", None)
        if code is None and isinstance(raw, dict):
            code = raw.get("code")
        text = str(code or "").strip()
        if text:
            codes.append(text)
    return codes


def _item_seg_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("seg_id") or "")
    return str(getattr(item, "seg_id", "") or "")


def _segment_id(segment: Any) -> str:
    if isinstance(segment, dict):
        return str(segment.get("seg_id") or "")
    return str(getattr(segment, "seg_id", "") or "")


def _participant_for_segment(segment: Any) -> str:
    if segment is None:
        return "unknown"
    if isinstance(segment, dict):
        speaker = segment.get("speaker")
        meta = segment.get("meta") or {}
    else:
        speaker = getattr(segment, "speaker", None)
        meta = getattr(segment, "meta", {}) or {}
    for key in ("participant", "participant_id", "interviewee", "speaker_id"):
        value = meta.get(key) if isinstance(meta, dict) else None
        if value:
            return str(value)
    return str(speaker or "unknown")
