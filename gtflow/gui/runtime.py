from __future__ import annotations

import io
import csv
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional

from gtflow.config import AppConfig, ProviderConfig
from gtflow.cost import Usage, estimate_cost
from gtflow.models.schemas import AxialTriple, Codebook, OpenCodingItem, Segment, Theory
from gtflow.pipeline.analytics import build_analysis_bundle
from gtflow.pipeline.axial_coder import build_axial
from gtflow.pipeline.codebook_builder import build_codebook
from gtflow.pipeline.evidence import build_evidence_catalog
from gtflow.pipeline.gioia_view import to_gioia
from gtflow.pipeline.negatives_scanner import scan_negatives
from gtflow.pipeline.open_coder import run_open_coding, run_open_coding_streaming
from gtflow.pipeline.quality import build_quality_audit
from gtflow.pipeline.report_html import emit_html
from gtflow.pipeline.saturation import saturation_suite
from gtflow.pipeline.segmenter import segment_dialog, segment_line, segment_paragraph
from gtflow.pipeline.selective_coder import build_theory
from gtflow.providers.base import make_provider
from gtflow.rate_limiter import TokenBucket
from gtflow.utils.file_io import ensure_dir, write_json
from gtflow.utils.jsonl_utils import iter_jsonl


SENSITIVE_HEADER_TOKENS = (
    "auth",
    "key",
    "token",
    "secret",
    "authorization",
    "cookie",
    "credential",
    "password",
    "session",
    "signature",
)


@dataclass
class PipelineArtifacts:
    segments: List[Segment]
    open_items: List[OpenCodingItem]
    codebook: Codebook
    triples: List[AxialTriple]
    theory: Theory
    negatives: List[Dict[str, Any]]
    saturation: Dict[str, Any]
    saturation_metrics: Dict[str, Any]
    analytics: Dict[str, Any]
    run_meta: Dict[str, Any]
    # Defaults keep older local integrations able to construct artifacts while
    # current pipeline runs always populate both audit payloads explicitly.
    evidence_catalog: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)


def default_config() -> AppConfig:
    return AppConfig()


def build_config(payload: Dict[str, Any]) -> AppConfig:
    data: Dict[str, Any] = {}
    if isinstance(payload.get("provider"), dict):
        data["provider"] = payload["provider"]
    if isinstance(payload.get("run"), dict):
        data["run"] = payload["run"]
    if isinstance(payload.get("output"), dict):
        data["output"] = payload["output"]
    return AppConfig.model_validate(data)


def segment_text(text: str, strategy: str, max_chars: int) -> List[Segment]:
    if strategy == "dialog":
        return segment_dialog(text, max_chars)
    if strategy == "paragraph":
        return segment_paragraph(text, max_chars)
    return segment_line(text, max_chars)


def source_segments(text: str, source_name: str, strategy: str, max_chars: int) -> List[Segment]:
    if not text.strip():
        return []
    if _is_structured_source(source_name):
        structured = _load_structured_segments_from_text(text, source_name, strategy, max_chars)
        if structured:
            return structured
    return segment_text(text, strategy, max_chars)


def _is_structured_source(source_name: str) -> bool:
    lowered = (source_name or "").split("?", 1)[0].lower()
    return lowered.endswith(".jsonl") or lowered.endswith(".csv")


def _load_structured_segments_from_text(
    text: str,
    source_name: str,
    strategy: str,
    max_chars: int,
) -> List[Segment]:
    lowered = (source_name or "").lower()
    if lowered.endswith(".jsonl"):
        records: List[Dict[str, Any]] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {exc.msg}") from exc
            if isinstance(record, dict):
                records.append(record)
        return _segments_from_structured_records(records, strategy, max_chars)

    if lowered.endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
            if not reader.fieldnames:
                return []
            return _segments_from_structured_records((dict(row) for row in reader), strategy, max_chars)
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV input: {exc}") from exc

    return []


