from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from ..models.schemas import AxialTriple, Codebook, CodebookEntry, OpenCodingItem, Segment, Theory
from ..utils.file_io import ensure_dir, read_json, write_json, write_text
from ..utils.jsonl_utils import iter_jsonl
from .analytics import build_analysis_bundle
from .gioia_view import to_gioia
from .saturation import saturation_suite


def load_project(out_dir: str) -> Dict[str, Any]:
    name = os.path.basename(os.path.abspath(out_dir)) or "project"
    return {
        "name": name,
        "path": out_dir,
        "segments": _read_model_list(out_dir, "segments.json", Segment),
        "open_items": _read_open_items(out_dir),
        "codebook": _read_model(out_dir, "codebook.json", Codebook, Codebook()),
        "triples": _read_model_list(out_dir, "axial_triples.json", AxialTriple),
        "theory": _read_model(out_dir, "theory.json", Theory, None),
        "negatives": _read_plain(out_dir, "negatives.json", []),
        "saturation": _read_plain(out_dir, "saturation_metrics.json", _read_plain(out_dir, "saturation.json", {})),
    }


def summarize_project(project: Dict[str, Any]) -> Dict[str, Any]:
    codebook: Codebook = project["codebook"]
    open_items = project["open_items"]
    return {
        "name": project["name"],
        "path": project["path"],
        "segments": len(project["segments"]),
        "open_codes": len(open_items),
        "initial_codes": sum(len(item.initial_codes) for item in open_items),
        "codebook_entries": len(codebook.entries),
        "second_order_themes": len(codebook.second_order_themes),
        "aggregate_dimensions": len(codebook.aggregate_dimensions),
        "triples": len(project["triples"]),
        "negative_cases": len(project["negatives"]),
    }


def compare_projects(left_dir: str, right_dir: str) -> Dict[str, Any]:
    left = load_project(left_dir)
    right = load_project(right_dir)
    left_codes = {entry.code for entry in left["codebook"].entries}
    right_codes = {entry.code for entry in right["codebook"].entries}
    return {
        "left": summarize_project(left),
        "right": summarize_project(right),
        "shared_codes": sorted(left_codes & right_codes),
        "left_only_codes": sorted(left_codes - right_codes),
        "right_only_codes": sorted(right_codes - left_codes),
        "shared_code_count": len(left_codes & right_codes),
        "jaccard_code_overlap": round(
            len(left_codes & right_codes) / max(1, len(left_codes | right_codes)),
            4,
        ),
    }


