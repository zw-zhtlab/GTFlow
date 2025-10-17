
from __future__ import annotations
import json, os, pathlib, asyncio, time
import typer, yaml
from rich.table import Table
from .config import AppConfig
from .logging import console
from .utils.file_io import read_text, write_json, write_text, ensure_dir, write_csv, read_json
from .providers.base import make_provider
from .pipeline.segmenter import segment_dialog, segment_paragraph, segment_line
from .pipeline.open_coder import run_open_coding
from .pipeline.codebook_builder import build_codebook
from .pipeline.axial_coder import build_axial
from .pipeline.selective_coder import build_theory
from .pipeline.gioia_view import to_gioia
from .pipeline.negatives_scanner import scan_negatives
from .pipeline.saturation import saturation
from .pipeline.report_html import emit_html
from .models.schemas import Segment
from .cost import UsageAccumulator, estimate_cost

app = typer.Typer(help="GTFlow grounded theory pipeline")

def _load_config(config_path: str | None) -> AppConfig:
    if config_path and os.path.exists(config_path):
        if config_path.endswith(".json"):
            data = json.loads(read_text(config_path))
        else:
            data = yaml.safe_load(read_text(config_path))
        return AppConfig.model_validate(data)
    return AppConfig()

def _stage_header(name: str):
    console.rule(f"[info]{name}[/info]")

