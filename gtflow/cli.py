
from __future__ import annotations
import csv, json, os, pathlib, asyncio, time, itertools
from contextlib import contextmanager
from typing import Optional
import typer, yaml
from rich.table import Table
from .config import AppConfig
from .logging import console
from .utils.file_io import read_text, write_json, write_text, ensure_dir, write_csv, read_json
from .utils.jsonl_utils import iter_jsonl, count_jsonl
from .providers.base import make_provider
from .pipeline.segmenter import segment_dialog, segment_paragraph, segment_line
from .pipeline.open_coder import run_open_coding, run_open_coding_streaming
from .pipeline.codebook_builder import build_codebook
from .pipeline.evidence import build_evidence_catalog
from .pipeline.axial_coder import build_axial
from .pipeline.selective_coder import build_theory
from .pipeline.gioia_view import to_gioia
from .pipeline.negatives_scanner import scan_negatives
from .pipeline.saturation import saturation_suite
from .pipeline.analytics import build_analysis_bundle
from .pipeline.quality import build_quality_audit
from .pipeline.stage_manifest import StageManifest, normalized_config, select_open_codes_path, sha256_file
from .pipeline.project_ops import compare_projects as compare_project_dirs, merge_projects as merge_project_dirs
from .pipeline.report_html import emit_html
from .rate_limiter import TokenBucket
from .models.schemas import Segment, Theory
from .cost import Usage, estimate_cost

app = typer.Typer(help="GTFlow grounded theory pipeline")


def _estimated_cost(input_tokens: int, output_tokens: int, price_in: Optional[float], price_out: Optional[float]) -> Optional[float]:
    cost = estimate_cost(Usage(input_tokens, output_tokens), price_in, price_out)
    return round(cost, 6) if cost is not None else None


def _format_cost(value) -> str:
    return "" if value is None else str(value)

def _load_segments_from_structured_input(
    input_path: str, strategy: str, max_segment_chars: int
) -> list[Segment]:
    if not (input_path.lower().endswith(".jsonl") or input_path.lower().endswith(".csv")):
        return []

    from .utils import text_utils

    segments: list[Segment] = []
    seen_ids: set[str] = set()

    def _unique_seg_id(candidate: str) -> str:
        base = candidate or "seg"
        seg_id = base
        counter = 2
        while seg_id in seen_ids:
            seg_id = f"{base}-{counter}"
            counter += 1
        seen_ids.add(seg_id)
        return seg_id

    def _coerce_meta(meta_value: object) -> dict[str, str]:
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

    def _consume_records(record_iter) -> None:
        for idx, rec in enumerate(record_iter, start=1):
            if not isinstance(rec, dict):
                continue

            raw_text = rec.get("text") or rec.get("content") or rec.get("utterance")
            if raw_text is None:
                continue
            text = str(raw_text).strip()
            if not text:
                continue

            base_id = rec.get("seg_id") or rec.get("id") or rec.get("ID") or rec.get("Id")
            base_id_str = str(base_id).strip() if base_id is not None else ""
            speaker = rec.get("speaker") or rec.get("role")
            speaker_str = (
                str(speaker).strip()
                if speaker is not None and str(speaker).strip()
                else None
            )

            meta = _coerce_meta(rec.get("meta"))
            for k, v in rec.items():
                if k in ("seg_id", "id", "ID", "Id", "text", "content", "utterance", "speaker", "role", "meta"):
                    continue
                if v is None:
                    continue
                meta[str(k)] = str(v)
            if base_id_str:
                meta.setdefault("source_id", base_id_str)
            meta.setdefault("source_row", str(idx))

            chunks: list[tuple[Optional[str], str]] = []
            if strategy == "dialog" and speaker_str is None:
                chunks = text_utils.split_dialog(text, max_segment_chars)
            elif strategy == "paragraph":
                chunks = [
                    (speaker_str, c)
                    for c in text_utils.split_paragraph(text, max_segment_chars)
                ]
            elif strategy == "line":
                chunks = [
                    (speaker_str, c)
                    for c in text_utils.split_lines(text, max_segment_chars)
                ]
            else:
                chunks = [
                    (speaker_str, c)
                    for c in text_utils.chunk_split(text, max_segment_chars)
                ]

            if not chunks:
                continue

            for part_idx, (part_speaker, part_text) in enumerate(chunks, start=1):
                part_text = str(part_text).strip()
                if not part_text:
                    continue
                if base_id_str:
                    candidate = (
                        base_id_str
                        if len(chunks) == 1
                        else f"{base_id_str}-{part_idx:02d}"
                    )
                else:
                    candidate = (
                        f"{idx:04d}"
                        if len(chunks) == 1
                        else f"{idx:04d}-{part_idx:02d}"
                    )
                seg_id = _unique_seg_id(candidate)
                segments.append(
                    Segment(
                        seg_id=seg_id,
                        text=part_text,
                        speaker=part_speaker or speaker_str,
                        meta=dict(meta),
                    )
                )

    if input_path.lower().endswith(".jsonl"):
        _consume_records(r for r in iter_jsonl(input_path) if isinstance(r, dict))
    else:
        with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
            _consume_records(dict(r) for r in csv.DictReader(f))

    return segments


