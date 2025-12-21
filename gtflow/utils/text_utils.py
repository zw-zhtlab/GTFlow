import re
from typing import List, Optional, Tuple

# Match both ASCII and full-width colons so Chinese speaker labels are captured.
_DIALOG_LINE = re.compile(r"^([^:：]+)[:：](.+)$")
# Prefer natural splits on common sentence-ending punctuation (ASCII + Chinese).
_SPLIT_PUNCTUATION = (".", "!", "?", ";", "。", "！", "？", "；")


def split_dialog(text: str, max_chars: int) -> List[Tuple[Optional[str], str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pairs: List[Tuple[Optional[str], str]] = []
    speaker: Optional[str] = None
    buf: List[str] = []
    for line in lines:
        match = _DIALOG_LINE.match(line)
        if match:
            if buf:
                chunk = " ".join(buf).strip()
                for part in chunk_split(chunk, max_chars):
                    pairs.append((speaker, part))
            speaker = match.group(1).strip()
            buf = [match.group(2).strip()]
        else:
            buf.append(line)
    if buf:
        chunk = " ".join(buf).strip()
        for part in chunk_split(chunk, max_chars):
            pairs.append((speaker, part))
    return pairs


def split_paragraph(text: str, max_chars: int) -> List[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: List[str] = []
    for para in paras:
        out.extend(chunk_split(para, max_chars))
    return out


def split_lines(text: str, max_chars: int) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    out: List[str] = []
    for line in lines:
        out.extend(chunk_split(line, max_chars))
    return out


def chunk_split(s: str, max_chars: int) -> List[str]:
    s = s.strip()
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(s) <= max_chars:
        return [s]
    out: List[str] = []
    start = 0
    while start < len(s):
        end = min(len(s), start + max_chars)
        best_idx = -1
        best_len = 0
        for punct in _SPLIT_PUNCTUATION:
            idx = s.rfind(punct, start, end)
            if idx != -1 and idx > best_idx:
                best_idx = idx
                best_len = len(punct)
        cut = best_idx + best_len if best_idx != -1 else -1
        if cut == -1 or cut <= start:
            cut = end
        out.append(s[start:cut].strip())
        start = cut
    return [chunk for chunk in out if chunk]
