
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
from openai import OpenAI
from .base import LLMProvider

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, conf):
        super().__init__(conf)
        base_url = conf.base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = conf.api_key or os.getenv("OPENAI_API_KEY")
        organization = conf.organization or os.getenv("OPENAI_ORG_ID")
        headers = {}
        if conf.extra_headers:
            headers.update(conf.extra_headers)
        self.client = OpenAI(base_url=base_url, api_key=api_key, organization=organization, default_headers=headers)
        self.use_responses = bool(conf.use_responses_api)

    def _extract_and_update_usage(self, obj: Any):
        try:
            usage = getattr(obj, "usage", None) or {}
            prompt = int(getattr(usage, "prompt_tokens", 0) or usage.get("prompt_tokens", 0) or 0)
            completion = int(getattr(usage, "completion_tokens", 0) or usage.get("completion_tokens", 0) or 0)
            self._update_usage(prompt, completion)
        except Exception:
            self._update_usage(0, 0)

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        model = kwargs.get("model") or self.conf.model
        temperature = kwargs.get("temperature", self.conf.temperature)
        max_tokens = kwargs.get("max_tokens", self.conf.max_tokens)
        timeout = kwargs.get("timeout")

        if self.use_responses:
            try:
                resp = self.client.responses.create(
                    model=model,
                    input={"type": "input_text", "text": messages[-1]["content"]} if (len(messages)==1 and messages[0]["role"]=="user") else None,
                    messages=messages if not (len(messages)==1 and messages[0]["role"]=="user") else None,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                )
                self._extract_and_update_usage(resp)
                if hasattr(resp, "output_text"):
                    return resp.output_text
                try:
                    return resp.choices[0].message.content
                except Exception:
                    return str(resp)
            except Exception:
                pass

        kwargs_payload = dict(model=model, messages=messages, temperature=temperature)
        if max_tokens:
            kwargs_payload["max_tokens"] = max_tokens
        if response_format:
            kwargs_payload["response_format"] = response_format

        if timeout is not None:
            kwargs_payload["timeout"] = timeout
        resp = self.client.chat.completions.create(**kwargs_payload)
        self._extract_and_update_usage(resp)
        return resp.choices[0].message.content
