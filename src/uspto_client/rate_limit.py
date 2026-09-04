"""Request sequencing and retry configuration."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryConfig:
    """Retry options for conservative USPTO rate-limit handling."""

    retry_on_429: bool = False
    retry_on_5xx: bool = False
    retry_on_transport_error: bool = False
    max_attempts: int = 1
    min_429_delay_seconds: float = 5.0
    backoff_initial_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    backoff_max_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.retry_on_429 and self.min_429_delay_seconds < 5.0:
            raise ValueError("429 retry delay must be at least 5 seconds")
        if self.backoff_initial_seconds < 0:
            raise ValueError("initial backoff cannot be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff multiplier must be at least 1")
        if self.backoff_max_seconds < self.backoff_initial_seconds:
            raise ValueError("maximum backoff cannot be less than initial backoff")

    def backoff_delay(self, failed_attempt: int) -> float:
        """Return bounded exponential backoff after a failed attempt."""

        return min(
            self.backoff_initial_seconds
            * (self.backoff_multiplier ** max(0, failed_attempt - 1)),
            self.backoff_max_seconds,
        )


@dataclass(frozen=True)
class PacingConfig:
    """Minimum spacing between requests made by one process."""

    request_interval_seconds: float = 0.010
    download_interval_seconds: float = 0.050

    def __post_init__(self) -> None:
        if self.request_interval_seconds < 0:
            raise ValueError("request interval cannot be negative")
        if self.download_interval_seconds < 0:
            raise ValueError("download interval cannot be negative")


class RequestCoordinator:
    """Serialize and pace calls that share an API key or public service."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._last_request_started: float | None = None

    def wait(
        self,
        minimum_interval_seconds: float,
        *,
        sleep: SleepCallable,
        monotonic: MonotonicCallable,
    ) -> None:
        """Wait until the next permitted start time and reserve that time."""

        now = monotonic()
        if self._last_request_started is None:
            scheduled = now
        else:
            scheduled = max(
                now,
                self._last_request_started + minimum_interval_seconds,
            )
        delay = scheduled - now
        if delay > 0:
            sleep(delay)
        self._last_request_started = scheduled


_COORDINATORS: dict[str, RequestCoordinator] = {}
_LOCKS_GUARD = threading.Lock()


def get_request_coordinator(scope: str) -> RequestCoordinator:
    """Return the process-local request coordinator for a service scope."""

    with _LOCKS_GUARD:
        coordinator = _COORDINATORS.get(scope)
        if coordinator is None:
            coordinator = RequestCoordinator()
            _COORDINATORS[scope] = coordinator
        return coordinator


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
MonotonicCallable = Callable[[], float]
DEFAULT_MONOTONIC: MonotonicCallable = time.monotonic
