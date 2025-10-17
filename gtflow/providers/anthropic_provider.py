
from __future__ import annotations
from typing import Any, Dict, List, Optional
from anthropic import Anthropic
from .base import LLMProvider

class AnthropicProvider(LLMProvider):
    def __init__(self, conf):
        super().__init__(conf)
        self.client = Anthropic(api_key=conf.api_key)

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        # Convert OpenAI-style messages to Anthropic format
        sys = None
        converted = []
        for m in messages:
            if m["role"] == "system":
                sys = m["content"]
            elif m["role"] in ("user", "assistant"):
                converted.append({"role": m["role"], "content": m["content"]})
        resp = self.client.messages.create(
            model=kwargs.get("model") or self.conf.model,
            system=sys,
            max_tokens=kwargs.get("max_tokens", self.conf.max_tokens),
            temperature=kwargs.get("temperature", self.conf.temperature),
            messages=converted
        )
        try:
            u = resp.usage
            self._update_usage(int(u.input_tokens), int(u.output_tokens))
        except Exception:
            self._update_usage(0, 0)
        # collect text parts
        return "".join([getattr(c, "text", "") for c in resp.content if getattr(c, "type", None) == "text"])
