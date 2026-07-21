# GTFlow

GTFlow is a local research workspace for grounded theory analysis. It turns interviews, field notes, and structured qualitative datasets into segments, initial codes, a codebook, Gioia structures, axial CAR triples, a core category and storyline, negative-case evidence, saturation metrics, participant contrasts, and shareable reports.

GTFlow includes a browser UI and a CLI. The browser UI is a lightweight local web app built with static HTML/CSS/JS and the Python pipeline.

## Highlights

- End-to-end grounded theory pipeline: segmentation, open coding, codebook building, Gioia alignment, axial coding, selective coding, negative cases, saturation, analytics, and report generation.
- Local web UI for interactive analysis, race-safe preview, cancellable background jobs, Gioia editing, result review, and ZIP export.
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
# Or, when running directly from a source checkout:
python -m gtflow.gui.launcher
```

Open the printed local URL in your browser. The default host is loopback-only and the default port is `8501`; GTFlow automatically selects the next available port when `8501` is busy.

The UI workflow:

1. Configure provider, model, API key, generation settings, and run limits.
2. Paste source text or upload `.txt`, `.md`, `.csv`, or `.jsonl`.
3. Review segmentation preview and readiness.
4. Run analysis and follow real stage progress; cancellation is cooperative at safe stage boundaries.
5. Review overview, Gioia alignment, contrasts, negative cases, code-novelty saturation, and raw data.
6. Save Gioia edits (with undo) to rebuild the quality audit, report, and ZIP bundle.
7. Download the ZIP bundle from its dedicated local endpoint.

The interface exposes explicit `empty`, `configured`, `ready`, `queued`, `running-stage`, `succeeded`, `failed`, `edited`, and `exported` states. A failed run keeps the previous successful result available. On screens below 920 px, settings move into a keyboard-accessible drawer instead of being stacked above the workspace. The static HTML/CSS/JS frontend uses system fonts, neutral layered surfaces, restrained blue accents, 44 px controls, visible focus rings, and reduced-motion support without a frontend framework or CDN.

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

## Data and provider boundary

The browser interface and segmentation preview are served by the local GTFlow
process. Preview requests never include the API key and do not call a model
provider. When you choose **Run analysis**, GTFlow sends source excerpts and
the generated analysis context to the provider endpoint you configured. That
endpoint may be a remote third party, an organizational gateway, or a local
service such as Ollama; its own retention and privacy terms apply. Output files
remain local unless you move or share them.

For sensitive studies, use an approved endpoint, avoid pasting secrets into
source text, and verify your provider's data-handling policy before running.

API keys are held only for the active request or job: they are excluded from UI
preference storage, exported configuration, and preview requests. Non-sensitive
interface preferences may be stored in the browser. The provider destination is
shown before a run so a local Ollama endpoint is distinguishable from a remote
cloud or gateway host.

## Local web security model

GTFlow's web service is designed for one local researcher, not as a public or
multi-tenant server. It binds to loopback by default and enforces:

- same-origin `Host`/`Origin` checks and a per-process `X-GTFlow-CSRF` token for mutations;
- JSON content-type validation, a 4 MiB request limit, bounded JSON depth/node counts, socket timeouts, and structured errors;
- containment checks for static file paths, including Windows absolute, UNC, encoded traversal, and drive-path cases;
- CSP, `nosniff`, and related response headers;
- one expensive analysis at a time, a bounded in-memory job registry, unguessable job IDs, and expiring completed jobs;
- credential isolation: a request-selected OpenAI-compatible base URL or Azure endpoint cannot inherit a process environment API key.

Background job state and bundles stay in process memory and disappear when the
server stops. Read-only job status uses an unguessable local job ID; create,
cancel, and edit operations also require the same-origin CSRF boundary. Do not
bind GTFlow to a LAN or public interface unless you add an appropriate trusted
reverse proxy and access-control layer yourself.

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
- `evidence_catalog.json` (canonical source text, source order, and linked open-code provenance)
- `quality.json` (cross-artifact coverage, verbatim, reference-validity, and limitation audit)
- `report.html`
- `run_meta.json`
- `stage_manifest.json` (CLI stage signatures, status, counts, and artifact hashes)

`merge-projects` additionally writes `project_manifest.json` and `merge_meta.json`.

`run_meta.json` stores per-stage token usage. Cost is estimated only when both model price fields are set.

`stage_manifest.json` makes CLI resume decisions auditable. It records the input
SHA-256, a secret-free normalized configuration, provider/model, prompt and
schema fingerprints, upstream artifact hashes, `running`/`complete`/`failed`
state, output hashes, and stage counts. A cache entry is reused only when its
signature and every declared output hash still match. Input, model, prompt, or
upstream provenance changes invalidate the affected stage and all dependent
stages—even if a changed prompt happens to produce byte-identical output.

Interrupted streamed JSONL is never marked complete. Before rerunning open
coding, GTFlow removes both possible open-code formats; a non-streamed run cannot
be shadowed by an older `open_codes.jsonl`. The manifest declares which format
is canonical.

Provider retries are owned by GTFlow rather than nested SDK retry loops. The
policy stops on permanent errors, retries bounded transient failures, honors
`Retry-After`, adds jittered backoff, and records secret-free per-attempt
telemetry in `run_meta.json`.

Every source segment now produces an open-coding record. Exhausted parse or validation retries are preserved with `status: "failed"` and `validation_errors` rather than appearing as empty successful coding. Axial and negative-case evidence IDs are checked against `evidence_catalog.json`; rejected IDs remain visible in audit metadata. The generated HTML report is self-contained and includes the theory rationale, provenance, quality audit, and limitations without loading third-party scripts. Saturation output is deliberately labeled as a code-novelty diagnostic; incomplete windows and failed coding records cannot create an early, misleading saturation claim.

Project merges validate manifest hashes and segment references before writing.
Each source project has a stable ID, so two directories both named `output` get
different prefixes. Merged outputs include `project_manifest.json` with source
IDs and artifact hashes; orphan open-code, axial-evidence, or negative-case IDs
cause the merge to fail rather than being silently rewritten.

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
docker run --rm -p 127.0.0.1:8501:8501 \
  -e OPENAI_API_KEY=YOUR_OPENAI_API_KEY \
  -e OPENAI_BASE_URL=https://api.openai.com/v1 \
  gtflow
```

Open `http://127.0.0.1:8501`.

## License

MIT
