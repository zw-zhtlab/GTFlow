
from __future__ import annotations
from typing import Any, Dict, List, Optional
import ipaddress
import os
from urllib.parse import urlsplit
from .base import LLMProvider


def _is_loopback_url(value: str) -> bool:
    try:
        host = (urlsplit(value).hostname or "").rstrip(".").lower()
    except ValueError:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, conf):
        super().__init__(conf)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI-compatible provider requires the 'openai' package. "
                "Install GTFlow with its default dependencies."
            ) from exc
        provider_name = (conf.name or "openai_compatible").lower()
        default_base_url = "http://localhost:11434/v1" if provider_name == "ollama" else "https://api.openai.com/v1"
        base_url = conf.base_url or os.getenv("OPENAI_BASE_URL") or default_base_url
        # A caller-selected endpoint must never inherit a process-wide credential.
        # Otherwise a request to the local UI could point at an attacker and cause
        # the server's OPENAI_API_KEY to be sent there.
        api_key = conf.api_key
        if not api_key and not conf.base_url:
            api_key = os.getenv("OPENAI_API_KEY")
        if provider_name == "ollama" and not api_key:
            api_key = "ollama"
        if not api_key:
            raise ValueError("An explicit API key is required when using a custom base URL.")
        organization = conf.organization
        if not organization and not conf.base_url:
            organization = os.getenv("OPENAI_ORG_ID")
        headers = {}
        if conf.extra_headers:
            headers.update(conf.extra_headers)
        # GTFlow owns the bounded retry policy and telemetry. Disable the SDK's
        # implicit retry loop so one configured attempt maps to one HTTP attempt.
        client_options: Dict[str, Any] = {
            "base_url": base_url,
            "api_key": api_key,
            "organization": organization,
            "default_headers": headers,
            "max_retries": 0,
        }
        if _is_loopback_url(str(base_url)):
            # On Windows, HTTPX may inherit the system proxy even when no proxy
            # environment variable is present. Loopback provider traffic must
            # stay on-device instead of leaking through that proxy.
            import httpx

            client_options["http_client"] = httpx.Client(trust_env=False)
        self.client = OpenAI(**client_options)
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
            def value_for(*names: str) -> int:
                for name in names:
                    value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
                    if value is not None:
                        return int(value)
                return 0

            prompt = value_for("prompt_tokens", "input_tokens")
            completion = value_for("completion_tokens", "output_tokens")
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

    def _response_format_to_text_config(self, response_format: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert chat-completions response_format to Responses API text.format."""
        if not response_format or not isinstance(response_format, dict):
            return None
        fmt_type = response_format.get("type")
        if fmt_type == "json_object":
            return {"format": {"type": "json_object"}}
        if fmt_type == "json_schema":
            schema_block = response_format.get("json_schema")
            if not isinstance(schema_block, dict):
                return None
            name = schema_block.get("name")
            schema = schema_block.get("schema")
            if not isinstance(name, str) or not isinstance(schema, dict):
                return None
            text_format: Dict[str, Any] = {
                "type": "json_schema",
                "name": name,
                "schema": schema,
            }
            if "strict" in schema_block:
                text_format["strict"] = bool(schema_block.get("strict"))
            if isinstance(schema_block.get("description"), str):
                text_format["description"] = schema_block.get("description")
            return {"format": text_format}
        return None

    def _can_fallback_from_responses(self, exc: Exception) -> bool:
        """Allow endpoint-compatibility fallback, never a nested transient retry."""
        status = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if status is None and response is not None:
            status = getattr(response, "status_code", None)
        try:
            status = int(status) if status is not None else None
        except (TypeError, ValueError):
            status = None
        message = str(exc).lower()
        if any(
            token in message
            for token in (
                "context length",
                "maximum context length",
                "too many tokens",
                "rate limit",
                "timeout",
                "temporarily unavailable",
            )
        ):
            return False
        if status in {400, 404, 405, 415, 422, 501}:
            return True
        if status is not None:
            return False
        return isinstance(exc, (AttributeError, NotImplementedError)) or any(
            token in message
            for token in ("responses endpoint", "unknown endpoint", "method not allowed", "unsupported endpoint")
        )

    def generate_text(self, messages: List[Dict[str, str]], response_format: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        force_responses = bool(kwargs.pop("force_responses", False))
        force_chat = bool(kwargs.pop("force_chat", False))
        model = kwargs.get("model") or self.conf.model
        temperature = kwargs.get("temperature", self.conf.temperature)
        max_tokens = kwargs.get("max_tokens", self.conf.max_tokens)
        timeout = kwargs.get("timeout")
        responses_exc: Optional[Exception] = None

        if (self.use_responses or force_responses) and not force_chat:
            try:
                payload: Dict[str, Any] = {
                    "model": model,
                    "input": self._messages_to_responses_input(messages),
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
                text_config = self._response_format_to_text_config(response_format)
                if text_config is not None:
                    payload["text"] = text_config
                if timeout is not None:
                    payload["timeout"] = timeout
                resp = self.client.responses.create(**payload)
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
            except Exception as exc:
                if not self._can_fallback_from_responses(exc):
                    raise
                responses_exc = exc

        kwargs_payload = dict(model=model, messages=messages, temperature=temperature)
        if max_tokens:
            kwargs_payload["max_tokens"] = max_tokens
        if response_format:
            kwargs_payload["response_format"] = response_format

        if timeout is not None:
            kwargs_payload["timeout"] = timeout
        try:
            resp = self.client.chat.completions.create(**kwargs_payload)
        except Exception as chat_exc:
            if responses_exc is not None:
                raise RuntimeError(
                    "OpenAI-compatible request failed on both /v1/responses and /v1/chat/completions"
                ) from chat_exc
            raise
        self._extract_and_update_usage(resp)
        return self._content_to_text(resp.choices[0].message.content)
