import re
from typing import List, Tuple

_DIALOG_LINE = re.compile(r"^([^:]+):(.+)$")
_SPLIT_PUNCTUATION = (".", "!", "?", ";")


def split_dialog(text: str, max_chars: int) -> List[Tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pairs: List[Tuple[str, str]] = []
    speaker = None
    buf: List[str] = []
    for line in lines:
        match = _DIALOG_LINE.match(line)
        if match:
            if buf and speaker:
                chunk = " ".join(buf).strip()
                for part in chunk_split(chunk, max_chars):
                    pairs.append((speaker, part))
            speaker = match.group(1).strip()
            buf = [match.group(2).strip()]
        else:
            buf.append(line)
    if buf and speaker:
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
    if len(s) <= max_chars:
        return [s]
    out: List[str] = []
    start = 0
    while start < len(s):
        end = min(len(s), start + max_chars)
        cut = -1
        for punct in _SPLIT_PUNCTUATION:
            cut = s.rfind(punct, start, end)
            if cut != -1:
                cut += len(punct)
                break
        if cut == -1 or cut <= start:
            cut = end
        out.append(s[start:cut].strip())
        start = cut
    return [chunk for chunk in out if chunk]
