
from __future__ import annotations
from typing import Iterable, List, Dict, Optional, Tuple

def saturation(open_codes: Iterable[Dict], window: int = 20, threshold: float = 0.05) -> Dict:
    new_counts, cumulative_unique = _new_code_counts(open_codes)
    result = _saturation_from_counts(new_counts, window, threshold)
    result["cumulative_unique"] = cumulative_unique
    result["total_unique_codes"] = cumulative_unique[-1] if cumulative_unique else 0
    return result


def saturation_suite(
    open_codes: Iterable[Dict],
    windows: Tuple[int, ...] = (5, 10, 20),
    thresholds: Tuple[float, ...] = (0.05, 0.1),
) -> Dict:
    new_counts, cumulative_unique = _new_code_counts(open_codes)
    default = _saturation_from_counts(new_counts, 20, 0.05)
    default["cumulative_unique"] = cumulative_unique
    default["total_unique_codes"] = cumulative_unique[-1] if cumulative_unique else 0

    window_metrics = []
    for window in windows:
        for threshold in thresholds:
            item = _saturation_from_counts(new_counts, window, threshold)
            item["name"] = f"window_{window}_threshold_{threshold:g}"
            window_metrics.append(item)

    novelty_curve = [
        {"index": idx, "new_codes": count, "cumulative_unique": cumulative_unique[idx]}
        for idx, count in enumerate(new_counts)
    ]
    return {
        "default": default,
        "window_metrics": window_metrics,
        "novelty_curve": novelty_curve,
        "total_segments": len(new_counts),
        "total_unique_codes": cumulative_unique[-1] if cumulative_unique else 0,
    }


def _new_code_counts(open_codes: Iterable[Dict]) -> Tuple[List[int], List[int]]:
    seen = set()
    new_counts = []
    cumulative_unique = []
    for item in open_codes:
        n_new = 0
        for ic in _initial_codes(item):
            c = _code_text(ic).strip().lower()
            if c and c not in seen:
                seen.add(c)
                n_new += 1
        new_counts.append(n_new)
        cumulative_unique.append(len(seen))
    return new_counts, cumulative_unique


def _saturation_from_counts(new_counts: List[int], window: int, threshold: float) -> Dict:
    rates: List[Optional[float]] = []
    for i in range(len(new_counts)):
        # Partial prefixes are not windows. Treating the first three empty
        # segments as three low-novelty windows caused false saturation before
        # enough material had even been observed.
        if i + 1 < window:
            rates.append(None)
            continue
        lo = i - window + 1
        rates.append(sum(new_counts[lo : i + 1]) / window)
    idx = None
    consec = 0
    for i, r in enumerate(rates):
        if r is not None and r <= threshold:
            consec += 1
            if consec >= 3:
                idx = i
                break
        else:
            consec = 0
    return {
        "metric_label": "code_novelty",
        "metric_definition": "mean newly observed unique codes per source segment over a complete rolling window",
        "window": window,
        "threshold": threshold,
        "saturation_seg_index": idx,
        "rates": rates,
    }


def _initial_codes(item):
    if isinstance(item, dict):
        return item.get("initial_codes", [])
    return getattr(item, "initial_codes", []) or []


def _code_text(initial_code) -> str:
    if isinstance(initial_code, dict):
        return str(initial_code.get("code") or "")
    return str(getattr(initial_code, "code", "") or "")