def _segments_from_structured_records(
    records: Any,
    strategy: str,
    max_chars: int,
) -> List[Segment]:
    from gtflow.utils import text_utils

    segments: List[Segment] = []
    seen_ids: set[str] = set()

    def unique_seg_id(candidate: str) -> str:
        base = candidate or "seg"
        seg_id = base
        counter = 2
        while seg_id in seen_ids:
            seg_id = f"{base}-{counter}"
            counter += 1
        seen_ids.add(seg_id)
        return seg_id

    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        raw_text = record.get("text") or record.get("content") or record.get("utterance")
        if raw_text is None:
            continue
        segment_text_value = str(raw_text).strip()
        if not segment_text_value:
            continue

        base_id = record.get("seg_id") or record.get("id") or record.get("ID") or record.get("Id")
        base_id_str = str(base_id).strip() if base_id is not None else ""
        speaker = record.get("speaker") or record.get("role")
        speaker_str = str(speaker).strip() if speaker is not None and str(speaker).strip() else None
        meta = _coerce_record_meta(record.get("meta"))
        for key, value in record.items():
            if key in ("seg_id", "id", "ID", "Id", "text", "content", "utterance", "speaker", "role", "meta"):
                continue
            if value is not None:
                meta[str(key)] = str(value)
        if base_id_str:
            meta.setdefault("source_id", base_id_str)
        meta.setdefault("source_row", str(idx))

        if strategy == "dialog" and speaker_str is None:
            chunks = text_utils.split_dialog(segment_text_value, max_chars)
        elif strategy == "paragraph":
            chunks = [(speaker_str, chunk) for chunk in text_utils.split_paragraph(segment_text_value, max_chars)]
        elif strategy == "line":
            chunks = [(speaker_str, chunk) for chunk in text_utils.split_lines(segment_text_value, max_chars)]
        else:
            chunks = [(speaker_str, chunk) for chunk in text_utils.chunk_split(segment_text_value, max_chars)]

        for part_idx, (part_speaker, part_text) in enumerate(chunks, start=1):
            part_text = str(part_text).strip()
            if not part_text:
                continue
            if base_id_str:
                candidate = base_id_str if len(chunks) == 1 else f"{base_id_str}-{part_idx:02d}"
            else:
                candidate = f"{idx:04d}" if len(chunks) == 1 else f"{idx:04d}-{part_idx:02d}"
            segments.append(
                Segment(
                    seg_id=unique_seg_id(candidate),
                    text=part_text,
                    speaker=part_speaker or speaker_str,
                    meta=dict(meta),
                )
            )

    return segments


def _coerce_record_meta(meta_value: Any) -> Dict[str, str]:
    if meta_value is None:
        return {}
    if isinstance(meta_value, dict):
        return {str(k): str(v) for k, v in meta_value.items() if k is not None and v is not None}
    if isinstance(meta_value, str):
        try:
            parsed = json.loads(meta_value)
        except Exception:
            return {"meta": meta_value}
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if k is not None and v is not None}
        return {"meta": meta_value}
    return {"meta": str(meta_value)}