def _load_segments(input_path: str, strategy: str, max_segment_chars: int) -> list[Segment]:
    structured = _load_segments_from_structured_input(input_path, strategy, max_segment_chars)
    if structured:
        return structured

    text = read_text(input_path)
    if strategy == "dialog":
        return segment_dialog(text, max_segment_chars)
    if strategy == "paragraph":
        return segment_paragraph(text, max_segment_chars)
    return segment_line(text, max_segment_chars)


def _load_config(config_path: Optional[str]) -> AppConfig:
    if not config_path:
        return AppConfig()
    if not os.path.exists(config_path):
        raise typer.BadParameter(f"Config file not found: {config_path}")
    if config_path.endswith(".json"):
        data = json.loads(read_text(config_path))
    else:
        data = yaml.safe_load(read_text(config_path))
    return AppConfig.model_validate(data)

def _stage_header(name: str):
    console.rule(f"[info]{name}[/info]")


def _iter_open_codes(open_json: str, open_jsonl: str):
    from .models.schemas import OpenCodingItem
    selected = select_open_codes_path(os.path.dirname(os.path.abspath(open_json)))
    if selected == os.path.abspath(open_jsonl):
        for rec in iter_jsonl(selected):
            yield OpenCodingItem.model_validate(rec)
    elif selected == os.path.abspath(open_json):
        for rec in read_json(selected):
            yield OpenCodingItem.model_validate(rec)


def _sample_open_codes(open_json: str, open_jsonl: str, limit: int = 200):
    return list(itertools.islice(_iter_open_codes(open_json, open_jsonl), limit))

@app.command()
def segment(
    input_path: str = typer.Option(..., "-i", help="Input text file"),
    out_dir: str = typer.Option("output", "-o", help="Output directory"),
    strategy: str = typer.Option("dialog", help="dialog|paragraph|line"),
    max_segment_chars: int = typer.Option(800, help="Maximum characters per segment")
):
    ensure_dir(out_dir)
    segs = _load_segments(input_path, strategy, max_segment_chars)
    write_json(os.path.join(out_dir, "segments.json"), [s.model_dump() for s in segs])
    from .utils.jsonl_utils import write_jsonl
    write_jsonl(os.path.join(out_dir, "segments.jsonl"), (s.model_dump() for s in segs))
    console.print(f"[ok] Segmented {len(segs)} segments -> {out_dir}/segments.json")

