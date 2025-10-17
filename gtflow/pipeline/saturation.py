
from __future__ import annotations
from typing import List, Dict, Tuple

def saturation(open_codes: List[Dict], window: int = 20, threshold: float = 0.05) -> Dict:
    seen = set()
    new_counts = []
    for item in open_codes:
        n_new = 0
        for ic in item.get("initial_codes", []):
            c = ic.get("code", "").strip().lower()
            if c and c not in seen:
                seen.add(c)
                n_new += 1
        new_counts.append(n_new)
    rates = []
    for i in range(len(new_counts)):
        lo = max(0, i-window+1)
        s = sum(new_counts[lo:i+1])
        rates.append(s / max(1, (i-lo+1)))
    idx = None
    consec = 0
    for i, r in enumerate(rates):
        if r <= threshold:
            consec += 1
            if consec >= 3:
                idx = i
                break
        else:
            consec = 0
    return {"window": window, "threshold": threshold, "saturation_seg_index": idx, "rates": rates}
