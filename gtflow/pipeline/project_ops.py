from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from ..models.schemas import AxialTriple, Codebook, CodebookEntry, OpenCodingItem, Segment, Theory
from ..utils.file_io import ensure_dir, read_json, write_json, write_text
from ..utils.jsonl_utils import iter_jsonl
from .analytics import build_analysis_bundle
from .gioia_view import to_gioia
from .saturation import saturation_suite
from .stage_manifest import MANIFEST_FORMAT_VERSION, canonical_sha256, select_open_codes_path, sha256_file


PROJECT_MANIFEST_FILENAME = "project_manifest.json"
PROJECT_MANIFEST_FORMAT_VERSION = 1


def load_project(out_dir: str, *, validate_references: bool = False) -> Dict[str, Any]:
    name = os.path.basename(os.path.abspath(out_dir)) or "project"
    identity = _load_project_identity(out_dir)
    project = {
        "name": name,
        "path": out_dir,
        "project_id": identity["project_id"],
        "manifest": identity,
        "segments": _read_model_list(out_dir, "segments.json", Segment),
        "open_items": _read_open_items(out_dir),
        "codebook": _read_model(out_dir, "codebook.json", Codebook, Codebook()),
        "triples": _read_model_list(out_dir, "axial_triples.json", AxialTriple),
        "theory": _read_model(out_dir, "theory.json", Theory, None),
        "negatives": _read_plain(out_dir, "negatives.json", []),
        "saturation": _read_plain(out_dir, "saturation_metrics.json", _read_plain(out_dir, "saturation.json", {})),
    }
    if validate_references:
        _validate_project(project)
    return project


