from __future__ import annotations

import io
import os
import tempfile
import zipfile

import streamlit as st

from gtflow.config import AppConfig, ProviderConfig
from gtflow.models.schemas import AxialTriple, Codebook, OpenCodingItem, Segment
from gtflow.pipeline.axial_coder import build_axial
from gtflow.pipeline.codebook_builder import build_codebook
from gtflow.pipeline.gioia_view import to_gioia
from gtflow.pipeline.negatives_scanner import scan_negatives
from gtflow.pipeline.open_coder import run_open_coding
from gtflow.pipeline.report_html import emit_html
from gtflow.pipeline.saturation import saturation
from gtflow.pipeline.segmenter import segment_dialog, segment_line, segment_paragraph
from gtflow.pipeline.selective_coder import build_theory
from gtflow.providers.base import make_provider
from gtflow.utils.file_io import ensure_dir, write_json


def _default_config() -> AppConfig:
    return AppConfig()


def _save_config_snippet(conf: AppConfig, dirpath: str) -> None:
    write_json(os.path.join(dirpath, "config.used.json"), conf.model_dump())


def _usage_box(title: str, usage: dict) -> None:
    cols = st.columns(4)
    cols[0].metric(f"{title} - input tokens", usage.get("input_tokens", 0))
    cols[1].metric(f"{title} - output tokens", usage.get("output_tokens", 0))
    cols[2].metric(f"{title} - total tokens", usage.get("total_tokens", 0))
    cols[3].metric(f"{title} - est. cost ($)", usage.get("estimated_cost", 0))