def readiness_state(
    conf: AppConfig,
    text: str,
    source_name: str = "",
    *,
    credential_configured: bool = False,
) -> Dict[str, Any]:
    provider = conf.provider
    has_input = bool(text.strip())
    has_model = bool((provider.model or "").strip())
    provider_name = (provider.name or "").lower()
    needs_key = provider_name in ("openai_compatible", "openai", "azure_openai", "anthropic")
    # Preview requests deliberately omit the credential.  The UI sends only a
    # boolean hint so readiness can still be accurate without echoing secrets
    # through a high-frequency endpoint.
    has_key = bool(provider.api_key) or credential_configured
    if provider_name in ("openai_compatible", "openai"):
        # Environment credentials are only eligible when routing also comes from
        # trusted defaults/environment. A request-selected endpoint needs its own key.
        has_key = has_key or (not provider.base_url and bool(os.getenv("OPENAI_API_KEY")))
    elif provider_name == "azure_openai":
        has_key = has_key or (not provider.endpoint and bool(os.getenv("AZURE_OPENAI_API_KEY")))
        has_endpoint = bool(provider.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT"))
        has_deployment = bool(provider.deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT"))
        has_key = has_key and has_endpoint and has_deployment
    elif provider_name == "anthropic":
        has_key = has_key or bool(os.getenv("ANTHROPIC_API_KEY"))
    provider_ready = has_model and (has_key or not needs_key)
    return {
        "input": has_input,
        "provider": provider_ready,
        "ready": has_input and provider_ready,
        "segments": len(source_segments(text, source_name, conf.run.segmentation_strategy, conf.run.max_segment_chars))
        if has_input
        else 0,
    }


def report_stats(artifacts: PipelineArtifacts) -> Dict[str, int]:
    return {
        "segments": len(artifacts.segments),
        "open_codes": len(artifacts.open_items),
        "initial_codes": sum(len(item.initial_codes) for item in artifacts.open_items),
        "codebook_entries": len(artifacts.codebook.entries),
        "triples": len(artifacts.triples),
    }


def build_run_meta(conf: AppConfig, totals: Dict[str, int]) -> Dict[str, Any]:
    price_in = conf.provider.price_input_per_1k
    price_out = conf.provider.price_output_per_1k
    cost = estimate_cost(
        Usage(totals.get("input_tokens", 0), totals.get("output_tokens", 0)),
        price_in,
        price_out,
    )
    return {
        "totals": {
            "input_tokens": totals.get("input_tokens", 0),
            "output_tokens": totals.get("output_tokens", 0),
            "total_tokens": totals.get("total_tokens", 0),
            "estimated_cost": round(cost, 6) if cost is not None else None,
        }
    }


def run_pipeline(
    conf: AppConfig,
    text: str,
    progress: Optional[Callable[[int, str], None]] = None,
    source_name: str = "",
    cancel_event: Optional[Any] = None,
) -> PipelineArtifacts:
    def tick(value: int, label: str) -> None:
        if progress:
            progress(value, label)

    tick(5, "Segmenting text")
    segments = source_segments(text, source_name, conf.run.segmentation_strategy, conf.run.max_segment_chars)
    segment_dicts = [segment.model_dump() for segment in segments]

    provider = make_provider(conf.provider)
    provider.reset_usage_totals()
    if cancel_event is not None:
        provider.cancel_event = cancel_event
    rate_limiter = TokenBucket(conf.run.rate_limit_rps) if conf.run.rate_limit_rps else None

    tick(20, "Open coding")
    if conf.run.stream_open_coding or len(segments) >= conf.run.stream_open_coding_threshold:
        tmpdir = tempfile.mkdtemp(prefix="gtflow_open_")
        try:
            open_jsonl = os.path.join(tmpdir, "open_codes.jsonl")
            run_open_coding_streaming(
                provider,
                segment_dicts,
                output_path=open_jsonl,
                batch_size=conf.run.batch_size,
                max_prompt_chars=conf.run.max_prompt_chars,
                max_retries=conf.run.retry_max,
                timeout_sec=conf.run.timeout_sec,
                rate_limiter=rate_limiter,
                sample_limit=300,
                output_language=conf.provider.output_language,
            )
            open_items = [OpenCodingItem.model_validate(record) for record in iter_jsonl(open_jsonl)]
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        open_items = run_open_coding(
            provider,
            segment_dicts,
            batch_size=conf.run.batch_size,
            max_prompt_chars=conf.run.max_prompt_chars,
            max_retries=conf.run.retry_max,
            timeout_sec=conf.run.timeout_sec,
            rate_limiter=rate_limiter,
            max_concurrency=max(conf.run.concurrent_workers, 1),
            output_language=conf.provider.output_language,
        )

    evidence_catalog = build_evidence_catalog(segments, open_items)

    tick(40, "Building codebook")
    codebook = build_codebook(
        provider,
        open_items,
        timeout_sec=conf.run.timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=conf.run.retry_max,
        output_language=conf.provider.output_language,
    )

    tick(60, "Axial coding")
    triples = build_axial(
        provider,
        codebook,
        timeout_sec=conf.run.timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=conf.run.retry_max,
        output_language=conf.provider.output_language,
        evidence_catalog=evidence_catalog,
    )

    tick(75, "Selective coding")
    theory = build_theory(
        provider,
        triples,
        timeout_sec=conf.run.timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=conf.run.retry_max,
        output_language=conf.provider.output_language,
        evidence_catalog=evidence_catalog,
    )

    tick(88, "Negative cases and saturation")
    validation_events: List[Dict[str, Any]] = []
    negatives = scan_negatives(
        provider,
        segment_dicts,
        theory.storyline,
        timeout_sec=conf.run.timeout_sec,
        rate_limiter=rate_limiter,
        max_retries=conf.run.retry_max,
        output_language=conf.provider.output_language,
        audit_log=validation_events,
    )
    sat_metrics = saturation_suite([item.model_dump() for item in open_items])
    analytics = build_analysis_bundle(segments, open_items, negatives)
    quality = build_quality_audit(
        segments,
        open_items,
        codebook,
        triples,
        negatives,
        validation_events=validation_events,
    )
    run_meta = build_run_meta(conf, provider.total_usage())
    run_meta["attempts"] = provider.attempt_telemetry()

    tick(100, "Complete")
    return PipelineArtifacts(
        segments=segments,
        open_items=open_items,
        codebook=codebook,
        triples=triples,
        theory=theory,
        negatives=negatives,
        saturation=sat_metrics["default"],
        saturation_metrics=sat_metrics,
        analytics=analytics,
        evidence_catalog=evidence_catalog,
        quality=quality,
        run_meta=run_meta,
    )


def artifacts_response(artifacts: PipelineArtifacts, bundle: Optional[bytes] = None) -> Dict[str, Any]:
    response = {
        "stats": report_stats(artifacts),
        "segments": [segment.model_dump() for segment in artifacts.segments[:300]],
        "open_items": [item.model_dump() for item in artifacts.open_items[:300]],
        "codebook": artifacts.codebook.model_dump(),
        "triples": [triple.model_dump() for triple in artifacts.triples],
        "theory": artifacts.theory.model_dump(),
        "negatives": artifacts.negatives,
        "saturation": artifacts.saturation,
        "saturation_metrics": artifacts.saturation_metrics,
        "analytics": artifacts.analytics,
        "evidence_catalog": artifacts.evidence_catalog,
        "quality": artifacts.quality,
        "run_meta": artifacts.run_meta,
        "gioia": to_gioia(artifacts.codebook),
    }
    if bundle is not None:
        import base64

        response["bundle_base64"] = base64.b64encode(bundle).decode("ascii")
    return response


def rebuild_artifacts_with_codebook(artifacts: PipelineArtifacts, codebook: Codebook) -> PipelineArtifacts:
    """Replace an edited codebook and refresh deterministic audit fields."""

    quality = build_quality_audit(
        artifacts.segments,
        artifacts.open_items,
        codebook,
        artifacts.triples,
        artifacts.negatives,
        validation_events=artifacts.quality.get("validation_events", []),
    )
    return replace(artifacts, codebook=codebook, quality=quality)


def output_bundle(conf: AppConfig, artifacts: PipelineArtifacts) -> bytes:
    tmpdir = tempfile.mkdtemp(prefix="gtflow_")
    try:
        ensure_dir(tmpdir)
        write_json(os.path.join(tmpdir, "segments.json"), [s.model_dump() for s in artifacts.segments])
        write_json(os.path.join(tmpdir, "open_codes.json"), [item.model_dump() for item in artifacts.open_items])
        write_json(os.path.join(tmpdir, "codebook.json"), artifacts.codebook.model_dump())
        write_json(os.path.join(tmpdir, "axial_triples.json"), [triple.model_dump() for triple in artifacts.triples])
        write_json(os.path.join(tmpdir, "theory.json"), artifacts.theory.model_dump())
        write_json(os.path.join(tmpdir, "gioia.json"), to_gioia(artifacts.codebook))
        write_json(os.path.join(tmpdir, "negatives.json"), artifacts.negatives)
        write_json(os.path.join(tmpdir, "saturation.json"), artifacts.saturation)
        write_json(os.path.join(tmpdir, "saturation_metrics.json"), artifacts.saturation_metrics)
        write_json(os.path.join(tmpdir, "analytics.json"), artifacts.analytics)
        write_json(os.path.join(tmpdir, "evidence_catalog.json"), artifacts.evidence_catalog)
        write_json(os.path.join(tmpdir, "quality.json"), artifacts.quality)
        write_json(os.path.join(tmpdir, "run_meta.json"), artifacts.run_meta)
        emit_html(
            os.path.join(tmpdir, "report.html"),
            report_stats(artifacts),
            to_gioia(artifacts.codebook),
            [triple.model_dump() for triple in artifacts.triples],
            artifacts.open_items,
            artifacts.codebook,
            analytics=artifacts.analytics,
            saturation_metrics=artifacts.saturation_metrics,
            theory=artifacts.theory,
            quality=artifacts.quality,
            run_meta=artifacts.run_meta,
            evidence_catalog=artifacts.evidence_catalog,
        )
        save_config_snippet(conf, tmpdir)
        return zip_dir(tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def zip_dir(dirpath: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        for filename in os.listdir(dirpath):
            zipped.write(os.path.join(dirpath, filename), arcname=filename)
    return buffer.getvalue()


def save_config_snippet(conf: AppConfig, dirpath: str) -> None:
    data = conf.model_dump(mode="python")
    provider = data.get("provider")
    if isinstance(provider, dict):
        provider["api_key"] = None
        headers = provider.get("extra_headers")
        if isinstance(headers, dict):
            provider["extra_headers"] = {
                k: ("***redacted***" if is_sensitive_header(k) else v)
                for k, v in headers.items()
            }
    write_json(os.path.join(dirpath, "config.used.json"), data)


def is_sensitive_header(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in SENSITIVE_HEADER_TOKENS)