@app.command()
def run_all(
    input_path: str = typer.Option(..., "-i"),
    config_path: str = typer.Option(..., "-c"),
    out_dir: str = typer.Option("output", "-o"),
    force: bool = typer.Option(False, "--force/--no-force")
):
    conf = _load_config(config_path)
    conf.output.out_dir = out_dir
    ensure_dir(out_dir)
    rate_limiter = TokenBucket(conf.run.rate_limit_rps) if conf.run.rate_limit_rps else None

    safe_config = normalized_config(conf)
    input_sha256 = sha256_file(input_path)
    stage_manifest = StageManifest(out_dir)
    stage_manifest.begin_run(
        input_path=input_path,
        input_sha256=input_sha256,
        config=safe_config,
    )
    cache_hits: list[str] = []

    @contextmanager
    def tracked_stage(
        name: str,
        output_paths: list[str],
        *,
        upstream_paths: Optional[list[str]] = None,
        cleanup_paths: Optional[list[str]] = None,
        allow_reuse: bool = True,
    ):
        signature, upstream, definition = stage_manifest.signature(
            name,
            input_sha256=input_sha256,
            config=safe_config,
            upstream_paths=upstream_paths or [],
        )
        if allow_reuse and not force and stage_manifest.can_reuse(name, signature, output_paths):
            cache_hits.append(name)
            yield False, {}
            return

        stage_manifest.mark_running(
            name,
            signature=signature,
            upstream=upstream,
            definition_fingerprint=definition,
        )
        for path in cleanup_paths or output_paths:
            if os.path.isfile(path):
                os.remove(path)
        details: dict = {}
        try:
            yield True, details
        except BaseException as exc:
            stage_manifest.mark_failed(name, exc)
            stage_manifest.finish_run(counts={}, status="failed")
            raise
        else:
            stage_manifest.mark_complete(
                name,
                output_paths=output_paths,
                counts=details.get("counts"),
                metadata=details.get("metadata"),
            )

    run_meta = {
        "stages": {},
        "totals": {},
        "provenance": {
            "project_id": stage_manifest.project_id,
            "stage_manifest": "stage_manifest.json",
            "input_sha256": input_sha256,
        },
        "cache_hits": cache_hits,
    }
    price_in = conf.provider.price_input_per_1k
    price_out = conf.provider.price_output_per_1k
    output_language = getattr(conf.provider, "output_language", None) or "English"

    segments_count = 0
    open_codes_count = None

    # 1) Segment
    _stage_header("Segment")
    seg_json = os.path.join(out_dir, "segments.json")
    seg_jsonl = os.path.join(out_dir, "segments.jsonl")
    with tracked_stage("segment", [seg_json, seg_jsonl]) as (execute, details):
        if execute:
            strat = conf.run.segmentation_strategy
            segs = _load_segments(input_path, strat, conf.run.max_segment_chars)
            write_json(seg_json, [s.model_dump() for s in segs])
            # also emit jsonl for large runs
            from .utils.jsonl_utils import write_jsonl
            write_jsonl(seg_jsonl, (s.model_dump() for s in segs))
            details["counts"] = {"segments": len(segs)}
        else:
            segs = [Segment.model_validate(x) for x in read_json(seg_json)]
    segments_count = len(segs)
    console.print(f"[ok] segments: {segments_count}")

    # provider
    provider = make_provider(conf.provider)
    provider.reset_usage_totals()

    # helper for per-stage usage delta
    def usage_delta(before):
        after = provider.total_usage()
        input_tokens = after["input_tokens"] - before["input_tokens"]
        output_tokens = after["output_tokens"] - before["output_tokens"]
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": after["total_tokens"] - before["total_tokens"],
            "estimated_cost": _estimated_cost(input_tokens, output_tokens, price_in, price_out),
        }

    # 2) Open coding
    _stage_header("Open Coding")
    open_json = os.path.join(out_dir, "open_codes.json")
    open_jsonl = os.path.join(out_dir, "open_codes.jsonl")
    stream_open_coding = conf.run.stream_open_coding or len(segs) >= conf.run.stream_open_coding_threshold
    open_outputs = [open_json, open_jsonl] if stream_open_coding else [open_json]
    with tracked_stage(
        "open_coding",
        open_outputs,
        upstream_paths=[seg_json, seg_jsonl],
        # Delete both formats before every rerun. A stale streamed artifact must
        # never override a new non-streamed dataset in the same directory.
        cleanup_paths=[open_json, open_jsonl],
    ) as (execute, details):
        if execute:
            seg_iter = (s.model_dump() for s in segs)
            before = provider.total_usage()
            if stream_open_coding:
                total, sample = run_open_coding_streaming(
                    provider,
                    seg_iter,
                    output_path=open_jsonl,
                    batch_size=conf.run.batch_size,
                    max_prompt_chars=conf.run.max_prompt_chars,
                    max_retries=conf.run.retry_max,
                    timeout_sec=conf.run.timeout_sec,
                    rate_limiter=rate_limiter,
                    sample_limit=200,
                    output_language=output_language,
                )
                console.print(f"[ok] open coding (streamed) items: {total}")
                write_json(open_json, [x.model_dump() for x in sample])
                open_codes_count = total
            else:
                seg_dicts = list(seg_iter)
                items = run_open_coding(
                    provider,
                    seg_dicts,
                    batch_size=conf.run.batch_size,
                    max_prompt_chars=conf.run.max_prompt_chars,
                    max_retries=conf.run.retry_max,
                    timeout_sec=conf.run.timeout_sec,
                    rate_limiter=rate_limiter,
                    max_concurrency=max(conf.run.concurrent_workers, 1),
                    output_language=output_language,
                )
                write_json(open_json, [x.model_dump() for x in items])
                open_codes_count = len(items)
            run_meta["stages"]["open_coding"] = usage_delta(before)
            run_meta["stages"]["open_coding"]["items"] = open_codes_count
            details["counts"] = {"items": int(open_codes_count or 0)}
            details["metadata"] = {
                "primary_output": "open_codes.jsonl" if stream_open_coding else "open_codes.json",
                "streamed": stream_open_coding,
            }
        elif stream_open_coding:
            open_codes_count = count_jsonl(open_jsonl)
        else:
            open_codes_count = len(read_json(open_json))

    # Canonical evidence context shared by axial/selective coding and audits.
    evidence_catalog_json = os.path.join(out_dir, "evidence_catalog.json")
    with tracked_stage(
        "evidence",
        [evidence_catalog_json],
        upstream_paths=[seg_json, *open_outputs],
    ) as (execute, details):
        if execute:
            evidence_catalog = build_evidence_catalog(segs, _iter_open_codes(open_json, open_jsonl))
            write_json(evidence_catalog_json, evidence_catalog)
            details["counts"] = {"evidence": len(evidence_catalog)}
        else:
            evidence_catalog = read_json(evidence_catalog_json)

    # 3) Codebook
    _stage_header("Codebook")
    codebook_json = os.path.join(out_dir, "codebook.json")
    with tracked_stage(
        "codebook",
        [codebook_json],
        upstream_paths=open_outputs,
    ) as (execute, details):
        if execute:
            items = _iter_open_codes(open_json, open_jsonl)
            before = provider.total_usage()
            codebook = build_codebook(
                provider,
                items,
                timeout_sec=conf.run.timeout_sec,
                rate_limiter=rate_limiter,
                max_retries=conf.run.retry_max,
                output_language=output_language,
            )
            write_json(codebook_json, codebook.model_dump())
            run_meta["stages"]["codebook"] = usage_delta(before)
            details["counts"] = {"entries": len(codebook.entries)}

    # 4) Axial triples
    _stage_header("Axial Coding")
    triples_json = os.path.join(out_dir, "axial_triples.json")
    with tracked_stage(
        "axial",
        [triples_json],
        upstream_paths=[codebook_json, evidence_catalog_json],
    ) as (execute, details):
        if execute:
            from .models.schemas import Codebook
            codebook = Codebook.model_validate(read_json(codebook_json))
            before = provider.total_usage()
            triples = build_axial(
                provider,
                codebook,
                timeout_sec=conf.run.timeout_sec,
                rate_limiter=rate_limiter,
                max_retries=conf.run.retry_max,
                output_language=output_language,
                evidence_catalog=evidence_catalog,
            )
            write_json(triples_json, [t.model_dump() for t in triples])
            run_meta["stages"]["axial"] = usage_delta(before)
            details["counts"] = {"triples": len(triples)}

    # 5) Theory
    _stage_header("Selective Coding / Theory")
    theory_json = os.path.join(out_dir, "theory.json")
    theory_md = os.path.join(out_dir, "theory.md")
    with tracked_stage(
        "theory",
        [theory_json, theory_md],
        upstream_paths=[triples_json, evidence_catalog_json],
    ) as (execute, details):
        if execute:
            from .models.schemas import AxialTriple
            triples = [AxialTriple.model_validate(x) for x in read_json(triples_json)]
            before = provider.total_usage()
            theory = build_theory(
                provider,
                triples,
                timeout_sec=conf.run.timeout_sec,
                rate_limiter=rate_limiter,
                max_retries=conf.run.retry_max,
                output_language=output_language,
                evidence_catalog=evidence_catalog,
            )
            write_json(theory_json, theory.model_dump())
            write_text(
                theory_md,
                f"# Core Category\n\n{theory.core_category}\n\n"
                f"## Rationale\n\n{theory.rationale or ''}\n\n"
                f"## Storyline\n\n{theory.storyline}\n",
            )
            run_meta["stages"]["theory"] = usage_delta(before)
            details["counts"] = {"theories": 1}

    # 6) Gioia
    _stage_header("Gioia View")
    gioia_json = os.path.join(out_dir, "gioia.json")
    with tracked_stage(
        "gioia",
        [gioia_json],
        upstream_paths=[codebook_json],
    ) as (execute, details):
        if execute:
            from .models.schemas import Codebook
            codebook = Codebook.model_validate(read_json(codebook_json))
            gioia = to_gioia(codebook)
            write_json(gioia_json, gioia)
            details["counts"] = {"entries": len(codebook.entries)}

    # 7) Negatives
    _stage_header("Negative Cases")
    negatives_json = os.path.join(out_dir, "negatives.json")
    validation_events = []
    with tracked_stage(
        "negatives",
        [negatives_json],
        upstream_paths=[seg_json, theory_json, evidence_catalog_json],
    ) as (execute, details):
        if execute:
            tho = read_json(theory_json)
            before = provider.total_usage()
            seg_dicts = [s.model_dump() for s in segs]
            negs = scan_negatives(
                provider,
                seg_dicts,
                tho.get("storyline",""),
                timeout_sec=conf.run.timeout_sec,
                rate_limiter=rate_limiter,
                max_retries=conf.run.retry_max,
                output_language=output_language,
                audit_log=validation_events,
            )
            write_json(negatives_json, negs)
            run_meta["stages"]["negatives"] = usage_delta(before)
            details["counts"] = {"negative_cases": len(negs)}

    # 8) Saturation
    _stage_header("Analytics")
    analytics_json = os.path.join(out_dir, "analytics.json")
    with tracked_stage(
        "analytics",
        [analytics_json],
        upstream_paths=[seg_json, *open_outputs, negatives_json],
    ) as (execute, details):
        if execute:
            open_items_full = list(_iter_open_codes(open_json, open_jsonl))
            negatives_for_analytics = read_json(negatives_json) if os.path.exists(negatives_json) else []
            analytics = build_analysis_bundle(segs, open_items_full, negatives_for_analytics)
            write_json(analytics_json, analytics)
            details["counts"] = {"open_codes": len(open_items_full)}

    _stage_header("Saturation")
    saturation_json = os.path.join(out_dir, "saturation.json")
    saturation_metrics_json = os.path.join(out_dir, "saturation_metrics.json")
    with tracked_stage(
        "saturation",
        [saturation_json, saturation_metrics_json],
        upstream_paths=open_outputs,
    ) as (execute, details):
        if execute:
            if stream_open_coding:
                oc_iter = iter_jsonl(open_jsonl)
            else:
                oc_iter = read_json(open_json)
            sat_metrics = saturation_suite(oc_iter)
            write_json(saturation_json, sat_metrics["default"])
            write_json(saturation_metrics_json, sat_metrics)
            details["counts"] = {"windows": len(sat_metrics.get("default", [])) if isinstance(sat_metrics.get("default"), list) else 1}

    # 9) Cross-artifact grounding audit
    _stage_header("Quality Audit")
    quality_json = os.path.join(out_dir, "quality.json")
    with tracked_stage(
        "quality",
        [quality_json],
        upstream_paths=[
            seg_json,
            *open_outputs,
            evidence_catalog_json,
            codebook_json,
            triples_json,
            negatives_json,
        ],
    ) as (execute, details):
        if execute:
            from .models.schemas import AxialTriple, Codebook

            audit_open_items = list(_iter_open_codes(open_json, open_jsonl))
            audit_codebook = Codebook.model_validate(read_json(codebook_json))
            audit_triples = [AxialTriple.model_validate(x) for x in read_json(triples_json)]
            audit_negatives = read_json(negatives_json) if os.path.exists(negatives_json) else []
            quality_data = build_quality_audit(
                segs,
                audit_open_items,
                audit_codebook,
                audit_triples,
                audit_negatives,
                validation_events=validation_events,
            )
            write_json(quality_json, quality_data)
            details["counts"] = {"validation_events": len(validation_events)}
        else:
            quality_data = read_json(quality_json)

    # 10) HTML Report
    _stage_header("HTML Report")
    html_path = os.path.join(out_dir, "report.html")
    from .models.schemas import Codebook, AxialTriple, OpenCodingItem
    codebook = Codebook.model_validate(read_json(codebook_json))
    triples = [AxialTriple.model_validate(x) for x in read_json(triples_json)]
    open_items = [OpenCodingItem.model_validate(x) for x in _sample_open_codes(open_json, open_jsonl, limit=200)]
    if open_codes_count is None:
        if os.path.exists(open_jsonl):
            open_codes_count = count_jsonl(open_jsonl)
        elif os.path.exists(open_json):
            open_codes_count = len(read_json(open_json))
        else:
            open_codes_count = 0
    stats = {
        "segments": segments_count,
        "open_codes": open_codes_count,
        "codebook_entries": len(codebook.entries),
        "triples": len(triples),
    }
    analytics_data = read_json(analytics_json) if os.path.exists(analytics_json) else {}
    saturation_metrics_data = read_json(saturation_metrics_json) if os.path.exists(saturation_metrics_json) else {}
    theory_data = Theory.model_validate(read_json(theory_json))
    report_totals = provider.total_usage()
    run_meta["totals"] = {
        "input_tokens": report_totals["input_tokens"],
        "output_tokens": report_totals["output_tokens"],
        "total_tokens": report_totals["total_tokens"],
        "estimated_cost": _estimated_cost(
            report_totals["input_tokens"], report_totals["output_tokens"], price_in, price_out
        ),
    }
    if hasattr(provider, "attempt_telemetry"):
        run_meta["attempts"] = provider.attempt_telemetry()
    with tracked_stage(
        "report",
        [html_path],
        upstream_paths=[
            seg_json,
            *open_outputs,
            evidence_catalog_json,
            codebook_json,
            triples_json,
            theory_json,
            gioia_json,
            negatives_json,
            analytics_json,
            saturation_metrics_json,
            quality_json,
        ],
        # The report embeds current cache/provenance metadata and is cheap to
        # rebuild, so each invocation receives a truthful run summary.
        allow_reuse=False,
    ) as (execute, details):
        if execute:
            emit_html(
                html_path,
                stats,
                read_json(gioia_json),
                [t.model_dump() for t in triples],
                open_items,
                codebook,
                analytics=analytics_data,
                saturation_metrics=saturation_metrics_data,
                theory=theory_data,
                quality=quality_data,
                run_meta=run_meta,
                evidence_catalog=evidence_catalog,
            )
            details["counts"] = stats

    # totals
    totals = provider.total_usage()
    run_meta["totals"] = {
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "estimated_cost": _estimated_cost(totals["input_tokens"], totals["output_tokens"], price_in, price_out),
    }
    write_json(os.path.join(out_dir, "run_meta.json"), run_meta)
    stage_manifest.finish_run(counts=stats, status="complete")

    console.print(f"[ok] Done. See {out_dir}")
    # pretty table
    table = Table(title="Token Usage by Stage")
    table.add_column("Stage")
    table.add_column("Input")
    table.add_column("Output")
    table.add_column("Total")
    table.add_column("Est. Cost ($)")
    for k,v in run_meta["stages"].items():
        table.add_row(k, str(v["input_tokens"]), str(v["output_tokens"]), str(v["total_tokens"]), _format_cost(v["estimated_cost"]))
    table.add_row("ALL", str(run_meta["totals"]["input_tokens"]), str(run_meta["totals"]["output_tokens"]), str(run_meta["totals"]["total_tokens"]), _format_cost(run_meta["totals"]["estimated_cost"]))
    console.print(table)

