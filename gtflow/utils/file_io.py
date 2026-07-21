
from __future__ import annotations
import os, json, csv, tempfile
from typing import Any, List, Dict

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def read_text(p: str) -> str:
    with open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

def write_text(p: str, s: str):
    ensure_dir(os.path.dirname(p) or ".")
    target_dir = os.path.dirname(os.path.abspath(p)) or "."
    fd, temp_path = tempfile.mkstemp(prefix=".gtflow-", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(s)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, p)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise

def read_json(p: str) -> Any:
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def write_json(p: str, obj: Any, pretty: bool=True):
    # Serialize completely before the atomic temporary-file replacement so a
    # validation/serialization error cannot destroy the previous artifact.
    payload = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None)
    write_text(p, payload)

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
