"""Request sequencing and retry configuration."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryConfig:
    """Retry options for conservative USPTO rate-limit handling."""

    retry_on_429: bool = False
    max_attempts: int = 1
    min_429_delay_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.retry_on_429 and self.min_429_delay_seconds < 5.0:
            raise ValueError("429 retry delay must be at least 5 seconds")


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def get_api_key_lock(api_key: str) -> threading.Lock:
    """Return the process-local serialization lock for an API key."""

    with _LOCKS_GUARD:
        lock = _LOCKS.get(api_key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[api_key] = lock
        return lock


def retry_after_delay(
    retry_after: str | None,
    *,
    minimum_seconds: float,
) -> float:
    """Resolve a retry delay from a Retry-After header and configured minimum."""

    if retry_after is None:
        return minimum_seconds
    try:
        return max(float(retry_after), minimum_seconds)
    except ValueError:
        return minimum_seconds


SleepCallable = Callable[[float], None]
