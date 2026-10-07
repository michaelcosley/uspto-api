"""Core USPTO client."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from email.message import Message
from pathlib import Path
from typing import Any, TypeVar, overload
from urllib.parse import unquote

import httpx
from pydantic import ValidationError

from uspto_client.applications import ApplicationsClient
from uspto_client.bulk import BulkClient
from uspto_client.errors import (
    UsptoAPIError,
    UsptoBadRequestError,
    UsptoForbiddenError,
    UsptoNotFoundError,
    UsptoRateLimitError,
    UsptoServerError,
)
from uspto_client.models import DocumentDownload, UsptoResponse
from uspto_client.ptab import PtabClient
from uspto_client.rate_limit import (
    DEFAULT_MONOTONIC,
    MonotonicCallable,
    PacingConfig,
    RetryConfig,
    SleepCallable,
    get_request_coordinator,
    retry_after_delay,
)
from uspto_client.streaming import StreamDownload, _stream_download

ResponseT = TypeVar("ResponseT", bound=UsptoResponse)


class UsptoClient:
    """Sync client for USPTO Open Data Portal patent APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.uspto.gov",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        retry_config: RetryConfig | None = None,
        pacing_config: PacingConfig | None = None,
        sleep: SleepCallable = time.sleep,
        monotonic: MonotonicCallable = DEFAULT_MONOTONIC,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.retry_config = retry_config or RetryConfig()
        self.pacing_config = pacing_config or PacingConfig()
        self._sleep = sleep
        self._monotonic = monotonic
        self._coordinator = get_request_coordinator(
            f"open-data-portal:{self.base_url}:{api_key}"
        )
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Accept": "application/json",
                "X-API-KEY": api_key,
            },
        )
        self.applications = ApplicationsClient(self)
        self.ptab = PtabClient(self)
        self.bulk = BulkClient(self)

    def stream_download(
        self,
        url: str,
        destination: Path,
        *,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
        max_bytes: int | None = None,
        resume: bool = True,
        progress: Callable[[int, int | None], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> StreamDownload:
        """Stream with this client's retry, pacing and credential policy.

        Library integrations can wrap this public method to coordinate the
        whole transfer, including retries, cancellation and validation.
        """
        return _stream_download(
            self,
            url,
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            max_bytes=max_bytes,
            resume=resume,
            progress=progress,
            cancelled=cancelled,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._http.close()

    def __enter__(self) -> UsptoClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    @overload
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> UsptoResponse: ...

    @overload
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        response_model: type[ResponseT],
    ) -> ResponseT: ...

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        response_model: type[UsptoResponse] = UsptoResponse,
    ) -> UsptoResponse:
        """Send a serialized request and parse the response."""

        attempts = 0
        while True:
            attempts += 1
            try:
                with self._coordinator.lock:
                    self._coordinator.wait(
                        self.pacing_config.request_interval_seconds,
                        sleep=self._sleep,
                        monotonic=self._monotonic,
                    )
                    response = self._http.request(
                        method,
                        path,
                        params=_clean_mapping(params),
                        json=_clean_mapping(json),
                    )
            except httpx.TransportError:
                if not self._should_retry_transport(attempts):
                    raise
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue

            if response.status_code == 429 and self._should_retry_429(attempts):
                delay = retry_after_delay(
                    response.headers.get("Retry-After"),
                    minimum_seconds=self.retry_config.min_429_delay_seconds,
                )
                response.close()
                self._sleep(delay)
                continue
            if response.status_code >= 500 and self._should_retry_5xx(attempts):
                response.close()
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue

            if response.is_error:
                raise _error_from_response(response)

            data = _json_body(response)
            try:
                return response_model.model_validate(data)
            except ValidationError as exc:
                raise UsptoAPIError(
                    "USPTO response did not match the expected model",
                    status_code=response.status_code,
                    response_body=data,
                ) from exc

    def _should_retry_429(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_429 and attempts < self.retry_config.max_attempts
        )

    def _should_retry_5xx(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_5xx and attempts < self.retry_config.max_attempts
        )

    def _should_retry_transport(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_transport_error
            and attempts < self.retry_config.max_attempts
        )

    def download(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download binary content, optionally writing it to disk."""

        attempts = 0
        while True:
            attempts += 1
            try:
                with self._coordinator.lock:
                    self._coordinator.wait(
                        self.pacing_config.download_interval_seconds,
                        sleep=self._sleep,
                        monotonic=self._monotonic,
                    )
                    response = self._send_download_request(path, params=params)
            except httpx.TransportError:
                if not self._should_retry_transport(attempts):
                    raise
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue

            if response.status_code == 429 and self._should_retry_429(attempts):
                delay = retry_after_delay(
                    response.headers.get("Retry-After"),
                    minimum_seconds=self.retry_config.min_429_delay_seconds,
                )
                response.close()
                self._sleep(delay)
                continue
            if response.status_code >= 500 and self._should_retry_5xx(attempts):
                response.close()
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue

            if response.is_error:
                raise _error_from_response(response)

            resolved_filename = _safe_filename(
                filename
                or _filename_from_content_disposition(
                    response.headers.get("Content-Disposition")
                )
                or _filename_from_path(str(response.url))
            )
            written_path = _write_download(
                response.content,
                output_path=output_path,
                filename=resolved_filename,
                avoid_filename_conflicts=avoid_filename_conflicts,
            )
            return DocumentDownload(
                content=response.content,
                filename=resolved_filename,
                path=str(written_path) if written_path is not None else None,
                content_type=response.headers.get("Content-Type"),
                status_code=response.status_code,
            )

    def _send_download_request(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None,
        max_redirects: int = 20,
    ) -> httpx.Response:
        """GET binary content while limiting API-key headers to the API origin."""

        url = httpx.URL(path)
        if url.is_relative_url:
            url = self._http.base_url.join(url)
        cleaned_params = _clean_mapping(params)
        for redirect_number in range(max_redirects + 1):
            request = self._http.build_request(
                "GET",
                url,
                params=cleaned_params if redirect_number == 0 else None,
            )
            if not _same_origin(request.url, self._http.base_url):
                request.headers.pop("X-API-KEY", None)
            response = self._http.send(request, follow_redirects=False)
            if not response.has_redirect_location:
                return response
            if redirect_number == max_redirects:
                response.close()
                raise httpx.TooManyRedirects(
                    "Exceeded maximum allowed redirects",
                    request=request,
                )
            location = response.headers["Location"]
            next_url = response.url.join(location)
            response.close()
            url = next_url
        raise AssertionError("redirect loop terminated unexpectedly")


def _clean_mapping(mapping: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if mapping is None:
        return None
    cleaned = {key: value for key, value in mapping.items() if value is not None}
    return cleaned or None


def _json_body(response: httpx.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def _error_from_response(response: httpx.Response) -> UsptoAPIError:
    body = _json_body(response)
    message = _message_from_body(body) or response.reason_phrase
    request_identifier = (
        body.get("requestIdentifier") if isinstance(body, dict) else None
    )
    kwargs = {
        "status_code": response.status_code,
        "response_body": body,
        "request_identifier": request_identifier,
    }
    if response.status_code == 400:
        return UsptoBadRequestError(message, **kwargs)
    if response.status_code in {401, 403}:
        return UsptoForbiddenError(message, **kwargs)
    if response.status_code == 404:
        return UsptoNotFoundError(message, **kwargs)
    if response.status_code == 429:
        return UsptoRateLimitError(message, **kwargs)
    if response.status_code >= 500:
        return UsptoServerError(message, **kwargs)
    return UsptoAPIError(message, **kwargs)


def _message_from_body(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("errorDetails", "error", "message", "detail"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _filename_from_path(path: str) -> str:
    filename = unquote(httpx.URL(path).path.rstrip("/").rsplit("/", maxsplit=1)[-1])
    return filename or "document.pdf"


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    message = Message()
    message["Content-Disposition"] = value
    return message.get_filename()


def _safe_filename(value: str) -> str:
    filename = Path(value.replace("\\", "/")).name
    return filename or "document.pdf"


def _same_origin(left: httpx.URL, right: httpx.URL) -> bool:
    return (
        left.scheme.casefold(),
        left.host.casefold(),
        left.port,
    ) == (
        right.scheme.casefold(),
        right.host.casefold(),
        right.port,
    )


def _write_download(
    content: bytes,
    *,
    output_path: str | Path | None,
    filename: str,
    avoid_filename_conflicts: bool,
) -> Path | None:
    if output_path is None:
        return None

    destination = Path(output_path)
    if destination.exists() and destination.is_dir():
        destination = destination / filename
    elif str(output_path).endswith(("/", "\\")):
        destination.mkdir(parents=True, exist_ok=True)
        destination = destination / filename
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)

    if avoid_filename_conflicts:
        from uspto_client.filenames import unique_path

        destination = unique_path(destination)

    destination.write_bytes(content)
    return destination
