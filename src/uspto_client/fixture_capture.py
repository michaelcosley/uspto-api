"""Helpers for safely storing live USPTO API fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
}
REDACTED = "<redacted>"


def sanitize_capture(
    capture: Mapping[str, Any],
    *,
    secret_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a copy of captured metadata with secrets removed."""

    secrets = {secret for secret in secret_values if secret}
    return cast(dict[str, Any], _sanitize_value(capture, secrets, key_hint=None))


def _sanitize_value(
    value: Any,
    secrets: set[str],
    *,
    key_hint: str | None,
) -> Any:
    if key_hint and key_hint.lower() in SENSITIVE_HEADER_NAMES:
        return REDACTED
    if isinstance(value, str):
        sanitized = value
        for secret in secrets:
            sanitized = sanitized.replace(secret, REDACTED)
        return sanitized
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_value(item, secrets, key_hint=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, secrets, key_hint=None) for item in value]
    return value
