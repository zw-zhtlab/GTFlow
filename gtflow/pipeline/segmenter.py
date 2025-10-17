
from __future__ import annotations
from typing import List
from ..models.schemas import Segment
from ..utils import text_utils

def segment_dialog(text: str, max_chars: int) -> List[Segment]:
    pairs = text_utils.split_dialog(text, max_chars)
    segs = []
    for i, (speaker, chunk) in enumerate(pairs, start=1):
        segs.append(Segment(seg_id=f"{i:04d}", text=chunk, speaker=speaker))
    return segs

def segment_paragraph(text: str, max_chars: int) -> List[Segment]:
    chunks = text_utils.split_paragraph(text, max_chars)
    return [Segment(seg_id=f"{i:04d}", text=c) for i, c in enumerate(chunks, start=1)]

def segment_line(text: str, max_chars: int) -> List[Segment]:
    chunks = text_utils.split_lines(text, max_chars)
    return [Segment(seg_id=f"{i:04d}", text=c) for i, c in enumerate(chunks, start=1)]
