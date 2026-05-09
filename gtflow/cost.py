
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

def estimate_cost(usage: Usage, price_in: Optional[float], price_out: Optional[float]) -> Optional[float]:
    if price_in is None or price_out is None:
        return None
    return (usage.input_tokens/1000.0)*price_in + (usage.output_tokens/1000.0)*price_out

class UsageAccumulator:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
    def add(self, in_t: int, out_t: int):
        self.input_tokens += int(in_t or 0)
        self.output_tokens += int(out_t or 0)
    def to_usage(self) -> Usage:
        return Usage(self.input_tokens, self.output_tokens)
    def to_dict(self, price_in: Optional[float], price_out: Optional[float]):
        u = self.to_usage()
        cost = estimate_cost(u, price_in, price_out)
        return {
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "total_tokens": u.total_tokens,
            "estimated_cost": round(cost, 6) if cost is not None else None
        }
