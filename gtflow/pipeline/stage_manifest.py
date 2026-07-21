from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union
from urllib.parse import urlsplit, urlunsplit

from ..utils.file_io import read_json, write_json


MANIFEST_FILENAME = "stage_manifest.json"
MANIFEST_FORMAT_VERSION = 1
PIPELINE_SCHEMA_VERSION = "gtflow-grounding-v1"


_STAGE_SOURCE_FILES: Dict[str, tuple[str, ...]] = {
    "segment": ("pipeline/segmenter.py", "models/schemas.py"),
    "open_coding": (
        "pipeline/open_coder.py",
        "pipeline/retry_utils.py",
        "models/schemas.py",
        "prompts/open_coding_zh.yaml",
    ),
    "evidence": ("pipeline/evidence.py", "models/schemas.py"),
    "codebook": (
        "pipeline/codebook_builder.py",
        "pipeline/retry_utils.py",
        "models/schemas.py",
        "prompts/codebook_zh.yaml",
    ),
    "axial": (
        "pipeline/axial_coder.py",
        "pipeline/retry_utils.py",
        "models/schemas.py",
        "prompts/axial_zh.yaml",
    ),
    "theory": (
        "pipeline/selective_coder.py",
        "pipeline/retry_utils.py",
        "models/schemas.py",
        "prompts/selective_zh.yaml",
    ),
    "gioia": ("pipeline/gioia_view.py", "models/schemas.py"),
    "negatives": (
        "pipeline/negatives_scanner.py",
        "pipeline/retry_utils.py",
        "models/schemas.py",
    ),
    "analytics": ("pipeline/analytics.py", "models/schemas.py"),
    "saturation": ("pipeline/saturation.py", "models/schemas.py"),
    "quality": ("pipeline/quality.py", "pipeline/evidence.py", "models/schemas.py"),
    "report": ("pipeline/report_html.py", "models/schemas.py"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Union[str, os.PathLike[str]]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_url(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def normalized_config(config: Any) -> Dict[str, Any]:
    """Return a deterministic, non-secret configuration snapshot.

    Credentials are deliberately never persisted. Header values are represented
    by one-way fingerprints so a behavior-affecting header change invalidates the
    cache without writing the secret into the project directory.
    """

    if hasattr(config, "model_dump"):
        raw = config.model_dump(mode="json")
    elif isinstance(config, Mapping):
        raw = dict(config)
    else:
        raise TypeError("config must be a Pydantic model or mapping")

    def scrub(value: Any, key: str = "") -> Any:
        lowered = key.lower()
        if lowered in {"api_key", "password", "access_token", "refresh_token"}:
            return {"present": bool(value)}
        if lowered == "extra_headers" and isinstance(value, Mapping):
            return {
                str(name): {"sha256": canonical_sha256(str(header_value))}
                for name, header_value in sorted(value.items(), key=lambda item: str(item[0]).lower())
            }
        if isinstance(value, Mapping):
            return {str(k): scrub(v, str(k)) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
        if isinstance(value, (list, tuple)):
            return [scrub(item) for item in value]
        if lowered in {"base_url", "endpoint"}:
            return _safe_url(value)
        return value

    result = scrub(raw)
    if isinstance(result.get("output"), dict):
        # The output location is an execution detail, not an analysis input.
        result["output"].pop("out_dir", None)
    return result


def stage_definition_fingerprint(stage: str) -> str:
    package_root = Path(__file__).resolve().parents[1]
    entries: list[dict[str, str]] = []
    for relative in _STAGE_SOURCE_FILES.get(stage, ("models/schemas.py",)):
        path = package_root / relative
        entries.append(
            {
                "path": relative,
                "sha256": sha256_file(path) if path.is_file() else "missing",
            }
        )
    return canonical_sha256(
        {
            "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
            "stage": stage,
            "sources": entries,
        }
    )


def select_open_codes_path(out_dir: str) -> Optional[str]:
    """Select the manifest-declared canonical open-coding artifact.

    Legacy outputs keep their historical JSONL preference, while manifest-backed
    runs never allow an untracked stale JSONL file to shadow a completed JSON
    artifact.
    """

    root = os.path.abspath(out_dir)
    json_path = os.path.join(root, "open_codes.json")
    jsonl_path = os.path.join(root, "open_codes.jsonl")
    manifest_path = os.path.join(root, MANIFEST_FILENAME)
    if os.path.isfile(manifest_path):
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict) or manifest.get("format_version") != MANIFEST_FORMAT_VERSION:
            raise ValueError(f"Unsupported or invalid GTFlow stage manifest: {manifest_path}")
        record = (manifest.get("stages") or {}).get("open_coding")
        if not isinstance(record, dict) or record.get("status") != "complete":
            raise ValueError(f"Open-coding stage is not complete in {manifest_path}")
        primary = (record.get("metadata") or {}).get("primary_output")
        if primary not in {"open_codes.json", "open_codes.jsonl"}:
            raise ValueError(f"Open-coding stage has no valid primary output in {manifest_path}")
        selected = os.path.join(root, primary)
        if not os.path.isfile(selected):
            raise FileNotFoundError(selected)
        return selected

    # Merged-project manifests always declare the canonical JSON artifact.
    if os.path.isfile(os.path.join(root, "project_manifest.json")) and os.path.isfile(json_path):
        return json_path
    if os.path.isfile(jsonl_path):
        return jsonl_path
    if os.path.isfile(json_path):
        return json_path
    return None


def _stage_config(stage: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    run = dict(config.get("run") or {})
    provider = dict(config.get("provider") or {})
    if stage == "segment":
        return {
            "segmentation_strategy": run.get("segmentation_strategy"),
            "max_segment_chars": run.get("max_segment_chars"),
        }
    if stage in {"open_coding", "codebook", "axial", "theory", "negatives"}:
        return {"provider": provider, "run": run}
    if stage == "report":
        return {"output": dict(config.get("output") or {})}
    return {}


class StageManifest:
    def __init__(self, out_dir: str):
        self.out_dir = os.path.abspath(out_dir)
        self.path = os.path.join(self.out_dir, MANIFEST_FILENAME)
        if os.path.exists(self.path):
            data = read_json(self.path)
            if not isinstance(data, dict) or data.get("format_version") != MANIFEST_FORMAT_VERSION:
                raise ValueError(f"Unsupported or invalid GTFlow stage manifest: {self.path}")
            if not isinstance(data.get("stages", {}), dict):
                raise ValueError(f"Invalid stages object in GTFlow stage manifest: {self.path}")
            self.data: Dict[str, Any] = data
        else:
            stable_path = os.path.normcase(os.path.realpath(self.out_dir))
            self.data = {
                "format_version": MANIFEST_FORMAT_VERSION,
                "project_id": canonical_sha256({"output_path": stable_path})[:16],
                "created_at": _utc_now(),
                "stages": {},
            }

    @property
    def project_id(self) -> str:
        return str(self.data["project_id"])

    def begin_run(
        self,
        *,
        input_path: str,
        input_sha256: str,
        config: Mapping[str, Any],
    ) -> None:
        self.data["run"] = {
            "status": "running",
            "input_path": os.path.basename(input_path),
            "input_sha256": input_sha256,
            "normalized_config": dict(config),
            "provider": (config.get("provider") or {}).get("name"),
            "model": (config.get("provider") or {}).get("model"),
            "started_at": _utc_now(),
        }
        self.data["updated_at"] = _utc_now()
        self._save()

    def signature(
        self,
        stage: str,
        *,
        input_sha256: str,
        config: Mapping[str, Any],
        upstream_paths: Iterable[str] = (),
    ) -> tuple[str, Dict[str, str], str]:
        upstream = self._upstream_context(upstream_paths)
        definition = stage_definition_fingerprint(stage)
        signature = canonical_sha256(
            {
                "stage": stage,
                "input_sha256": input_sha256,
                "config": _stage_config(stage, config),
                "prompt_schema_version": definition,
                "upstream": upstream,
            }
        )
        return signature, upstream, definition

    def can_reuse(self, stage: str, signature: str, output_paths: Iterable[str]) -> bool:
        record = self.data.get("stages", {}).get(stage)
        if not isinstance(record, dict):
            return False
        if record.get("status") != "complete" or record.get("signature") != signature:
            return False
        expected = record.get("outputs")
        if not isinstance(expected, dict):
            return False
        try:
            actual = self.hash_paths(output_paths)
        except FileNotFoundError:
            return False
        return actual == expected

    def mark_running(
        self,
        stage: str,
        *,
        signature: str,
        upstream: Mapping[str, str],
        definition_fingerprint: str,
    ) -> None:
        self.data.setdefault("stages", {})[stage] = {
            "status": "running",
            "signature": signature,
            "prompt_schema_version": definition_fingerprint,
            "upstream": dict(upstream),
            "started_at": _utc_now(),
        }
        self.data["updated_at"] = _utc_now()
        self._save()

    def mark_complete(
        self,
        stage: str,
        *,
        output_paths: Iterable[str],
        counts: Optional[Mapping[str, int]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        record = self.data.setdefault("stages", {}).setdefault(stage, {})
        record.update(
            {
                "status": "complete",
                "outputs": self.hash_paths(output_paths),
                "counts": dict(counts or {}),
                "completed_at": _utc_now(),
            }
        )
        if metadata:
            record["metadata"] = dict(metadata)
        else:
            record.pop("metadata", None)
        record.pop("error", None)
        self.data["updated_at"] = _utc_now()
        self._save()

    def mark_failed(self, stage: str, exc: BaseException) -> None:
        record = self.data.setdefault("stages", {}).setdefault(stage, {})
        record.update(
            {
                "status": "failed",
                "failed_at": _utc_now(),
                "error": {"type": type(exc).__name__},
            }
        )
        record.pop("outputs", None)
        self.data["updated_at"] = _utc_now()
        self._save()

    def finish_run(self, *, counts: Mapping[str, int], status: str = "complete") -> None:
        run = self.data.setdefault("run", {})
        run["status"] = status
        run["counts"] = dict(counts)
        run["finished_at"] = _utc_now()
        self.data["updated_at"] = _utc_now()
        self._save()

    def hash_paths(self, paths: Iterable[str]) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        for raw_path in paths:
            path = os.path.abspath(raw_path)
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            try:
                name = os.path.relpath(path, self.out_dir).replace("\\", "/")
            except ValueError:
                name = os.path.basename(path)
            hashes[name] = sha256_file(path)
        return dict(sorted(hashes.items()))

    def _upstream_context(self, paths: Iterable[str]) -> Dict[str, str]:
        """Hash artifacts and bind them to their producing stage signature.

        The producer signature is essential when a prompt/config change happens
        to produce byte-identical output: downstream caches must still be
        invalidated because their methodological provenance changed.
        """

        hashes = self.hash_paths(paths)
        context = dict(hashes)
        requested = set(hashes)
        for stage_name, record in (self.data.get("stages") or {}).items():
            if not isinstance(record, dict) or record.get("status") != "complete":
                continue
            outputs = record.get("outputs")
            signature = record.get("signature")
            if isinstance(outputs, dict) and isinstance(signature, str) and requested.intersection(outputs):
                context[f"@stage:{stage_name}"] = signature
        return dict(sorted(context.items()))

    def _save(self) -> None:
        write_json(self.path, self.data)
