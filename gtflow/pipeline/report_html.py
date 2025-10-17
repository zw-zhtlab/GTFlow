
from __future__ import annotations
from typing import List, Dict, Any
from jinja2 import Template
from ..utils.file_io import write_text

HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8"/>
<title>GTFlow Report</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({ startOnLoad: true });</script>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, "Microsoft YaHei", sans-serif; padding: 24px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #ddd; padding: 8px; }
th { background: #f7f7f7; }
pre { background: #f9f9f9; padding: 12px; overflow: auto; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; background: #eef; margin-right: 6px; }
</style>
</head>
<body>
<h1>GTFlow Grounded Theory Report</h1>
<h2>Stats</h2>
<ul>
{% for k,v in stats.items() %}
<li><b>{{k}}</b>: {{v}}</li>
{% endfor %}
</ul>

<h2>Gioia View</h2>
<pre>{{gioia | tojson(indent=2)}}</pre>

<h2>Axial Triples (Mermaid)</h2>
<div class="mermaid">
flowchart TD
{% for t in triples %}
  A{{ loop.index }}["{{t.condition}}"] --> B{{ loop.index }}["{{t.action}}"] --> C{{ loop.index }}["{{t.result}}"]
{% endfor %}
</div>

<h2>Open Codes (first 20)</h2>
<table>
<tr><th>seg_id</th><th>codes</th></tr>
{% for row in open_codes[:20] %}
<tr><td>{{row.seg_id}}</td><td>{{ row.initial_codes | map(attribute='code') | join(', ') }}</td></tr>
{% endfor %}
</table>

<h2>Codebook Entries (first 20)</h2>
<table>
<tr><th>code</th><th>definition</th></tr>
{% for e in codebook.entries[:20] %}
<tr><td>{{e.code}}</td><td>{{e.definition}}</td></tr>
{% endfor %}
</table>

</body>
</html>
"""

def emit_html(out_path: str, stats: Dict[str, Any], gioia: Dict[str, Any], triples: List[Dict[str,str]], open_codes: List[Any], codebook: Any):
    html = Template(HTML).render(stats=stats, gioia=gioia, triples=triples, open_codes=open_codes, codebook=codebook)
    write_text(out_path, html)
