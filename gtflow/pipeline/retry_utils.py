from __future__ import annotations

import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional

from ..providers.base import LLMProvider


_TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_TRANSIENT_MESSAGE_TOKENS = (
    "rate limit",
    "too many requests",
    "temporarily unavailable",
    "service unavailable",
    "connection reset",
    "connection aborted",
    "connection refused",
    "connection error",
    "timed out",
    "timeout",
    "overloaded",
    "try again",
)


class PipelineCancelled(RuntimeError):
    """Raised when a bounded background run requests cooperative cancellation."""


def _exception_chain(exc: BaseException) -> Iterable[BaseException]:
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _status_code(exc: BaseException) -> Optional[int]:
    for current in _exception_chain(exc):
        candidates = [
            getattr(current, "status_code", None),
            getattr(current, "status", None),
        ]
        response = getattr(current, "response", None)
        if response is not None:
            candidates.extend(
                [getattr(response, "status_code", None), getattr(response, "status", None)]
            )
        for candidate in candidates:
            try:
                code = int(candidate)
            except (TypeError, ValueError):
                continue
            if 100 <= code <= 599:
                return code
    match = re.search(r"(?<!\d)(4\d\d|5\d\d)(?!\d)", str(exc))
    return int(match.group(1)) if match else None


def _headers(exc: BaseException) -> Dict[str, str]:
    for current in _exception_chain(exc):
        response = getattr(current, "response", None)
        raw = getattr(response, "headers", None) if response is not None else None
        if raw is None:
            raw = getattr(current, "headers", None)
        if raw is not None and hasattr(raw, "items"):
            return {str(key).lower(): str(value) for key, value in raw.items()}
    return {}


def retry_after_seconds(exc: BaseException, *, now: Optional[datetime] = None) -> Optional[float]:
    value = _headers(exc).get("retry-after")
    if not value:
        return None
    try:
        return min(120.0, max(0.0, float(value.strip())))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return min(120.0, max(0.0, (target - current).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return None


def _should_relax_format(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(token in msg for token in _TRANSIENT_MESSAGE_TOKENS) or _status_code(exc) in _TRANSIENT_STATUS_CODES:
        return False
    return any(token in msg for token in ("response_format", "schema", "json mode", "bad request"))


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


def classify_retry(exc: Exception) -> str:
    """Classify an exception as ``transient`` or ``permanent``.

    Unknown programming/configuration errors are permanent by default. This
    prevents duplicate paid calls when the provider did not identify a
    transport or server-side failure.
    """

    if _is_context_error(exc):
        return "permanent"
    status = _status_code(exc)
    if status in _TRANSIENT_STATUS_CODES:
        return "transient"
    if status is not None and 400 <= status < 500:
        return "permanent"
    if status is not None and 500 <= status < 600:
        return "transient"

    chain = list(_exception_chain(exc))
    if any(isinstance(item, (TimeoutError, ConnectionError)) for item in chain):
        return "transient"
    names = " ".join(type(item).__name__.lower() for item in chain)
    if any(
        token in names
        for token in (
            "timeout",
            "connection",
            "ratelimit",
            "serviceunavailable",
            "internalserver",
            "overloaded",
        )
    ):
        return "transient"
    message = " ".join(str(item).lower() for item in chain)
    if any(token in message for token in _TRANSIENT_MESSAGE_TOKENS):
        return "transient"
    return "permanent"


def _attempt_count(max_retries: int) -> int:
    try:
        return max(1, int(max_retries))
    except Exception:
        return 1


def _record_attempt(provider: LLMProvider, event: Dict[str, Any]) -> None:
    recorder = getattr(provider, "record_attempt", None)
    if callable(recorder):
        recorder(event)


def _cancel_event(provider: LLMProvider) -> Optional[Any]:
    event = getattr(provider, "cancel_event", None)
    return event if event is not None and hasattr(event, "is_set") else None


def _raise_if_cancelled(provider: LLMProvider) -> None:
    event = _cancel_event(provider)
    if event is not None and event.is_set():
        raise PipelineCancelled("Analysis cancellation requested")


def call_with_retry(
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    response_format: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    timeout_sec: int = 60,
    rate_limiter: Optional[Any] = None,
    operation_name: str = "LLM request",
    *,
    sleep_fn: Any = time.sleep,
    jitter_fn: Any = random.uniform,
) -> str:
    err: Optional[Exception] = None
    force_responses = False
    compatibility_recovery_used = False
    attempts = _attempt_count(max_retries)
    performed = 0

    for attempt in range(attempts):
        _raise_if_cancelled(provider)
        performed = attempt + 1
        started = time.monotonic()
        try:
            if rate_limiter:
                rate_limiter.acquire()
            result = provider.generate_text(
                messages,
                response_format=response_format,
                timeout=timeout_sec,
                force_responses=force_responses,
            )
            _raise_if_cancelled(provider)
            _record_attempt(
                provider,
                {
                    "operation": operation_name,
                    "attempt": performed,
                    "max_attempts": attempts,
                    "outcome": "success",
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                },
            )
            return result
        except Exception as exc:
            if isinstance(exc, PipelineCancelled):
                raise
            err = exc
            classification = classify_retry(exc)
            status = _status_code(exc)
            compatibility_recovery = False
            if not compatibility_recovery_used and response_format is not None and _should_relax_format(exc):
                response_format = None
                compatibility_recovery = True
            if (
                not compatibility_recovery_used
                and hasattr(provider, "use_responses")
                and getattr(provider, "use_responses") is False
                and _should_relax_format(exc)
            ):
                force_responses = True
                compatibility_recovery = True
            compatibility_recovery_used = compatibility_recovery_used or compatibility_recovery

            retryable = compatibility_recovery or classification == "transient"
            has_next = attempt < attempts - 1
            delay = 0.0
            if retryable and has_next:
                retry_after = retry_after_seconds(exc)
                if retry_after is not None:
                    delay = retry_after
                else:
                    exponential = min(60.0, max(0.0, float(backoff_base) ** attempt))
                    delay = exponential * float(jitter_fn(0.8, 1.2))
            _record_attempt(
                provider,
                {
                    "operation": operation_name,
                    "attempt": performed,
                    "max_attempts": attempts,
                    "outcome": "retry" if retryable and has_next else "failed",
                    "classification": classification,
                    "status_code": status,
                    "error_type": type(exc).__name__,
                    "compatibility_recovery": compatibility_recovery,
                    "delay_seconds": round(delay, 3),
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                },
            )
            if _cancel_event(provider) is not None and _cancel_event(provider).is_set():
                raise PipelineCancelled("Analysis cancellation requested") from exc
            if not retryable or not has_next:
                break
            cancel_event = _cancel_event(provider)
            if cancel_event is not None and hasattr(cancel_event, "wait"):
                if cancel_event.wait(delay):
                    raise PipelineCancelled("Analysis cancellation requested") from exc
            else:
                sleep_fn(delay)

    error_type = type(err).__name__ if err is not None else "UnknownError"
    raise RuntimeError(
        f"{operation_name} failed after {performed} attempt(s) ({error_type})"
    ) from err
