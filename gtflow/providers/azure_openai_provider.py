
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
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
        endpoint = conf.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = conf.deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_version = conf.api_version or os.getenv("AZURE_OPENAI_API_VERSION")
        api_key = conf.api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if not endpoint or not deployment or not api_key:
            raise ValueError("AzureOpenAI requires endpoint, deployment and api_key.")
        self.url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        self.headers = {"api-key": api_key, "Content-Type": "application/json"}

    def _content_to_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif hasattr(item, "text"):
                    try:
                        parts.append(str(item.text))
                    except Exception:
                        pass
                elif isinstance(item, dict):
                    txt = item.get("text") or item.get("content") or item.get("data")
                    if txt:
                        parts.append(str(txt))
            return "".join(parts)
        if hasattr(content, "text"):
            try:
                return str(content.text)
            except Exception:
                pass
        return str(content)

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        payload = {
            "messages": messages,
            "temperature": kwargs.get("temperature", self.conf.temperature),
            "max_tokens": kwargs.get("max_tokens", self.conf.max_tokens),
        }
        if response_format:
            payload["response_format"] = response_format
        try:
            timeout = kwargs.get("timeout")
            r = requests.post(self.url, headers=self.headers, json=payload, timeout=timeout or 60)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {}) or {}
            prompt = int(usage.get("prompt_tokens", 0) or 0)
            completion = int(usage.get("completion_tokens", 0) or 0)
            self._update_usage(prompt, completion)
            msg = (data.get("choices") or [{}])[0].get("message", {}) if isinstance(data, dict) else {}
            return self._content_to_text(msg.get("content"))
        except Exception as e:
            self._update_usage(0, 0)
            raise RuntimeError(f"AzureOpenAI request failed: {e}")