def _emit_report_from_out_dir(
    out_dir: str,
    template_path: Optional[str] = None,
    methods: bool = True,
    results: bool = True,
    appendices: bool = True,
) -> None:
    codebook = read_json(os.path.join(out_dir, "codebook.json"))
    triples = read_json(os.path.join(out_dir, "axial_triples.json"))
    open_json = os.path.join(out_dir, "open_codes.json")
    open_jsonl = os.path.join(out_dir, "open_codes.jsonl")
    selected_open_codes = select_open_codes_path(out_dir)
    if selected_open_codes == os.path.abspath(open_jsonl):
        open_items = list(itertools.islice(iter_jsonl(selected_open_codes), 200))
        open_codes_count = count_jsonl(selected_open_codes)
    elif selected_open_codes == os.path.abspath(open_json):
        open_items = read_json(selected_open_codes)
        open_codes_count = len(open_items)
    else:
        open_items = []
        open_codes_count = 0
    segs = read_json(os.path.join(out_dir, "segments.json"))
    from .pipeline.report_html import emit_html
    stats = {
        "segments": len(segs),
        "open_codes": open_codes_count,
        "codebook_entries": len(codebook.get("entries",[])),
        "triples": len(triples),
    }
    from .pipeline.gioia_view import to_gioia
    from .models.schemas import Codebook
    analytics_path = os.path.join(out_dir, "analytics.json")
    saturation_metrics_path = os.path.join(out_dir, "saturation_metrics.json")
    negatives_path = os.path.join(out_dir, "negatives.json")
    negatives = read_json(negatives_path) if os.path.exists(negatives_path) else []
    analytics_data = (
        read_json(analytics_path)
        if os.path.exists(analytics_path)
        else build_analysis_bundle(segs, open_items, negatives)
    )
    saturation_metrics_data = (
        read_json(saturation_metrics_path)
        if os.path.exists(saturation_metrics_path)
        else saturation_suite(open_items)
    )
    codebook_model = Codebook.model_validate(codebook)
    theory_path = os.path.join(out_dir, "theory.json")
    quality_path = os.path.join(out_dir, "quality.json")
    evidence_catalog_path = os.path.join(out_dir, "evidence_catalog.json")
    run_meta_path = os.path.join(out_dir, "run_meta.json")
    theory_data = Theory.model_validate(read_json(theory_path)) if os.path.exists(theory_path) else None
    if os.path.exists(evidence_catalog_path):
        evidence_catalog = read_json(evidence_catalog_path)
    else:
        all_open_items = list(_iter_open_codes(open_json, open_jsonl))
        evidence_catalog = build_evidence_catalog(segs, all_open_items)
        write_json(evidence_catalog_path, evidence_catalog)
    if os.path.exists(quality_path):
        quality_data = read_json(quality_path)
    else:
        all_open_items = list(_iter_open_codes(open_json, open_jsonl))
        quality_data = build_quality_audit(
            segs,
            all_open_items,
            codebook_model,
            triples,
            negatives,
        )
        write_json(quality_path, quality_data)
    run_meta_data = read_json(run_meta_path) if os.path.exists(run_meta_path) else {}
    emit_html(
        os.path.join(out_dir, "report.html"),
        stats,
        to_gioia(codebook_model),
        triples,
        open_items,
        codebook_model,
        analytics=analytics_data,
        saturation_metrics=saturation_metrics_data,
        theory=theory_data,
        quality=quality_data,
        run_meta=run_meta_data,
        evidence_catalog=evidence_catalog,
        template_path=template_path,
        sections={"methods": methods, "results": results, "appendices": appendices},
    )


