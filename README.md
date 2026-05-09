# GTFlow

GTFlow is a local research workspace for grounded theory analysis. It turns interviews, field notes, and structured qualitative datasets into segments, initial codes, a codebook, Gioia structures, axial CAR triples, a core category and storyline, negative-case evidence, saturation metrics, participant contrasts, and shareable reports.

GTFlow includes a browser UI and a CLI. The browser UI is a lightweight local web app built with static HTML/CSS/JS and the Python pipeline.

## Highlights

- End-to-end grounded theory pipeline: segmentation, open coding, codebook building, Gioia alignment, axial coding, selective coding, negative cases, saturation, analytics, and report generation.
- Local web UI for interactive analysis, file upload, preview, batch runs, Gioia editing, result review, and ZIP export.
- CLI for reproducible scripted runs and project automation.
- Provider support for OpenAI-compatible APIs, Azure OpenAI, Anthropic, OpenAI, and Ollama-style `/v1` endpoints.
- Structured inputs: `.txt`, `.md`, `.csv`, and `.jsonl`.
- Large-run support with JSONL streaming for open coding.
- Project utilities for comparing and merging GTFlow output directories.
- Configurable HTML reports with methods, results, and appendix sections.

## Install

GTFlow requires Python 3.9+.

From the repository root:

```bash
pip install -e .
```

Graphviz enables graph output in reports.

## Quick Start

### Web UI

```bash
gtflow-ui
```

Open the printed local URL in your browser. The default port is `8501`; GTFlow automatically selects the next available port when `8501` is busy.

The UI workflow:

1. Configure provider, model, API key, generation settings, and run limits.
2. Paste source text or upload `.txt`, `.md`, `.csv`, or `.jsonl`.
3. Review segmentation preview and readiness.
4. Run analysis.
5. Review overview, Gioia alignment, contrasts, negative cases, saturation, and raw data.
6. Download the ZIP bundle with artifacts and the HTML report.

### CLI

```bash
gtflow run-all -i examples/data/sample_dialog.txt -c examples/config.example.yaml -o output --force
gtflow report -o output
```

Open `output/report.html` after the run finishes.

## Provider Setup

### OpenAI-Compatible APIs

Use this path for OpenAI, SiliconFlow, local gateways, and services that expose an OpenAI-compatible `/v1` API.

```bash
export OPENAI_API_KEY=YOUR_OPENAI_API_KEY
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_ORG_ID=org_...
```

SiliconFlow example:

```bash
export OPENAI_API_KEY=YOUR_OPENAI_API_KEY
export OPENAI_BASE_URL=https://api.siliconflow.cn/v1
```

Then set the model in the UI or config, for example:

```yaml
provider:
  name: openai_compatible
  model: deepseek-ai/DeepSeek-V4-Flash
```

### Azure OpenAI

```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT=YOUR-DEPLOYMENT
export AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Anthropic

```bash
export ANTHROPIC_API_KEY=...
```

## Configuration

Create a YAML config for CLI runs and reusable defaults.

```yaml
provider:
  name: openai_compatible
  model: gpt-4o-mini
  output_language: English
  base_url: https://api.openai.com/v1
  organization:
  use_responses_api: false
  structured: true
  max_tokens: 1024
  temperature: 0.2
  price_input_per_1k:
  price_output_per_1k:

run:
  segmentation_strategy: dialog
  max_segment_chars: 800
  batch_size: 10
  concurrent_workers: 6
  rate_limit_rps: 2.0
  retry_max: 3
  timeout_sec: 60
  max_prompt_chars: 200000
  stream_open_coding: false
  stream_open_coding_threshold: 2000

output:
  out_dir: output
  save_graphviz: true
  log_file: analysis.log
```

`provider.output_language` controls LLM-generated codes, memos, definitions, theory text, negative-case summaries, and report prose. Source excerpts stay in their original language. JSON field names stay stable in English.

## Input Formats

### Plain Text

Use `.txt` or `.md` for raw interviews, notes, transcripts, or field material.

```text
Participant A: The checkout flow feels long.
Participant B: Clearer hints would help me recover.
```

### JSONL

Use one record per line.

```jsonl
{"id":"p1-001","speaker":"Participant A","text":"The checkout flow feels long.","participant":"P1"}
{"id":"p2-001","speaker":"Participant B","text":"Clearer hints would help me recover.","participant":"P2"}
```

Supported text keys: `text`, `content`, `utterance`.

Supported identity keys: `seg_id`, `id`, `ID`, `Id`.

Supported speaker keys: `speaker`, `role`.

All additional fields become segment metadata.

### CSV

Use columns such as:

```csv
id,speaker,text,participant
c1,A,The checkout flow feels long.,P1
c2,B,Clearer hints would help me recover.,P2
```

GTFlow preserves row metadata and creates unique segment IDs when source IDs repeat.

## CLI Commands

```bash
# Segment input into analysis units
gtflow segment -i data/interview_1.txt -o output --strategy dialog --max-segment-chars 800

# Run the full pipeline
gtflow run-all -i data/interview_1.txt -c config.yaml -o output --force

# Rebuild the HTML report from saved artifacts
gtflow report -o output

# Use a custom report template and section switches
gtflow report -o output --template templates/report.html --methods --results --appendices
gtflow report -o output --template templates/report.html --no-appendices

# Compare two GTFlow output directories
gtflow compare-projects --left output_a --right output_b -o comparison.json

# Merge multiple GTFlow output directories
gtflow merge-projects output_a output_b -o merged_output
```

## Output Artifacts

The full pipeline writes a structured project directory:

- `segments.json` and `segments.jsonl`
- `open_codes.json` and, for streamed runs, `open_codes.jsonl`
- `codebook.json`
- `axial_triples.json`
- `theory.json`
- `theory.md`
- `gioia.json`
- `negatives.json`
- `saturation.json`
- `saturation_metrics.json`
- `analytics.json`
- `report.html`
- `run_meta.json`

`run_meta.json` stores per-stage token usage. Cost is estimated only when both model price fields are set.

## Analysis Views

The UI and report expose:

- Gioia alignment with editable first-order codes, second-order themes, and aggregate dimensions.
- Negative-case summaries and supporting rows.
- Participant-level contrasts.
- Code frequency charts.
- Multiple saturation metrics and novelty curves.
- Raw segments, open codes, and codebook tables.

## Large Inputs

Use these settings for long studies:

```yaml
run:
  max_segment_chars: 400
  batch_size: 10
  concurrent_workers: 6
  rate_limit_rps: 2.0
  max_prompt_chars: 200000
  stream_open_coding: true
```

Streaming writes full open-coding output to `open_codes.jsonl` while keeping `open_codes.json` as a quick inspection sample.

## Report Templates

`gtflow report` accepts a Jinja2 template:

```bash
gtflow report -o output --template templates/report.html
```

Template rendering receives project stats, Gioia data, axial triples, sampled open codes, codebook entries, analytics, and saturation metrics. Section flags control methods, results, and appendices:

```bash
gtflow report -o output --no-methods
gtflow report -o output --no-results
gtflow report -o output --no-appendices
```

## Docker

```bash
docker build -t gtflow .
docker run --rm -p 8501:8501 \
  -e OPENAI_API_KEY=YOUR_OPENAI_API_KEY \
  -e OPENAI_BASE_URL=https://api.openai.com/v1 \
  gtflow
```

Open `http://127.0.0.1:8501`.

## Development Checks

```bash
python -m compileall -q gtflow
gtflow --help
python -m gtflow.gui.launcher --help
```

## License

MIT
