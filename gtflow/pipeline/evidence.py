from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping


EvidenceCatalog = Dict[str, Dict[str, Any]]


def build_evidence_catalog(
    segments: Iterable[Any], open_items: Iterable[Any] = ()
) -> EvidenceCatalog:
    """Build the canonical, source-ordered evidence catalog used across stages.

    Segment text is copied once into this catalog and downstream prompts receive
    the catalog as data. Model-produced IDs can then be checked against the same
    immutable key set before an artifact is persisted.
    """

    catalog: EvidenceCatalog = {}
    for source_index, segment in enumerate(segments):
        data = _as_mapping(segment)
        seg_id = str(data.get("seg_id") or "").strip()
        if not seg_id or seg_id in catalog:
            continue
        catalog[seg_id] = {
            "seg_id": seg_id,
            "source_index": source_index,
            "text": str(data.get("text") or ""),
            "speaker": data.get("speaker"),
            "meta": dict(data.get("meta") or {}),
            "codes": [],
            "in_vivo_phrases": [],
            "open_coding_status": "missing",
            "validation_errors": [],
        }

    for item in open_items:
        data = _as_mapping(item)
        seg_id = str(data.get("seg_id") or "").strip()
        if seg_id not in catalog:
            continue
        codes: List[str] = []
        for raw_code in data.get("initial_codes") or []:
            code_data = _as_mapping(raw_code)
            code = str(code_data.get("code") or "").strip()
            if code:
                codes.append(code)
        record = catalog[seg_id]
        record["codes"] = codes
        record["in_vivo_phrases"] = [
            str(value) for value in data.get("in_vivo_phrases") or [] if str(value)
        ]
        record["open_coding_status"] = str(data.get("status") or "ok")
        record["validation_errors"] = [
            str(value) for value in data.get("validation_errors") or [] if str(value)
        ]
    return catalog


def valid_evidence_ids(catalog: Mapping[str, Any]) -> set[str]:
    return {str(key) for key in catalog if str(key)}


def _as_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}
