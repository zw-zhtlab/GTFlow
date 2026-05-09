from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..models.schemas import Codebook, CodebookEntry


def codebook_to_alignment_rows(codebook: Codebook) -> List[Dict[str, Any]]:
    code_to_theme = _invert_mapping(codebook.second_order_themes)
    theme_to_dimension = _invert_mapping(codebook.aggregate_dimensions)
    rows: List[Dict[str, Any]] = []
    for entry in codebook.entries:
        theme = code_to_theme.get(entry.code, "")
        rows.append(
            {
                "old_code": entry.code,
                "code": entry.code,
                "definition": entry.definition,
                "second_order_theme": theme,
                "aggregate_dimension": theme_to_dimension.get(theme, ""),
                "aliases": ", ".join(entry.aliases),
            }
        )
    return rows


def batch_align_rows(
    rows: Iterable[Dict[str, Any]],
    code_contains: str = "",
    second_order_theme: Optional[str] = None,
    aggregate_dimension: Optional[str] = None,
) -> List[Dict[str, Any]]:
    needle = code_contains.strip().lower()
    out: List[Dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        haystack = " ".join(
            str(updated.get(key, ""))
            for key in ("code", "definition", "aliases", "second_order_theme", "aggregate_dimension")
        ).lower()
        if not needle or needle in haystack:
            if second_order_theme is not None and second_order_theme.strip():
                updated["second_order_theme"] = second_order_theme.strip()
            if aggregate_dimension is not None and aggregate_dimension.strip():
                updated["aggregate_dimension"] = aggregate_dimension.strip()
        out.append(updated)
    return out


def apply_gioia_alignment_edits(codebook: Codebook, rows: Iterable[Dict[str, Any]]) -> Codebook:
    original_by_code = {entry.code: entry for entry in codebook.entries}
    entries: List[CodebookEntry] = []
    second_order: Dict[str, List[str]] = {}
    aggregate: Dict[str, List[str]] = {}
    seen_codes: set[str] = set()

    for row in rows:
        code = str(row.get("code") or "").strip()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        original = original_by_code.get(str(row.get("old_code") or "").strip()) or original_by_code.get(code)
        entry_data = original.model_dump() if original else {}
        entry_data["code"] = code
        if "definition" in row:
            entry_data["definition"] = str(row.get("definition") or "").strip()
        entry_data["aliases"] = _split_list(row.get("aliases"))
        entries.append(CodebookEntry.model_validate(entry_data))

        theme = str(row.get("second_order_theme") or "").strip()
        dimension = str(row.get("aggregate_dimension") or "").strip()
        if theme:
            second_order.setdefault(theme, [])
            if code not in second_order[theme]:
                second_order[theme].append(code)
        if theme and dimension:
            aggregate.setdefault(dimension, [])
            if theme not in aggregate[dimension]:
                aggregate[dimension].append(theme)

    return Codebook(entries=entries, second_order_themes=second_order, aggregate_dimensions=aggregate)


def _invert_mapping(mapping: Dict[str, List[str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for parent, children in mapping.items():
        for child in children:
            out.setdefault(str(child), str(parent))
    return out


def _split_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]
