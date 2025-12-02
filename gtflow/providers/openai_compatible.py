
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

    def _content_to_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
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

    def _extract_and_update_usage(self, obj: Any):
        try:
            usage = getattr(obj, "usage", None) or {}
            # /v1/chat/completions returns prompt/completion tokens; /v1/responses returns input/output tokens.
            prompt = (
                getattr(usage, "prompt_tokens", None)
                or usage.get("prompt_tokens", None)
                or getattr(usage, "input_tokens", None)
                or usage.get("input_tokens", 0)
            )
            completion = (
                getattr(usage, "completion_tokens", None)
                or usage.get("completion_tokens", None)
                or getattr(usage, "output_tokens", None)
                or usage.get("output_tokens", 0)
            )
            self._update_usage(prompt, completion)
        except Exception:
            self._update_usage(0, 0)

    def _messages_to_responses_input(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for msg in messages:
            role = msg.get("role") or "user"
            content = msg.get("content")
            if content is None:
                continue
            out.append({"role": role, "content": content})
        return out

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        model = kwargs.get("model") or self.conf.model
        temperature = kwargs.get("temperature", self.conf.temperature)
        max_tokens = kwargs.get("max_tokens", self.conf.max_tokens)
        timeout = kwargs.get("timeout")

        if self.use_responses:
            try:
                resp = self.client.responses.create(
                    model=model,
                    input=self._messages_to_responses_input(messages),
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                )
                self._extract_and_update_usage(resp)
                if hasattr(resp, "output_text"):
                    return resp.output_text
                try:
                    return self._content_to_text(resp.output[0].content)
                except Exception:
                    try:
                        return self._content_to_text(resp.choices[0].message.content)
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
        return self._content_to_text(resp.choices[0].message.content)
