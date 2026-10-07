"""Bounded-memory, resumable downloads using the client's transport and pacing."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import httpx

if TYPE_CHECKING:
    from uspto_client.client import UsptoClient


@dataclass(frozen=True)
class StreamDownload:
    path: Path
    bytes_written: int
    sha256: str
    resumed: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StreamingClient(Protocol):
    """Public transport boundary for Library and bulk downloads.

    A facade may implement this method to apply process coordination without
    exposing the client's HTTP transport, credentials or retry internals.
    """

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
    ) -> StreamDownload: ...


def stream_download(
    client: StreamingClient,
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
    """Download through the supplied client's public streaming boundary."""
    return client.stream_download(
        url,
        destination,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
        max_bytes=max_bytes,
        resume=resume,
        progress=progress,
        cancelled=cancelled,
    )


def _stream_download(
    client: UsptoClient,
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
    from uspto_client.client import _error_from_response, _same_origin
    from uspto_client.rate_limit import retry_after_delay

    if max_bytes is not None and (
        max_bytes < 0 or (expected_size is not None and expected_size > max_bytes)
    ):
        raise ValueError("Download exceeds byte budget")
    destination = destination.resolve()
    if destination.exists():
        digest = file_sha256(destination)
        if (
            expected_sha256
            and digest == expected_sha256
            and (expected_size is None or destination.stat().st_size == expected_size)
        ):
            return StreamDownload(
                destination, destination.stat().st_size, digest, False
            )
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    state = destination.with_name(destination.name + ".part.json")
    lock = destination.with_name(destination.name + ".download.lock")
    # Never persist a signed URL or an API key; identify the request by hash.
    request_id = hashlib.sha256(url.encode()).hexdigest()
    with lock.open("x") as lock_handle:
        lock_handle.write(str(os.getpid()))
    try:
        for attempt in range(1, client.retry_config.max_attempts + 1):
            saved = json.loads(state.read_text()) if resume and state.exists() else {}
            if saved.get("request_id") != request_id:
                saved = {}
            validator = saved.get("etag") or saved.get("last_modified")
            offset = partial.stat().st_size if partial.exists() and validator else 0
            response: httpx.Response | None = None
            total: int | None = None
            try:
                with client._coordinator.lock:
                    client._coordinator.wait(
                        client.pacing_config.download_interval_seconds,
                        sleep=client._sleep,
                        monotonic=client._monotonic,
                    )
                    target = client._http.base_url.join(url)
                    for _ in range(21):
                        headers = {"Accept-Encoding": "identity"}
                        if offset:
                            headers.update(
                                {
                                    "Range": f"bytes={offset}-",
                                    "If-Range": str(validator),
                                }
                            )
                        request = client._http.build_request(
                            "GET", target, headers=headers
                        )
                        if not _same_origin(request.url, client._http.base_url):
                            request.headers.pop("X-API-KEY", None)
                        response = client._http.send(
                            request, stream=True, follow_redirects=False
                        )
                        if not response.has_redirect_location:
                            break
                        target = response.url.join(response.headers["Location"])
                        response.close()
                        if target.scheme != "https":
                            raise ValueError("Refusing non-HTTPS download redirect")
                    else:
                        raise ValueError("Too many download redirects")
                    if response.status_code == 429 and client._should_retry_429(
                        attempt
                    ):
                        client._sleep(
                            retry_after_delay(
                                response.headers.get("Retry-After"),
                                minimum_seconds=client.retry_config.min_429_delay_seconds,
                            )
                        )
                        continue
                    if response.status_code >= 500 and client._should_retry_5xx(
                        attempt
                    ):
                        client._sleep(client.retry_config.backoff_delay(attempt))
                        continue
                    if response.is_error:
                        response.read()
                        raise _error_from_response(response)
                    if response.status_code not in (200, 206):
                        raise ValueError(
                            f"Unexpected download status {response.status_code}"
                        )
                    if (
                        response.headers.get("Content-Encoding", "identity")
                        != "identity"
                    ):
                        raise ValueError("Encoded response cannot be safely resumed")
                    if response.status_code == 206:
                        match = re.fullmatch(
                            r"bytes (\d+)-(\d+)/(\d+)",
                            response.headers.get("Content-Range", ""),
                        )
                        if not match or int(match[1]) != offset:
                            raise ValueError("Invalid Content-Range")
                        total = int(match[3])
                        if (
                            saved.get("etag")
                            and response.headers.get("ETag") != saved["etag"]
                        ):
                            raise ValueError("Download validator changed")
                    else:
                        offset = (
                            0  # A server without ranges safely restarts the transfer.
                        )
                        total = (
                            int(response.headers["Content-Length"])
                            if "Content-Length" in response.headers
                            else expected_size
                        )
                    if (
                        max_bytes is not None
                        and total is not None
                        and total > max_bytes
                    ):
                        raise ValueError("Download exceeds byte budget")
                    etag = response.headers.get("ETag", "")
                    if etag.startswith("W/"):
                        etag = ""
                    state.write_text(
                        json.dumps(
                            {
                                "request_id": request_id,
                                "etag": etag,
                                "last_modified": response.headers.get(
                                    "Last-Modified", ""
                                ),
                            }
                        ),
                        encoding="utf-8",
                    )
                    written = offset
                    with partial.open("ab" if offset else "wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if cancelled and cancelled():
                                raise InterruptedError("Download cancelled")
                            written += len(chunk)
                            if max_bytes is not None and written > max_bytes:
                                raise ValueError("Download exceeds byte budget")
                            handle.write(chunk)
                            if progress:
                                progress(written, total)
                        handle.flush()
                        os.fsync(handle.fileno())
                    if (expected_size is not None and written != expected_size) or (
                        total is not None and written != total
                    ):
                        raise ValueError("Download size mismatch")
                    digest = file_sha256(partial)
                    if expected_sha256 and digest.lower() != expected_sha256.lower():
                        raise ValueError("Download checksum mismatch")
                    os.replace(partial, destination)
                    state.unlink(missing_ok=True)
                    return StreamDownload(destination, written, digest, bool(offset))
            except httpx.TransportError:
                if not client._should_retry_transport(attempt):
                    raise
                client._sleep(client.retry_config.backoff_delay(attempt))
            finally:
                if response is not None:
                    response.close()
        raise RuntimeError("Download attempts exhausted")
    finally:
        lock.unlink(missing_ok=True)
