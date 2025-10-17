
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
    try:
        return json.loads(s)
    except Exception:
        # fix common trailing commas / stray control characters
        s2 = re.sub(r",\s*([}\]])", r"\1", s)
        s2 = re.sub(r"[\x00-\x1F]+", " ", s2)
        return json.loads(s2)
