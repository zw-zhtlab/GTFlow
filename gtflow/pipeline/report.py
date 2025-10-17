
from __future__ import annotations
from typing import List, Dict, Any
from ..utils.file_io import write_text

def emit_markdown(out_path: str, stats: Dict[str, Any], tables: Dict[str, List[Dict[str,Any]]]):
    lines = ["# GTFlow Grounded Theory Report", ""]
    lines.append("## Stats")
    for k,v in stats.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    for name, rows in tables.items():
        lines.append(f"## {name}")
        if not rows:
            lines.append("_Empty_")
            continue
        headers = list(rows[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"]*len(headers)) + "|")
        for r in rows:
            lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
        lines.append("")
    write_text(out_path, "\n".join(lines))
