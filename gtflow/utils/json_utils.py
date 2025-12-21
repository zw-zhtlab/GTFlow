
import json
import re
from typing import Any

def try_parse_json(s: str) -> Any:
    if not isinstance(s, str):
        return s
    # strip code fences
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    # try to locate first and last braces/brackets
    start = min([x for x in [s.find("{"), s.find("[")] if x != -1], default=-1)
    end_brace = s.rfind("}")
    end_bracket = s.rfind("]")
    end = max(end_brace, end_bracket)
    if start != -1 and end != -1 and end > start:
        s = s[start:end+1]
    def _loads(value: str) -> Any:
        return json.loads(value)

    def _repair(value: str) -> Any:
        try:
            from json_repair import repair_json as _repair_json  # type: ignore
        except Exception:
            return None
        try:
            repaired = _repair_json(value)
        except Exception:
            return None
        if isinstance(repaired, str):
            try:
                return json.loads(repaired)
            except Exception:
                return None
        return repaired

    try:
        return _loads(s)
    except Exception:
        # fix common trailing commas / stray control characters
        s2 = re.sub(r",\s*([}\]])", r"\1", s)
        s2 = re.sub(r"[\x00-\x1F]+", " ", s2)
        try:
            return _loads(s2)
        except Exception:
            repaired = _repair(s2)
            if repaired is not None:
                return repaired
            repaired = _repair(s)
            if repaired is not None:
                return repaired
            raise
