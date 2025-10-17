
from __future__ import annotations
from typing import Dict, List
from ..models.schemas import Codebook

def to_gioia(codebook: Codebook) -> Dict[str, List[str]]:
    view = {
        "first_order": [e.code for e in codebook.entries],
        "second_order": list(codebook.second_order_themes.keys()),
        "aggregate_dimensions": list(codebook.aggregate_dimensions.keys()),
    }
    return view
