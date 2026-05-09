from __future__ import annotations

from typing import Any, Dict, List, Optional

from jinja2 import Environment, Template

from ..utils.file_io import read_text, write_text


DEFAULT_SECTIONS = {
    "methods": True,
    "results": True,
    "appendices": True,
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>GTFlow Report</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true });</script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, "Microsoft YaHei", sans-serif; margin: 0; color: #222; background: #fff; }
main { max-width: 1180px; margin: 0 auto; padding: 28px; }
h1, h2, h3 { letter-spacing: 0; }
h1 { margin: 0 0 8px; font-size: 30px; }
h2 { margin-top: 32px; padding-top: 12px; border-top: 1px solid #ddd; font-size: 21px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0 20px; table-layout: fixed; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #f6f8fa; }
pre { background: #f6f8fa; padding: 12px; overflow: auto; border: 1px solid #ddd; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 16px 0 8px; }
.metric { border: 1px solid #ddd; padding: 10px; border-radius: 6px; }
.metric b { display: block; font-size: 20px; margin-top: 4px; }
.bar { display: inline-block; height: 10px; background: #4f7cac; min-width: 2px; }
.muted { color: #666; }
</style>
</head>
<body>
<main>
<h1>GTFlow Grounded Theory Report</h1>
<div class="metrics">
{% for k, v in stats.items() %}
  <div class="metric"><span>{{ k }}</span><b>{{ v }}</b></div>
{% endfor %}
</div>

{% if sections.methods %}
<h2>Methods</h2>
<table>
<tr><th>Artifact</th><th>Value</th></tr>
<tr><td>Segments</td><td>{{ stats.get("segments", 0) }}</td></tr>
<tr><td>Open coding rows</td><td>{{ stats.get("open_codes", 0) }}</td></tr>
<tr><td>Codebook entries</td><td>{{ stats.get("codebook_entries", 0) }}</td></tr>
<tr><td>Axial triples</td><td>{{ stats.get("triples", 0) }}</td></tr>
</table>
{% endif %}

{% if sections.results %}
<h2>Results</h2>
<h3>Gioia View</h3>
<pre>{{ gioia | tojson(indent=2) }}</pre>

<h3>Axial Triples</h3>
<div class="mermaid">
flowchart TD
{% for t in triples %}
  A{{ loop.index }}["{{ t.condition }}"] --> B{{ loop.index }}["{{ t.action }}"] --> C{{ loop.index }}["{{ t.result }}"]
{% endfor %}
</div>

<h3>Code Frequencies</h3>
<table>
<tr><th>Code</th><th>Count</th><th>Relative</th></tr>
{% set max_code_count = analytics.get("code_frequencies", [{}])[0].get("count", 1) if analytics.get("code_frequencies") else 1 %}
{% for row in analytics.get("code_frequencies", [])[:20] %}
<tr><td>{{ row.code }}</td><td>{{ row.count }}</td><td><span class="bar" style="width: {{ (row.count / max_code_count * 100) | round(0) }}%"></span></td></tr>
{% endfor %}
</table>

<h3>Participant Contrasts</h3>
<table>
<tr><th>Participant</th><th>Segments</th><th>Open codes</th><th>Unique codes</th><th>Top codes</th></tr>
{% for row in analytics.get("participant_contrasts", []) %}
<tr><td>{{ row.participant }}</td><td>{{ row.segments }}</td><td>{{ row.open_codes }}</td><td>{{ row.unique_codes }}</td><td>{{ row.top_codes }}</td></tr>
{% endfor %}
</table>

<h3>Negative Cases</h3>
<table>
<tr><th>seg_id</th><th>Participant</th><th>Conflict</th><th>Boundary</th><th>Explanation</th></tr>
{% for row in analytics.get("negative_case_rows", [])[:30] %}
<tr><td>{{ row.seg_id }}</td><td>{{ row.participant }}</td><td>{{ row.conflict_type }}</td><td>{{ row.boundary_condition }}</td><td>{{ row.explanation }}</td></tr>
{% endfor %}
</table>

<h3>Saturation Metrics</h3>
<table>
<tr><th>Name</th><th>Window</th><th>Threshold</th><th>Saturation index</th></tr>
{% for row in saturation_metrics.get("window_metrics", []) %}
<tr><td>{{ row.name }}</td><td>{{ row.window }}</td><td>{{ row.threshold }}</td><td>{{ row.saturation_seg_index }}</td></tr>
{% endfor %}
</table>
{% endif %}

{% if sections.appendices %}
<h2>Appendices</h2>
<h3>Open Codes</h3>
<table>
<tr><th>seg_id</th><th>codes</th><th>memo</th></tr>
{% for row in open_codes[:50] %}
<tr><td>{{ row.seg_id }}</td><td>{{ row.initial_codes | map(attribute='code') | join(', ') }}</td><td>{{ row.quick_memo or "" }}</td></tr>
{% endfor %}
</table>

<h3>Codebook Entries</h3>
<table>
<tr><th>code</th><th>definition</th><th>aliases</th></tr>
{% for e in codebook.entries[:80] %}
<tr><td>{{ e.code }}</td><td>{{ e.definition }}</td><td>{{ e.aliases | join(', ') }}</td></tr>
{% endfor %}
</table>
{% endif %}
</main>
</body>
</html>
"""

_ENV = Environment(autoescape=True)


def emit_html(
    out_path: str,
    stats: Dict[str, Any],
    gioia: Dict[str, Any],
    triples: List[Dict[str, Any]],
    open_codes: List[Any],
    codebook: Any,
    analytics: Optional[Dict[str, Any]] = None,
    saturation_metrics: Optional[Dict[str, Any]] = None,
    template_path: Optional[str] = None,
    sections: Optional[Dict[str, bool]] = None,
) -> None:
    sanitized_triples = [_sanitize_mermaid_fields(t) for t in triples]
    context = {
        "stats": stats,
        "gioia": gioia,
        "triples": sanitized_triples,
        "open_codes": open_codes,
        "codebook": codebook,
        "analytics": analytics or {},
        "saturation_metrics": saturation_metrics or {},
        "sections": {**DEFAULT_SECTIONS, **(sections or {})},
    }
    html = _load_template(template_path).render(**context)
    write_text(out_path, html)


def _load_template(template_path: Optional[str]) -> Template:
    if template_path:
        return _ENV.from_string(read_text(template_path))
    return _ENV.from_string(HTML)


def _sanitize_mermaid_fields(triple: Dict[str, Any]) -> Dict[str, Any]:
    def _clean(val: Any) -> str:
        if not isinstance(val, str):
            return ""
        return val.replace('"', '\\"').replace("\n", " ").replace("\r", " ").strip()

    return {
        **triple,
        "condition": _clean(triple.get("condition", "")),
        "action": _clean(triple.get("action", "")),
        "result": _clean(triple.get("result", "")),
    }
