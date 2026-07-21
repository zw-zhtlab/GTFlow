
from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from ..config import ProviderConfig
import threading

@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0

class LLMProvider:
    def __init__(self, conf: ProviderConfig):
        self.conf = conf
        self._last_usage = UsageStats()
        self._total_usage = UsageStats()
        self._usage_lock = threading.Lock()
        self._attempt_events: List[Dict[str, Any]] = []

    def _update_usage(self, input_tokens: int, output_tokens: int):
        in_tok = int(input_tokens or 0)
        out_tok = int(output_tokens or 0)
        with self._usage_lock:
            self._last_usage = UsageStats(in_tok, out_tok)
            self._total_usage.input_tokens += in_tok
            self._total_usage.output_tokens += out_tok

    def last_usage(self) -> Dict[str, int]:
        with self._usage_lock:
            last = UsageStats(self._last_usage.input_tokens, self._last_usage.output_tokens)
        return {
            "input_tokens": last.input_tokens,
            "output_tokens": last.output_tokens,
            "total_tokens": last.input_tokens + last.output_tokens,
        }

    def total_usage(self) -> Dict[str, int]:
        with self._usage_lock:
            total = UsageStats(self._total_usage.input_tokens, self._total_usage.output_tokens)
        return {
            "input_tokens": total.input_tokens,
            "output_tokens": total.output_tokens,
            "total_tokens": total.input_tokens + total.output_tokens,
        }

    def reset_usage_totals(self):
        with self._usage_lock:
            self._total_usage = UsageStats()
            self._attempt_events = []

    def record_attempt(self, event: Dict[str, Any]) -> None:
        """Store bounded, secret-free telemetry for each outer retry attempt."""
        allowed = {
            "operation",
            "attempt",
            "max_attempts",
            "outcome",
            "classification",
            "status_code",
            "error_type",
            "compatibility_recovery",
            "delay_seconds",
            "duration_ms",
        }
        sanitized = {key: event.get(key) for key in allowed if key in event}
        with self._usage_lock:
            self._attempt_events.append(sanitized)
            if len(self._attempt_events) > 1000:
                del self._attempt_events[: len(self._attempt_events) - 1000]

    def attempt_telemetry(self) -> List[Dict[str, Any]]:
        with self._usage_lock:
            return [dict(event) for event in self._attempt_events]

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        raise NotImplementedError

def make_provider(conf: ProviderConfig) -> LLMProvider:
    name = (conf.name or "openai_compatible").lower()
    if name in ("openai_compatible","openai","ollama"):
        from .openai_compatible import OpenAICompatibleProvider
        return OpenAICompatibleProvider(conf)
    elif name == "azure_openai":
        from .azure_openai_provider import AzureOpenAIProvider
        return AzureOpenAIProvider(conf)
    elif name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(conf)
    else:
        raise ValueError(f"Unknown provider: {name}")