@app.command()
def html_report(
    out_dir: str = typer.Option("output", "-o"),
    template_path: Optional[str] = typer.Option(None, "--template", help="Optional Jinja2 report template"),
    methods: bool = typer.Option(True, "--methods/--no-methods"),
    results: bool = typer.Option(True, "--results/--no-results"),
    appendices: bool = typer.Option(True, "--appendices/--no-appendices"),
):
    _emit_report_from_out_dir(
        out_dir,
        template_path=template_path,
        methods=methods,
        results=results,
        appendices=appendices,
    )
    console.print(f"[ok] Wrote {out_dir}/report.html")


@app.command()
def report(
    out_dir: str = typer.Option("output", "-o"),
    template_path: Optional[str] = typer.Option(None, "--template", help="Optional Jinja2 report template"),
    methods: bool = typer.Option(True, "--methods/--no-methods"),
    results: bool = typer.Option(True, "--results/--no-results"),
    appendices: bool = typer.Option(True, "--appendices/--no-appendices"),
):
    """Alias for `html-report`."""
    _emit_report_from_out_dir(
        out_dir,
        template_path=template_path,
        methods=methods,
        results=results,
        appendices=appendices,
    )
    console.print(f"[ok] Wrote {out_dir}/report.html")


@app.command("compare-projects")
def compare_projects(
    left_dir: str = typer.Option(..., "--left"),
    right_dir: str = typer.Option(..., "--right"),
    out_path: Optional[str] = typer.Option(None, "-o", help="Optional JSON output path"),
):
    result = compare_project_dirs(left_dir, right_dir)
    if out_path:
        write_json(out_path, result)
        console.print(f"[ok] Wrote {out_path}")
    else:
        console.print_json(json.dumps(result, ensure_ascii=False))


@app.command("merge-projects")
def merge_projects(
    project_dirs: list[str] = typer.Argument(..., help="GTFlow output directories to merge"),
    out_dir: str = typer.Option(..., "-o", help="Merged output directory"),
):
    result = merge_project_dirs(project_dirs, out_dir)
    console.print_json(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    app()
