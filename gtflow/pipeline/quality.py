from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from .evidence import build_evidence_catalog


def build_quality_audit(
    segments: Iterable[Any],
    open_items: Iterable[Any],
    codebook: Any,
    triples: Iterable[Any],
    negatives: Iterable[Mapping[str, Any]],
    *,
    validation_events: Optional[Iterable[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Audit grounding across source, coding, theory-building artifacts.

    The audit is deterministic and contains the concrete invalid/missing IDs so
    a perfect-looking aggregate cannot conceal referential failures.
    """

    segment_list = list(segments)
    item_list = list(open_items)
    triple_list = list(triples)
    negative_list = list(negatives)
    events = [dict(event) for event in (validation_events or [])]
    catalog = build_evidence_catalog(segment_list, item_list)
    valid_ids = set(catalog)

    item_by_id: Dict[str, Dict[str, Any]] = {}
    unknown_open_ids: List[str] = []
    duplicate_open_ids: List[str] = []
    failed_ids: List[str] = []
    for raw_item in item_list:
        item = _as_dict(raw_item)
        seg_id = str(item.get("seg_id") or "")
        if seg_id not in valid_ids:
            unknown_open_ids.append(seg_id)
            continue
        if seg_id in item_by_id:
            duplicate_open_ids.append(seg_id)
            continue
        item_by_id[seg_id] = item
        if item.get("status") == "failed" or item.get("validation_errors"):
            failed_ids.append(seg_id)

    covered_ids = [seg_id for seg_id in catalog if seg_id in item_by_id]
    successful_ids = [seg_id for seg_id in covered_ids if seg_id not in failed_ids]
    missing_ids = [seg_id for seg_id in catalog if seg_id not in item_by_id]
    total_segments = len(catalog)

    verbatim_checks: List[Dict[str, Any]] = []
    observed_codes: set[str] = set()
    for seg_id, item in item_by_id.items():
        source_text = str(catalog[seg_id]["text"])
        for phrase in item.get("in_vivo_phrases") or []:
            _append_verbatim_check(verbatim_checks, seg_id, "in_vivo_phrase", phrase, source_text)
        for raw_code in item.get("initial_codes") or []:
            code = _as_dict(raw_code)
            code_name = str(code.get("code") or "").strip()
            if code_name:
                observed_codes.add(code_name.casefold())
            span = code.get("evidence_span")
            if span:
                _append_verbatim_check(verbatim_checks, seg_id, "evidence_span", span, source_text)

    valid_verbatim = sum(1 for row in verbatim_checks if row["valid"])
    verbatim_rate = _rate(valid_verbatim, len(verbatim_checks), empty=1.0)

    reference_checks: List[Dict[str, Any]] = []
    for index, raw_triple in enumerate(triple_list):
        triple = _as_dict(raw_triple)
        for ref in triple.get("evidence") or []:
            _append_reference_check(reference_checks, "axial", index, ref, valid_ids)
        for ref in triple.get("invalid_evidence") or []:
            _append_reference_check(reference_checks, "axial_rejected", index, ref, valid_ids, forced_invalid=True)
    for index, negative in enumerate(negative_list):
        _append_reference_check(reference_checks, "negative_case", index, negative.get("seg_id"), valid_ids)

    valid_references = sum(1 for row in reference_checks if row["valid"])
    valid_reference_rate = _rate(valid_references, len(reference_checks), empty=1.0)

    entries = _as_dict(codebook).get("entries") or []
    codebook_checks: List[Dict[str, Any]] = []
    for raw_entry in entries:
        entry = _as_dict(raw_entry)
        names = [entry.get("code"), *(entry.get("aliases") or [])]
        grounded = any(str(name or "").strip().casefold() in observed_codes for name in names)
        codebook_checks.append({"code": str(entry.get("code") or ""), "grounded": grounded})
    supported_entries = sum(1 for row in codebook_checks if row["grounded"])
    support_rate = _rate(supported_entries, len(codebook_checks), empty=1.0)

    coverage_rate = _rate(len(covered_ids), total_segments, empty=1.0)
    success_rate = _rate(len(successful_ids), total_segments, empty=1.0)
    scores = [coverage_rate, success_rate, verbatim_rate, valid_reference_rate, support_rate]
    overall_score = round(sum(scores) / len(scores), 4)

    limitations: List[str] = []
    if missing_ids:
        limitations.append(f"{len(missing_ids)} source segments have no open-coding record.")
    if failed_ids:
        limitations.append(f"{len(failed_ids)} source segments have explicit open-coding failures.")
    invalid_reference_ids = [row["seg_id"] for row in reference_checks if not row["valid"]]
    if invalid_reference_ids:
        limitations.append(f"{len(invalid_reference_ids)} downstream evidence references are invalid or rejected.")
    non_verbatim = [row for row in verbatim_checks if not row["valid"]]
    if non_verbatim:
        limitations.append(f"{len(non_verbatim)} claimed excerpts are not verbatim substrings of their source segment.")
    if any(not row["grounded"] for row in codebook_checks):
        limitations.append("Some codebook entries cannot be linked to an observed initial code or alias.")
    if not limitations:
        limitations.append(
            "Automated referential checks cannot establish interpretive validity; researcher review and reflexive memoing remain required."
        )

    return {
        "overall": {"score": overall_score, "scale": "0-1", "passed": overall_score == 1.0},
        "source": {
            "segments": total_segments,
            "duplicate_segment_ids": _duplicates(_segment_ids(segment_list)),
        },
        "open_coding": {
            "coverage_rate": coverage_rate,
            "success_rate": success_rate,
            "covered_ids": covered_ids,
            "missing_ids": missing_ids,
            "failed_ids": failed_ids,
            "unknown_ids": unknown_open_ids,
            "duplicate_ids": duplicate_open_ids,
        },
        "evidence": {
            "valid_reference_rate": valid_reference_rate,
            "verbatim_rate": verbatim_rate,
            "reference_checks": reference_checks,
            "verbatim_checks": verbatim_checks,
            "invalid_reference_ids": invalid_reference_ids,
        },
        "codebook": {"support_rate": support_rate, "entry_checks": codebook_checks},
        "validation_events": events,
        "provenance": {
            "catalog_size": len(catalog),
            "source_order": list(catalog),
            "artifact_counts": {
                "open_coding": len(item_list),
                "codebook_entries": len(entries),
                "axial_triples": len(triple_list),
                "negative_cases": len(negative_list),
            },
        },
        "limitations": limitations,
    }


def _append_verbatim_check(
    rows: List[Dict[str, Any]], seg_id: str, field: str, value: Any, source_text: str
) -> None:
    phrase = str(value or "").strip()
    rows.append(
        {
            "seg_id": seg_id,
            "field": field,
            "value": phrase,
            "valid": bool(phrase) and phrase.casefold() in source_text.casefold(),
        }
    )


def _append_reference_check(
    rows: List[Dict[str, Any]],
    artifact: str,
    index: int,
    value: Any,
    valid_ids: set[str],
    forced_invalid: bool = False,
) -> None:
    seg_id = str(value or "")
    rows.append(
        {
            "artifact": artifact,
            "artifact_index": index,
            "seg_id": seg_id,
            "valid": False if forced_invalid else seg_id in valid_ids,
        }
    )


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _segment_ids(segments: Iterable[Any]) -> List[str]:
    return [str(_as_dict(segment).get("seg_id") or "") for segment in segments]


def _duplicates(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    repeated: List[str] = []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


def _rate(numerator: int, denominator: int, *, empty: float) -> float:
    if denominator == 0:
        return empty
    return round(numerator / denominator, 4)
