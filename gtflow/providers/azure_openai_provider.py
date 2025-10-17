
from __future__ import annotations
from typing import Any, Dict, List, Optional
import requests
from .base import LLMProvider

class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI (not strictly the same path as OpenAI).

    Requires:
      - conf.endpoint (e.g., https://YOUR-RESOURCE.openai.azure.com)
      - conf.deployment (Azure deployment name)
      - conf.api_version (e.g., 2024-02-15-preview)
      - conf.api_key
    """
    def __init__(self, conf):
        super().__init__(conf)
        if not conf.endpoint or not conf.deployment or not conf.api_key:
            raise ValueError("AzureOpenAI requires endpoint, deployment and api_key.")
        self.url = f"{conf.endpoint}/openai/deployments/{conf.deployment}/chat/completions?api-version={conf.api_version}"
        self.headers = {"api-key": conf.api_key, "Content-Type": "application/json"}

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        payload = {
            "messages": messages,
            "temperature": kwargs.get("temperature", self.conf.temperature),
            "max_tokens": kwargs.get("max_tokens", self.conf.max_tokens),
        }
        try:
            r = requests.post(self.url, headers=self.headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {}) or {}
            prompt = int(usage.get("prompt_tokens", 0) or 0)
            completion = int(usage.get("completion_tokens", 0) or 0)
            self._update_usage(prompt, completion)
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            self._update_usage(0, 0)
            raise RuntimeError(f"AzureOpenAI request failed: {e}")
