"""Typed exceptions raised by the USPTO client."""

from __future__ import annotations

from typing import Any


class UsptoAPIError(Exception):
    """Base exception for USPTO API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: Any | None = None,
        request_identifier: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.request_identifier = request_identifier


class UsptoBadRequestError(UsptoAPIError):
    """Raised for HTTP 400 responses."""


class UsptoForbiddenError(UsptoAPIError):
    """Raised for HTTP 401/403 responses."""


class UsptoNotFoundError(UsptoAPIError):
    """Raised for HTTP 404 responses."""


class UsptoRateLimitError(UsptoAPIError):
    """Raised for HTTP 429 responses."""


class UsptoServerError(UsptoAPIError):
    """Raised for HTTP 5xx responses."""
