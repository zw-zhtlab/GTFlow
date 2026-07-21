from __future__ import annotations
from typing import Any, Iterable, Iterator, List
import os
import json

def write_jsonl(path: str, records: Iterable[Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")

def append_jsonl(path: str, records: Iterable[Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write("\n")

def iter_jsonl(path: str) -> Iterator[Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL in {path} at line {line_no}: {exc.msg}"
                ) from exc

def iter_jsonl_batches(path: str, batch_size: int) -> Iterator[List[Any]]:
    batch: List[Any] = []
    for rec in iter_jsonl(path):
        batch.append(rec)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def count_jsonl(path: str) -> int:
    count = 0
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                count += 1
    return count
