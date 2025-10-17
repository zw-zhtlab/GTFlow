# GTFlow: End-to-end tool for Grounded Theory research

GTFlow turns raw qualitative text into theory-building artifacts. It ships with a Streamlit-based UI and a CLI, supports OpenAI‑protocol compatible endpoints, Azure OpenAI, and Anthropic, and tracks token usage and estimated costs.

---

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [UI Usage](#ui-usage)
- [Inputs and Outputs](#inputs-and-outputs)
- [Reproducibility, Usage, and Cost](#reproducibility-usage-and-cost)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features
- **End-to-end pipeline**: Segmentation, Open coding, Codebook building with Gioia view, Axial coding with CAR triples, Selective coding and storyline, Negative case scan, Saturation check, and Report generation.
- **Two interfaces**: Streamlit UI for interactive work and a CLI for scripted, reproducible runs.
- **Provider compatibility**: OpenAI‑protocol compatible, Azure OpenAI, and Anthropic. Gateways are supported if they expose an OpenAI‑compatible API.
- **Structured output first**: Prompts prefer JSON with robust parsing and graceful fallbacks.
- **Reproducibility utilities**: Run directory with intermediate artifacts, token usage and cost estimation, and a one‑command report.

---

## Quick Start

### 1) Install
> Python **3.9+** is required.

From PyPI (if published):
```bash
pip install -U gtflow
# or in an isolated tool environment
pipx install gtflow
```

From source:
```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
pip install -e .
```

### 2) Configure provider credentials
Choose one path below.

**OpenAI‑compatible** (OpenAI, compatible gateways, or Ollama’s /v1):
```bash
# minimally set your key (and optionally a custom base URL)
export OPENAI_API_KEY=sk-...
# for self-hosted or gateways
export OPENAI_BASE_URL=https://your-endpoint/v1
# optional organization header
export OPENAI_ORG_ID=org_...
```

**Azure OpenAI**:
```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT=YOUR-DEPLOYMENT
export AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

**Anthropic**:
```bash
export ANTHROPIC_API_KEY=...
```

> Tip: when using the YAML config below, either put real values or omit the `api_key` field. Avoid literal placeholders like `${OPENAI_API_KEY}` in YAML because they will be treated as a string rather than expanded.

### 3) Run the UI or the pipeline

**UI (recommended for first run)**
```bash
gtflow-ui
```
Follow the left sidebar to set provider and run parameters, upload or paste your text, and export artifacts.

**One‑command pipeline (CLI)**
```bash
# Example data and config may live under examples/
gtflow run-all -i examples/data/sample_dialog.txt -c examples/config.example.yaml -o output
gtflow report -o output
# Open output/report.html in your browser
```

---

## Installation
- Python **3.9+**
- Linux, macOS, or Windows
- Optional: Graphviz installed system‑wide if you plan to generate graph files

Dependencies are automatically installed via `pip`. See `pyproject.toml` or `requirements.txt` for versions.

---

## Configuration

You can control providers and runtime behavior via a YAML file. A minimal example:

```yaml
# config.yaml
provider:
  name: openai_compatible          # openai_compatible | openai | azure_openai | anthropic | ollama
  model: gpt-4o-mini               # change as needed
  # api_key: <fill-your-real-key-or-omit>
  base_url: https://api.openai.com/v1
  use_responses_api: false         # true to try /v1/responses first
  structured: true                 # request JSON when supported
  max_tokens: 1024
  temperature: 0.2
  price_input_per_1k: 0.002
  price_output_per_1k: 0.006

run:
  segmentation_strategy: dialog    # dialog | paragraph | line
  max_segment_chars: 800
  batch_size: 10
  concurrent_workers: 6
  rate_limit_rps: 2.0
  retry_max: 3
  timeout_sec: 60

output:
  out_dir: output
  save_graphviz: true
  log_file: analysis.log
```

Notes:
- **OpenAI‑compatible**: if `api_key` is omitted in YAML, `OPENAI_API_KEY` is used automatically. `OPENAI_BASE_URL` overrides `base_url` at runtime.
- **Azure OpenAI**: set `endpoint`, `deployment`, `api_version`, and `api_key` in YAML. The CLI does not read Azure env vars automatically.
- **Anthropic**: set `api_key` in YAML or export `ANTHROPIC_API_KEY` and wire it in your own wrapper before creating the config.

---

## CLI Usage

`gtflow` exposes focused commands:

```bash
# 1) Segment a source file into analysis units
gtflow segment   -i data/interview_1.txt   -o output   --strategy dialog   --max-segment-chars 800

# 2) Run the entire pipeline using a YAML config
gtflow run-all   -i data/interview_1.txt   -c config.yaml   -o output   --force                  # optional, overwrite existing artifacts

# 3) Build a report from saved artifacts
gtflow report -o output

# General help
gtflow --help
gtflow run-all --help
```

What `run-all` produces under `output/`:
- `segments.json`
- `open_codes.json`
- `codebook.json`
- `axial_triples.json`
- `theory.json` and `theory.md`
- `gioia.json`
- `negatives.json`
- `saturation.json`
- `report.html`
- `run_meta.json` (token usage by stage and estimated cost)

---

## UI Usage

Launch:
```bash
gtflow-ui
```
The dashboard lets you:
- Configure the provider (OpenAI‑compatible, Azure OpenAI, Anthropic), model, temperature, and token limits.
- Choose segmentation strategy and batching.
- Run open coding, build a codebook, generate axial CAR triples, derive a core category and storyline, scan negatives, approximate saturation.
- Download a ZIP of artifacts and an HTML report.

---

## Inputs and Outputs

**Typical inputs**
- Plain text files (`.txt`, `.md`).
- JSONL with one record per line. Suggested keys: `id`, `text`, optional `speaker`, optional `meta`.
- CSV with columns: `id`, `text`, optional `speaker` and `meta`.

**Key outputs**
- `segments.json`: segmented units used for analysis.
- `open_codes.json`: initial codes per segment.
- `codebook.json`: first‑order codes, definitions, and Gioia groupings.
- `axial_triples.json`: CAR triples with short evidence spans.
- `theory.json` and `theory.md`: core category and storyline.
- `gioia.json`: compact Gioia view used by the report.
- `negatives.json`: candidate negative cases from the corpus.
- `saturation.json`: sliding‑window estimate of new‑code discovery.
- `report.html`: consolidated visual report with a Gioia panel and a Mermaid diagram for CAR relations.
- `run_meta.json`: per‑stage token counts and estimated cost.

---

## Reproducibility, Usage, and Cost
- Each run writes a structured set of artifacts to the output directory so you can rerun, diff, and audit results.
- The CLI prints a **Token Usage by Stage** table and writes `run_meta.json` with input tokens, output tokens, totals, and an estimated cost using your configured `price_input_per_1k` and `price_output_per_1k`.
- For ethics and privacy, ensure consent for any interview or sensitive text and follow your IRB or organizational guidelines.

---

## Roadmap
- Batch editing and alignment in the Gioia panel.
- Visualizations for negative cases and participant‑level contrasts.
- Multiple saturation metrics in parallel.
- Configurable report templates for methods, results, and appendices.
- Project‑level comparison and merging utilities.

---

## Contributing
Contributions are welcome. A suggested process:
1. Open an issue to discuss the proposal.
2. Fork the repo and create a feature branch.
3. Add tests or local checks where reasonable.
4. Submit a PR describing motivation and changes.

---

## License
This project is licensed under the MIT License.
