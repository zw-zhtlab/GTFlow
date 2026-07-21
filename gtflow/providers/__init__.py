
"""Provider interfaces with SDK implementations loaded only when requested.

Importing :mod:`gtflow.providers` is part of CLI and UI startup, so importing an
optional provider SDK here makes every command pay its startup cost.  The lazy
attributes below preserve the public API without importing ``openai`` or
``anthropic`` until that provider is actually used.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .base import LLMProvider, make_provider

if TYPE_CHECKING:
    from .anthropic_provider import AnthropicProvider
    from .azure_openai_provider import AzureOpenAIProvider
    from .openai_compatible import OpenAICompatibleProvider

__all__ = [
    "LLMProvider",
    "make_provider",
    "OpenAICompatibleProvider",
    "AzureOpenAIProvider",
    "AnthropicProvider",
]

_LAZY_PROVIDERS = {
    "OpenAICompatibleProvider": (".openai_compatible", "OpenAICompatibleProvider"),
    "AzureOpenAIProvider": (".azure_openai_provider", "AzureOpenAIProvider"),
    "AnthropicProvider": (".anthropic_provider", "AnthropicProvider"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _LAZY_PROVIDERS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