def main():
    st.set_page_config(page_title="GTFlow", layout="wide")
    st.title("GTFlow Dashboard")

    if "conf" not in st.session_state:
        st.session_state["conf"] = _default_config()

    with st.sidebar:
        st.header("Provider Settings")
        conf_provider: ProviderConfig = st.session_state["conf"].provider
        provider_choices = ["openai_compatible", "azure_openai", "anthropic"]
        name = st.selectbox(
            "Provider",
            provider_choices,
            index=provider_choices.index(conf_provider.name)
            if conf_provider.name in provider_choices
            else 0,
        )
        model = st.text_input("model", value=conf_provider.model)
        temperature = st.slider(
            "temperature",
            min_value=0.0,
            max_value=1.0,
            value=conf_provider.temperature,
            step=0.05,
        )
        max_tokens = st.number_input(
            "max_tokens",
            min_value=1,
            max_value=8192,
            value=conf_provider.max_tokens,
            step=64,
        )
        st.markdown("---")
        if name == "openai_compatible":
            base_url = st.text_input(
                "base_url",
                value=conf_provider.base_url
                or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
            api_key = st.text_input(
                "api_key",
                type="password",
                value=conf_provider.api_key or os.getenv("OPENAI_API_KEY", ""),
            )
            organization = st.text_input(
                "organization (optional)",
                value=conf_provider.organization or os.getenv("OPENAI_ORG_ID", ""),
            )
            use_responses = st.checkbox(
                "Use /v1/responses endpoint", value=conf_provider.use_responses_api
            )
        elif name == "azure_openai":
            endpoint = st.text_input("endpoint", value=conf_provider.endpoint or "")
            deployment = st.text_input("deployment", value=conf_provider.deployment or "")
            api_version = st.text_input(
                "api_version", value=conf_provider.api_version or "2024-02-15-preview"
            )
            api_key = st.text_input("api_key", type="password", value=conf_provider.api_key or "")
        else:
            api_key = st.text_input("api_key", type="password", value=conf_provider.api_key or "")

        st.header("Run Parameters")
        seg_strategy = st.selectbox(
            "Segmentation strategy",
            ["dialog", "paragraph", "line"],
            index=["dialog", "paragraph", "line"].index(
                st.session_state["conf"].run.segmentation_strategy
            ),
        )
        max_chars = st.slider(
            "Max chars per segment",
            min_value=200,
            max_value=2000,
            value=st.session_state["conf"].run.max_segment_chars,
            step=50,
        )
        batch_size = st.slider(
            "Open coding batch size",
            min_value=1,
            max_value=20,
            value=st.session_state["conf"].run.batch_size,
            step=1,
        )
        retry_max = st.slider(
            "Retry attempts",
            min_value=0,
            max_value=5,
            value=st.session_state["conf"].run.retry_max,
            step=1,
        )

        st.session_state["conf"].provider.name = name
        st.session_state["conf"].provider.model = model
        st.session_state["conf"].provider.temperature = float(temperature)
        st.session_state["conf"].provider.max_tokens = int(max_tokens)
        st.session_state["conf"].run.segmentation_strategy = seg_strategy
        st.session_state["conf"].run.max_segment_chars = int(max_chars)
        st.session_state["conf"].run.batch_size = int(batch_size)
        st.session_state["conf"].run.retry_max = int(retry_max)

        if name == "openai_compatible":
            st.session_state["conf"].provider.base_url = base_url
            st.session_state["conf"].provider.api_key = api_key
            st.session_state["conf"].provider.organization = organization or None
            st.session_state["conf"].provider.use_responses_api = use_responses
        elif name == "azure_openai":
            st.session_state["conf"].provider.endpoint = endpoint
            st.session_state["conf"].provider.deployment = deployment
            st.session_state["conf"].provider.api_version = api_version
            st.session_state["conf"].provider.api_key = api_key
        else:
            st.session_state["conf"].provider.api_key = api_key

    st.header("Input Text")
    txt = st.text_area("Paste or upload text", height=200)
    uploaded = st.file_uploader("or upload a .txt file", type=["txt"])
    if uploaded and not txt:
        txt = uploaded.read().decode("utf-8", errors="ignore")

    run_btn = st.button("Run pipeline", type="primary", disabled=not txt)

    if not run_btn:
        return

    conf = st.session_state["conf"]

    with st.status("Segmenting...", expanded=True) as status_box:
        if conf.run.segmentation_strategy == "dialog":
            segments = segment_dialog(txt, conf.run.max_segment_chars)
        elif conf.run.segmentation_strategy == "paragraph":
            segments = segment_paragraph(txt, conf.run.max_segment_chars)
        else:
            segments = segment_line(txt, conf.run.max_segment_chars)
        status_box.update(label=f"Segmented {len(segments)} entries.")

    provider = make_provider(conf.provider)
    provider.reset_usage_totals()

    progress = st.progress(0, text="Open coding in progress...")

    segment_dicts = [segment.model_dump() for segment in segments]
    items = run_open_coding(
        provider,
        segment_dicts,
        batch_size=conf.run.batch_size,
        max_retries=conf.run.retry_max,
    )
    progress.progress(20, text="Open coding complete.")

    codebook = build_codebook(provider, items)
    progress.progress(40, text="Codebook complete.")

    triples = build_axial(provider, codebook)
    progress.progress(60, text="Axial coding complete.")

    theory = build_theory(provider, triples)
    progress.progress(75, text="Selective coding complete.")

    negatives = scan_negatives(provider, segment_dicts, theory.storyline)
    sat = saturation([item.model_dump() for item in items])
    progress.progress(85, text="Negative cases and saturation calculated.")

    tmpdir = tempfile.mkdtemp(prefix="gtflow_")
    ensure_dir(tmpdir)
    write_json(os.path.join(tmpdir, "segments.json"), segment_dicts)
    write_json(os.path.join(tmpdir, "open_codes.json"), [item.model_dump() for item in items])
    write_json(os.path.join(tmpdir, "codebook.json"), codebook.model_dump())
    write_json(os.path.join(tmpdir, "axial_triples.json"), [triple.model_dump() for triple in triples])
    write_json(os.path.join(tmpdir, "theory.json"), theory.model_dump())
    write_json(os.path.join(tmpdir, "gioia.json"), to_gioia(codebook))
    write_json(os.path.join(tmpdir, "negatives.json"), negatives)
    write_json(os.path.join(tmpdir, "saturation.json"), sat)
    emit_html(
        os.path.join(tmpdir, "report.html"),
        {
            "segments": len(segments),
            "open_codes": sum(len(item.initial_codes) for item in items),
            "codebook_entries": len(codebook.entries),
            "triples": len(triples),
        },
        to_gioia(codebook),
        [triple.model_dump() for triple in triples],
        items,
        codebook,
    )
    _save_config_snippet(conf, tmpdir)

    totals = provider.total_usage()
    price_in = conf.provider.price_input_per_1k
    price_out = conf.provider.price_output_per_1k
    run_meta = {
        "totals": {
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "total_tokens": totals["total_tokens"],
            "estimated_cost": round(
                totals["input_tokens"] / 1000.0 * price_in
                + totals["output_tokens"] / 1000.0 * price_out,
                6,
            ),
        }
    }
    write_json(os.path.join(tmpdir, "run_meta.json"), run_meta)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        for filename in os.listdir(tmpdir):
            zipped.write(os.path.join(tmpdir, filename), arcname=filename)
    progress.progress(100, text="All done.")

    st.success("Pipeline completed.")
    st.download_button(
        "Download output ZIP",
        data=buffer.getvalue(),
        file_name="gtflow_output.zip",
        use_container_width=True,
    )

    st.subheader("Usage and Cost Summary")
    _usage_box("Total", run_meta["totals"])

    st.subheader("Preview")
    st.markdown(f"**Core category**: {theory.core_category}")
    st.markdown(f"**Storyline**: {theory.storyline}")
    st.dataframe([{"seg_id": seg.seg_id, "text": seg.text[:180]} for seg in segments[:20]])
    st.dataframe(
        [
            {"seg_id": item.seg_id, "codes": ", ".join(initial.code for initial in item.initial_codes)}
            for item in items[:20]
        ]
    )
    st.dataframe(
        [{"code": entry.code, "definition": entry.definition} for entry in codebook.entries[:20]]
    )


if __name__ == "__main__":
    main()
