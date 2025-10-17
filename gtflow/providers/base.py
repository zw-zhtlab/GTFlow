
from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from ..config import ProviderConfig

@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0

class LLMProvider:
    def __init__(self, conf: ProviderConfig):
        self.conf = conf
        self._last_usage = UsageStats()
        self._total_usage = UsageStats()

    def _update_usage(self, input_tokens: int, output_tokens: int):
        self._last_usage = UsageStats(int(input_tokens or 0), int(output_tokens or 0))
        self._total_usage.input_tokens += int(input_tokens or 0)
        self._total_usage.output_tokens += int(output_tokens or 0)

    def last_usage(self) -> Dict[str, int]:
        return {
            "input_tokens": self._last_usage.input_tokens,
            "output_tokens": self._last_usage.output_tokens,
            "total_tokens": self._last_usage.input_tokens + self._last_usage.output_tokens,
        }

    def total_usage(self) -> Dict[str, int]:
        return {
            "input_tokens": self._total_usage.input_tokens,
            "output_tokens": self._total_usage.output_tokens,
            "total_tokens": self._total_usage.input_tokens + self._total_usage.output_tokens,
        }

    def reset_usage_totals(self):
        self._total_usage = UsageStats()

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