@app.command()
def segment(
    input_path: str = typer.Option(..., "-i", help="Input text file"),
    out_dir: str = typer.Option("output", "-o", help="Output directory"),
    strategy: str = typer.Option("dialog", help="dialog|paragraph|line"),
    max_segment_chars: int = typer.Option(800, help="Maximum characters per segment")
):
    ensure_dir(out_dir)
    text = read_text(input_path)
    if strategy == "dialog":
        segs = segment_dialog(text, max_segment_chars)
    elif strategy == "paragraph":
        segs = segment_paragraph(text, max_segment_chars)
    else:
        segs = segment_line(text, max_segment_chars)
    write_json(os.path.join(out_dir, "segments.json"), [s.model_dump() for s in segs])
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

    run_meta = {"stages": {}, "totals": {}}
    price_in = conf.provider.price_input_per_1k
    price_out = conf.provider.price_output_per_1k

    # 1) Segment
    _stage_header("Segment")
    seg_json = os.path.join(out_dir, "segments.json")
    if not os.path.exists(seg_json) or force:
        text = read_text(input_path)
        strat = conf.run.segmentation_strategy
        if strat == "dialog":
            segs = segment_dialog(text, conf.run.max_segment_chars)
        elif strat == "paragraph":
            segs = segment_paragraph(text, conf.run.max_segment_chars)
        else:
            segs = segment_line(text, conf.run.max_segment_chars)
        write_json(seg_json, [s.model_dump() for s in segs])
    else:
        segs = [Segment.model_validate(x) for x in read_json(seg_json)]
    console.print(f"[ok] segments: {len(segs)}")

    # provider
    provider = make_provider(conf.provider)
    provider.reset_usage_totals()

    # helper for per-stage usage delta
    def usage_delta(before):
        after = provider.total_usage()
        return {
            "input_tokens": after["input_tokens"] - before["input_tokens"],
            "output_tokens": after["output_tokens"] - before["output_tokens"],
            "total_tokens": after["total_tokens"] - before["total_tokens"],
            "estimated_cost": round((after["input_tokens"] - before["input_tokens"]) / 1000.0 * price_in + (after["output_tokens"] - before["output_tokens"]) / 1000.0 * price_out, 6)
        }

    # 2) Open coding
    _stage_header("Open Coding")
    open_json = os.path.join(out_dir, "open_codes.json")
    if not os.path.exists(open_json) or force:
        seg_dicts = [s.model_dump() for s in segs]
        before = provider.total_usage()
        items = run_open_coding(provider, seg_dicts, batch_size=conf.run.batch_size, max_retries=conf.run.retry_max)
        write_json(open_json, [x.model_dump() for x in items])
        run_meta["stages"]["open_coding"] = usage_delta(before)

    # 3) Codebook
    _stage_header("Codebook")
    codebook_json = os.path.join(out_dir, "codebook.json")
    if not os.path.exists(codebook_json) or force:
        from .models.schemas import OpenCodingItem
        items = [OpenCodingItem.model_validate(x) for x in read_json(open_json)]
        before = provider.total_usage()
        codebook = build_codebook(provider, items)
        write_json(codebook_json, codebook.model_dump())
        run_meta["stages"]["codebook"] = usage_delta(before)

    # 4) Axial triples
    _stage_header("Axial Coding")
    triples_json = os.path.join(out_dir, "axial_triples.json")
    if not os.path.exists(triples_json) or force:
        from .models.schemas import Codebook
        codebook = Codebook.model_validate(read_json(codebook_json))
        before = provider.total_usage()
        triples = build_axial(provider, codebook)
        write_json(triples_json, [t.model_dump() for t in triples])
        run_meta["stages"]["axial"] = usage_delta(before)

    # 5) Theory
    _stage_header("Selective Coding / Theory")
    theory_json = os.path.join(out_dir, "theory.json")
    if not os.path.exists(theory_json) or force:
        from .models.schemas import AxialTriple
        triples = [AxialTriple.model_validate(x) for x in read_json(triples_json)]
        before = provider.total_usage()
        theory = build_theory(provider, triples)
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
        negs = scan_negatives(provider, seg_dicts, tho.get("storyline",""))
        write_json(negatives_json, negs)
        run_meta["stages"]["negatives"] = usage_delta(before)

    # 8) Saturation
    _stage_header("Saturation")
    saturation_json = os.path.join(out_dir, "saturation.json")
    if not os.path.exists(saturation_json) or force:
        oc = read_json(open_json)
        sat = saturation(oc)
        write_json(saturation_json, sat)

    # 9) HTML Report
    _stage_header("HTML Report")
    html_path = os.path.join(out_dir, "report.html")
    from .models.schemas import Codebook, AxialTriple, OpenCodingItem
    codebook = Codebook.model_validate(read_json(codebook_json))
    triples = [AxialTriple.model_validate(x) for x in read_json(triples_json)]
    open_items = [OpenCodingItem.model_validate(x) for x in read_json(open_json)]
    stats = {
        "segments": len(segs),
        "open_codes": sum(len(i.initial_codes) for i in open_items),
        "codebook_entries": len(codebook.entries),
        "triples": len(triples),
    }
    emit_html(html_path, stats, read_json(gioia_json), [t.model_dump() for t in triples], open_items, codebook)

    # totals
    totals = provider.total_usage()
    run_meta["totals"] = {
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "total_tokens": totals["total_tokens"],
        "estimated_cost": round(totals["input_tokens"]/1000.0*price_in + totals["output_tokens"]/1000.0*price_out, 6)
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
        table.add_row(k, str(v["input_tokens"]), str(v["output_tokens"]), str(v["total_tokens"]), str(v["estimated_cost"]))
    table.add_row("ALL", str(run_meta["totals"]["input_tokens"]), str(run_meta["totals"]["output_tokens"]), str(run_meta["totals"]["total_tokens"]), str(run_meta["totals"]["estimated_cost"]))
    console.print(table)

@app.command()
def html_report(out_dir: str = typer.Option("output", "-o")):
    codebook = read_json(os.path.join(out_dir, "codebook.json"))
    triples = read_json(os.path.join(out_dir, "axial_triples.json"))
    open_items = read_json(os.path.join(out_dir, "open_codes.json"))
    segs = read_json(os.path.join(out_dir, "segments.json"))
    from .pipeline.report_html import emit_html
    stats = {
        "segments": len(segs),
        "open_codes": sum(len(i.get("initial_codes",[])) for i in open_items),
        "codebook_entries": len(codebook.get("entries",[])),
        "triples": len(triples),
    }
    from .pipeline.gioia_view import to_gioia
    from .models.schemas import Codebook
    emit_html(os.path.join(out_dir,"report.html"), stats, to_gioia(Codebook.model_validate(codebook)), triples, open_items, Codebook.model_validate(codebook))
    console.print(f"[ok] Wrote {out_dir}/report.html")