def summarize_project(project: Dict[str, Any]) -> Dict[str, Any]:
    codebook: Codebook = project["codebook"]
    open_items = project["open_items"]
    return {
        "name": project["name"],
        "path": project["path"],
        "project_id": project["project_id"],
        "manifest_status": project["manifest"]["status"],
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
    projects = [load_project(path, validate_references=True) for path in project_dirs]
    if len(projects) < 2:
        raise ValueError("At least two valid GTFlow projects are required for merge.")
    project_ids = [project["project_id"] for project in projects]
    if len(project_ids) != len(set(project_ids)):
        raise ValueError("Projects to merge must have distinct project IDs.")
    ensure_dir(out_dir)
    stale_stream = os.path.join(out_dir, "open_codes.jsonl")
    if os.path.isfile(stale_stream):
        os.remove(stale_stream)

    segments: List[Segment] = []
    open_items: List[OpenCodingItem] = []
    triples: List[AxialTriple] = []
    negatives: List[Dict[str, Any]] = []
    id_maps: Dict[str, Dict[str, str]] = {}

    for project in projects:
        prefix = f"{_safe_prefix(project['name'])}:{project['project_id'][:8]}"
        id_maps[project["project_id"]] = {}
        id_map = id_maps[project["project_id"]]
        for segment in project["segments"]:
            new_id = f"{prefix}:{segment.seg_id}"
            id_map[segment.seg_id] = new_id
            data = segment.model_dump()
            data["seg_id"] = new_id
            data.setdefault("meta", {})
            data["meta"]["project"] = project["name"]
            data["meta"]["project_id"] = project["project_id"]
            data["meta"]["source_seg_id"] = segment.seg_id
            segments.append(Segment.model_validate(data))
        for item in project["open_items"]:
            data = item.model_dump()
            data["seg_id"] = id_map[item.seg_id]
            open_items.append(OpenCodingItem.model_validate(data))
        for triple in project["triples"]:
            data = triple.model_dump()
            data["evidence"] = [id_map[ev] for ev in triple.evidence]
            data["invalid_evidence"] = [f"{prefix}:{ev}" for ev in triple.invalid_evidence]
            triples.append(AxialTriple.model_validate(data))
        for negative in project["negatives"]:
            copied = dict(negative)
            if copied.get("seg_id"):
                copied["seg_id"] = id_map[str(copied["seg_id"])]
            copied["project"] = project["name"]
            copied["project_id"] = project["project_id"]
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
    merge_meta = {"projects": [summarize_project(p) for p in projects]}
    write_json(os.path.join(out_dir, "merge_meta.json"), merge_meta)
    write_text(os.path.join(out_dir, "theory.md"), "# Merged Project\n\nThis directory merges existing GTFlow artifacts.\n")

    merged_artifact_names = [
        "segments.json",
        "open_codes.json",
        "codebook.json",
        "gioia.json",
        "axial_triples.json",
        "negatives.json",
        "analytics.json",
        "saturation.json",
        "saturation_metrics.json",
        "merge_meta.json",
        "theory.md",
    ]
    source_ids = sorted(project_ids)
    merged_project_id = canonical_sha256({"sources": source_ids})[:16]
    write_json(
        os.path.join(out_dir, PROJECT_MANIFEST_FILENAME),
        {
            "format_version": PROJECT_MANIFEST_FORMAT_VERSION,
            "project_id": merged_project_id,
            "kind": "merged",
            "sources": [
                {
                    "project_id": project["project_id"],
                    "name": project["name"],
                    "manifest_status": project["manifest"]["status"],
                }
                for project in projects
            ],
            "artifacts": {
                name: sha256_file(os.path.join(out_dir, name)) for name in merged_artifact_names
            },
        },
    )

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
    if not isinstance(data, list):
        raise ValueError(f"{filename} must contain a JSON array")
    if any(not isinstance(item, dict) for item in data):
        raise ValueError(f"{filename} contains a non-object record")
    return [model.model_validate(item) for item in data]


def _read_open_items(out_dir: str) -> List[OpenCodingItem]:
    selected = select_open_codes_path(out_dir)
    if selected and selected.endswith(".jsonl"):
        items = list(iter_jsonl(selected))
        if any(not isinstance(item, dict) for item in items):
            raise ValueError("open_codes.jsonl contains a non-object record")
        return [OpenCodingItem.model_validate(item) for item in items]
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


def _load_project_identity(out_dir: str) -> Dict[str, Any]:
    project_path = os.path.join(out_dir, PROJECT_MANIFEST_FILENAME)
    stage_path = os.path.join(out_dir, "stage_manifest.json")
    if os.path.isfile(project_path):
        manifest = read_json(project_path)
        if not isinstance(manifest, dict) or manifest.get("format_version") != PROJECT_MANIFEST_FORMAT_VERSION:
            raise ValueError(f"Invalid project manifest: {project_path}")
        project_id = _validate_project_id(manifest.get("project_id"), project_path)
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise ValueError(f"Project manifest has no artifact hashes: {project_path}")
        _verify_artifact_hashes(out_dir, artifacts, project_path)
        return {"project_id": project_id, "status": "verified-project-manifest", "data": manifest}

    if os.path.isfile(stage_path):
        manifest = read_json(stage_path)
        if not isinstance(manifest, dict) or manifest.get("format_version") != MANIFEST_FORMAT_VERSION:
            raise ValueError(f"Invalid stage manifest: {stage_path}")
        project_id = _validate_project_id(manifest.get("project_id"), stage_path)
        run = manifest.get("run")
        if not isinstance(run, dict) or run.get("status") != "complete":
            raise ValueError(f"Project stage manifest is not complete: {stage_path}")
        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            raise ValueError(f"Project stage manifest has no stages: {stage_path}")
        required = {"segment", "open_coding", "codebook", "axial", "theory", "negatives"}
        incomplete = sorted(
            stage for stage in required if not isinstance(stages.get(stage), dict) or stages[stage].get("status") != "complete"
        )
        if incomplete:
            raise ValueError(f"Project stage manifest has incomplete stages: {', '.join(incomplete)}")
        for stage_name, record in stages.items():
            if not isinstance(record, dict) or record.get("status") != "complete":
                continue
            outputs = record.get("outputs")
            if not isinstance(outputs, dict):
                raise ValueError(f"Stage {stage_name} has no output hashes in {stage_path}")
            _verify_artifact_hashes(out_dir, outputs, stage_path)
        return {"project_id": project_id, "status": "verified-stage-manifest", "data": manifest}

    # Older GTFlow output directories remain mergeable, but receive a stable ID
    # derived from the canonical path and are still subjected to full reference
    # validation before any output is written.
    stable_path = os.path.normcase(os.path.realpath(os.path.abspath(out_dir)))
    return {
        "project_id": canonical_sha256({"legacy_output_path": stable_path})[:16],
        "status": "legacy-derived",
        "data": None,
    }


def _validate_project_id(value: Any, manifest_path: str) -> str:
    project_id = str(value or "")
    if not (8 <= len(project_id) <= 64) or any(
        not (char.isalnum() or char in ("-", "_")) for char in project_id
    ):
        raise ValueError(f"Invalid project_id in {manifest_path}")
    return project_id


def _verify_artifact_hashes(out_dir: str, artifacts: Dict[str, Any], manifest_path: str) -> None:
    root = os.path.realpath(os.path.abspath(out_dir))
    for relative, expected in artifacts.items():
        name = str(relative).replace("\\", "/")
        candidate = os.path.realpath(os.path.join(root, name))
        try:
            inside = os.path.commonpath([root, candidate]) == root
        except ValueError:
            inside = False
        if not inside or os.path.isabs(name) or name.startswith("../"):
            raise ValueError(f"Unsafe artifact path in {manifest_path}: {relative}")
        if not os.path.isfile(candidate):
            raise ValueError(f"Missing manifest artifact: {relative}")
        if not isinstance(expected, str) or sha256_file(candidate) != expected:
            raise ValueError(f"Artifact hash mismatch for {relative}")


def _validate_project(project: Dict[str, Any]) -> None:
    segment_ids = [str(segment.seg_id) for segment in project["segments"]]
    if any(not seg_id for seg_id in segment_ids):
        raise ValueError(f"Project {project['name']} contains an empty segment ID.")
    if len(segment_ids) != len(set(segment_ids)):
        raise ValueError(f"Project {project['name']} contains duplicate segment IDs.")
    valid_ids = set(segment_ids)

    open_ids = [str(item.seg_id) for item in project["open_items"]]
    orphan_open = sorted(set(open_ids) - valid_ids)
    if orphan_open:
        raise ValueError(
            f"Project {project['name']} has open coding rows with unknown seg_id: {', '.join(orphan_open[:5])}"
        )
    if len(open_ids) != len(set(open_ids)):
        raise ValueError(f"Project {project['name']} contains duplicate open coding seg_id values.")

    orphan_evidence = sorted(
        {
            str(evidence_id)
            for triple in project["triples"]
            for evidence_id in triple.evidence
            if str(evidence_id) not in valid_ids
        }
    )
    if orphan_evidence:
        raise ValueError(
            f"Project {project['name']} has axial evidence with unknown seg_id: {', '.join(orphan_evidence[:5])}"
        )

    negatives = project["negatives"]
    if not isinstance(negatives, list) or any(not isinstance(item, dict) for item in negatives):
        raise ValueError(f"Project {project['name']} negatives.json must be an array of objects.")
    orphan_negatives = sorted(
        {
            str(item.get("seg_id"))
            for item in negatives
            if item.get("seg_id") and str(item.get("seg_id")) not in valid_ids
        }
    )
    if orphan_negatives:
        raise ValueError(
            f"Project {project['name']} has negative cases with unknown seg_id: {', '.join(orphan_negatives[:5])}"
        )

    code_names = [entry.code.strip() for entry in project["codebook"].entries]
    if any(not code for code in code_names) or len(code_names) != len(set(code_names)):
        raise ValueError(f"Project {project['name']} contains empty or duplicate codebook codes.")


def _safe_prefix(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name) or "project"
