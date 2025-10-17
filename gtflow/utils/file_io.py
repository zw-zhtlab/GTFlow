
from __future__ import annotations
import os, json, csv
from typing import Any, List, Dict

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def read_text(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def write_text(p: str, s: str):
    ensure_dir(os.path.dirname(p) or ".")
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)

def read_json(p: str) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(p: str, obj: Any, pretty: bool=True):
    ensure_dir(os.path.dirname(p) or ".")
    with open(p, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        else:
            json.dump(obj, f, ensure_ascii=False)

def write_csv(p: str, rows: List[Dict[str, Any]]):
    ensure_dir(os.path.dirname(p) or ".")
    if not rows:
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    headers = list(rows[0].keys())
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)