def merge_projects(project_dirs: Iterable[str], out_dir: str) -> Dict[str, Any]:
    projects = [load_project(path) for path in project_dirs]
    ensure_dir(out_dir)

    segments: List[Segment] = []
    open_items: List[OpenCodingItem] = []
    triples: List[AxialTriple] = []
    negatives: List[Dict[str, Any]] = []
    id_maps: Dict[str, Dict[str, str]] = {}

    for project in projects:
        prefix = _safe_prefix(project["name"])
        id_maps[prefix] = {}
        for segment in project["segments"]:
            new_id = f"{prefix}:{segment.seg_id}"
            id_maps[prefix][segment.seg_id] = new_id
            data = segment.model_dump()
            data["seg_id"] = new_id
            data.setdefault("meta", {})
            data["meta"]["project"] = project["name"]
            data["meta"]["source_seg_id"] = segment.seg_id
            segments.append(Segment.model_validate(data))
        for item in project["open_items"]:
            data = item.model_dump()
            data["seg_id"] = id_maps[prefix].get(item.seg_id, f"{prefix}:{item.seg_id}")
            open_items.append(OpenCodingItem.model_validate(data))
        for triple in project["triples"]:
            data = triple.model_dump()
            data["evidence"] = [id_maps[prefix].get(ev, f"{prefix}:{ev}") for ev in triple.evidence]
            triples.append(AxialTriple.model_validate(data))
        for negative in project["negatives"]:
            copied = dict(negative)
            if copied.get("seg_id"):
                copied["seg_id"] = id_maps[prefix].get(str(copied["seg_id"]), f"{prefix}:{copied['seg_id']}")
            copied["project"] = project["name"]
            negatives.append(copied)

    codebook = _merge_codebooks(project["codebook"] for project in projects)
    analytics = build_analysis_bundle(segments, open_items, negatives)
    sat_metrics = saturation_suite([item.model_dump() for item in open_items])

    write_json(os.path.join(out_dir, "segments.json"), [segment.model_dump() for segment in segments])
    write_json(os.path.join(out_dir, "open_codes.json"), [item.model_dump() for item in open_items])
    write_json(os.path.join(out_dir, "codebook.json"), codebook.model_dump())
    write_json(os.path.join(out_dir, "gioia.json"), to_gioia(codebook))
    write_json(os.path.join(out_dir, "axial_triples.json"), [triple.model_dump() for triple in triples])
    write_json(os.path.join(out_dir, "negatives.json"), negatives)
    write_json(os.path.join(out_dir, "analytics.json"), analytics)
    write_json(os.path.join(out_dir, "saturation.json"), sat_metrics["default"])
    write_json(os.path.join(out_dir, "saturation_metrics.json"), sat_metrics)
    write_json(os.path.join(out_dir, "merge_meta.json"), {"projects": [summarize_project(p) for p in projects]})
    write_text(os.path.join(out_dir, "theory.md"), "# Merged Project\n\nThis directory merges existing GTFlow artifacts.\n")

    return {
        "out_dir": out_dir,
        "projects": [summarize_project(project) for project in projects],
        "merged": summarize_project(load_project(out_dir)),
    }


def _merge_codebooks(codebooks: Iterable[Codebook]) -> Codebook:
    entries_by_code: Dict[str, CodebookEntry] = {}
    second_order: Dict[str, List[str]] = {}
    aggregate: Dict[str, List[str]] = {}

    for codebook in codebooks:
        for entry in codebook.entries:
            if entry.code not in entries_by_code:
                entries_by_code[entry.code] = entry
            else:
                entries_by_code[entry.code] = _merge_entries(entries_by_code[entry.code], entry)
        _merge_mapping(second_order, codebook.second_order_themes)
        _merge_mapping(aggregate, codebook.aggregate_dimensions)

    return Codebook(
        entries=sorted(entries_by_code.values(), key=lambda entry: entry.code),
        second_order_themes=second_order,
        aggregate_dimensions=aggregate,
    )


def _merge_entries(left: CodebookEntry, right: CodebookEntry) -> CodebookEntry:
    data = left.model_dump()
    if not data.get("definition") and right.definition:
        data["definition"] = right.definition
    for field in ("include", "exclude", "positive_examples", "near_miss", "aliases"):
        data[field] = _unique([*getattr(left, field), *getattr(right, field)])
    return CodebookEntry.model_validate(data)


def _merge_mapping(target: Dict[str, List[str]], source: Dict[str, List[str]]) -> None:
    for key, values in source.items():
        target[key] = _unique([*target.get(key, []), *values])


def _unique(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _read_model_list(out_dir: str, filename: str, model: Any) -> List[Any]:
    data = _read_plain(out_dir, filename, [])
    return [model.model_validate(item) for item in data if isinstance(item, dict)]


def _read_open_items(out_dir: str) -> List[OpenCodingItem]:
    jsonl_path = os.path.join(out_dir, "open_codes.jsonl")
    if os.path.exists(jsonl_path):
        return [OpenCodingItem.model_validate(item) for item in iter_jsonl(jsonl_path) if isinstance(item, dict)]
    return _read_model_list(out_dir, "open_codes.json", OpenCodingItem)


def _read_model(out_dir: str, filename: str, model: Any, default: Any) -> Any:
    data = _read_plain(out_dir, filename, None)
    if data is None:
        return default
    return model.model_validate(data)


def _read_plain(out_dir: str, filename: str, default: Any) -> Any:
    path = os.path.join(out_dir, filename)
    if not os.path.exists(path):
        return default
    return read_json(path)


def _safe_prefix(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name) or "project"
