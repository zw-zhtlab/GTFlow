
from __future__ import annotations
import csv, json, os, pathlib, asyncio, time, itertools
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
from .pipeline.axial_coder import build_axial
from .pipeline.selective_coder import build_theory
from .pipeline.gioia_view import to_gioia
from .pipeline.negatives_scanner import scan_negatives
from .pipeline.saturation import saturation_suite
from .pipeline.analytics import build_analysis_bundle
from .pipeline.project_ops import compare_projects as compare_project_dirs, merge_projects as merge_project_dirs
from .pipeline.report_html import emit_html
from .rate_limiter import TokenBucket
from .models.schemas import Segment
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
    if os.path.exists(open_jsonl):
        for rec in iter_jsonl(open_jsonl):
            try:
                yield OpenCodingItem.model_validate(rec)
            except Exception:
                continue
    elif os.path.exists(open_json):
        for rec in read_json(open_json):
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

    run_meta = {"stages": {}, "totals": {}}
    price_in = conf.provider.price_input_per_1k
    price_out = conf.provider.price_output_per_1k
    output_language = getattr(conf.provider, "output_language", None) or "English"

    segments_count = 0
    open_codes_count = None

    # 1) Segment
    _stage_header("Segment")
    seg_json = os.path.join(out_dir, "segments.json")
    seg_jsonl = os.path.join(out_dir, "segments.jsonl")
    if not os.path.exists(seg_json) or force:
        strat = conf.run.segmentation_strategy
        segs = _load_segments(input_path, strat, conf.run.max_segment_chars)
        write_json(seg_json, [s.model_dump() for s in segs])
        # also emit jsonl for large runs
        from .utils.jsonl_utils import write_jsonl
        write_jsonl(seg_jsonl, (s.model_dump() for s in segs))
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
    if (not os.path.exists(open_json) and not os.path.exists(open_jsonl)) or force:
        seg_iter = (s.model_dump() for s in segs)
        before = provider.total_usage()
        if conf.run.stream_open_coding or len(segs) >= conf.run.stream_open_coding_threshold:
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

    # 3) Codebook
    _stage_header("Codebook")
    codebook_json = os.path.join(out_dir, "codebook.json")
    if not os.path.exists(codebook_json) or force:
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

    # 4) Axial triples
    _stage_header("Axial Coding")
    triples_json = os.path.join(out_dir, "axial_triples.json")
    if not os.path.exists(triples_json) or force:
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
        )
        write_json(triples_json, [t.model_dump() for t in triples])
        run_meta["stages"]["axial"] = usage_delta(before)

    # 5) Theory
    _stage_header("Selective Coding / Theory")
    theory_json = os.path.join(out_dir, "theory.json")
    if not os.path.exists(theory_json) or force:
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
        )
        write_json(theory_json, theory.model_dump())
        write_text(os.path.join(out_dir,"theory.md"), f"# Core Category\n\n{theory.core_category}\n\n## Storyline\n\n{theory.storyline}\n")
        run_meta["stages"]["theory"] = usage_delta(before)

    # 6) Gioia
    _stage_header("Gioia View")
    gioia_json = os.path.join(out_dir, "gioia.json")
    if not os.path.exists(gioia_json) or force:
        from .models.schemas import Codebook
        codebook = Codebook.model_validate(read_json(codebook_json))
        gioia = to_gioia(codebook)
        write_json(gioia_json, gioia)

    # 7) Negatives
    _stage_header("Negative Cases")
    negatives_json = os.path.join(out_dir, "negatives.json")
    if not os.path.exists(negatives_json) or force:
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
        )
        write_json(negatives_json, negs)
        run_meta["stages"]["negatives"] = usage_delta(before)

    # 8) Saturation
    _stage_header("Analytics")
    analytics_json = os.path.join(out_dir, "analytics.json")
    if not os.path.exists(analytics_json) or force:
        open_items_full = list(_iter_open_codes(open_json, open_jsonl))
        negatives_for_analytics = read_json(negatives_json) if os.path.exists(negatives_json) else []
        analytics = build_analysis_bundle(segs, open_items_full, negatives_for_analytics)
        write_json(analytics_json, analytics)

    _stage_header("Saturation")
    saturation_json = os.path.join(out_dir, "saturation.json")
    saturation_metrics_json = os.path.join(out_dir, "saturation_metrics.json")
    if not os.path.exists(saturation_json) or force:
        if os.path.exists(open_jsonl):
            oc_iter = iter_jsonl(open_jsonl)
        else:
            oc_iter = read_json(open_json)
        sat_metrics = saturation_suite(oc_iter)
        write_json(saturation_json, sat_metrics["default"])
        write_json(saturation_metrics_json, sat_metrics)
    elif not os.path.exists(saturation_metrics_json):
        if os.path.exists(open_jsonl):
            oc_iter = iter_jsonl(open_jsonl)
        else:
            oc_iter = read_json(open_json)
        write_json(saturation_metrics_json, saturation_suite(oc_iter))

    # 9) HTML Report
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
    emit_html(
        html_path,
        stats,
        read_json(gioia_json),
        [t.model_dump() for t in triples],
        open_items,
        codebook,
        analytics=analytics_data,
        saturation_metrics=saturation_metrics_data,
    )

    # totals
    totals = provider.total_usage()
    run_meta["totals"] = {
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "estimated_cost": _estimated_cost(totals["input_tokens"], totals["output_tokens"], price_in, price_out),
    }
    write_json(os.path.join(out_dir, "run_meta.json"), run_meta)

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
    if os.path.exists(open_jsonl):
        open_items = list(itertools.islice(iter_jsonl(open_jsonl), 200))
        open_codes_count = count_jsonl(open_jsonl)
    elif os.path.exists(open_json):
        open_items = read_json(open_json)
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
    emit_html(
        os.path.join(out_dir, "report.html"),
        stats,
        to_gioia(Codebook.model_validate(codebook)),
        triples,
        open_items,
        Codebook.model_validate(codebook),
        analytics=analytics_data,
        saturation_metrics=saturation_metrics_data,
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
