from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..providers.base import LLMProvider


def _should_relax_format(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(token in msg for token in ("rate limit", "429", "timeout", "temporarily unavailable")):
        return False
    return any(token in msg for token in ("response_format", "schema", "json", "bad request", "400"))


def _is_context_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "context length",
            "maximum context length",
            "max context length",
            "too many tokens",
            "tokens exceed",
            "too long",
            "overloaded input",
            "length limit",
        )
    )


def _attempt_count(max_retries: int) -> int:
    try:
        return max(1, int(max_retries))
    except Exception:
        return 1


def call_with_retry(
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    operation_name: str = "LLM request",
) -> str:
    err: Optional[Exception] = None
    force_responses = False
    attempts = _attempt_count(max_retries)

    for attempt in range(attempts):
        try:
            if rate_limiter:
                rate_limiter.acquire()
            return provider.generate_text(
                messages,
                response_format=response_format,
                timeout=timeout_sec,
                force_responses=force_responses,
            )
        except Exception as exc:
            err = exc
            if response_format is not None and _should_relax_format(exc):
                response_format = None
            if hasattr(provider, "use_responses") and getattr(provider, "use_responses") is False and _should_relax_format(exc):
                force_responses = True
            if _is_context_error(exc):
                break
            if attempt < attempts - 1:
                time.sleep(backoff_base**attempt)
    raise RuntimeError(f"{operation_name} failed after {attempts} attempts: {err}")
