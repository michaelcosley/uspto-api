from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import httpx
import pytest

from uspto_client import (
    UsptoAPIError,
    UsptoBadRequestError,
    UsptoClient,
    UsptoForbiddenError,
    UsptoNotFoundError,
    UsptoRateLimitError,
    UsptoServerError,
)
from uspto_client.rate_limit import PacingConfig, RetryConfig

FIXTURES = Path(__file__).parent / "fixtures"


def _json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_client_stores_config_without_network_call() -> None:
    client = UsptoClient(api_key="test-key", base_url="https://example.test")

    assert client.api_key == "test-key"
    assert client.base_url == "https://example.test"


def test_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        UsptoClient(api_key="")


def test_request_sends_api_key_and_uses_base_url_override() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers["X-API-KEY"]
        return httpx.Response(200, json={"count": 0})

    client = UsptoClient(
        api_key="secret",
        base_url="https://example.test/base",
        transport=httpx.MockTransport(handler),
    )

    client.request("GET", "/path", params={"q": "x"})

    assert seen == {
        "url": "https://example.test/base/path?q=x",
        "api_key": "secret",
    }


@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (400, UsptoBadRequestError),
        (403, UsptoForbiddenError),
        (404, UsptoNotFoundError),
        (429, UsptoRateLimitError),
        (500, UsptoServerError),
    ],
)
def test_error_responses_raise_typed_exceptions(
    status_code: int,
    exception_type: type[Exception],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "error": "Broken",
                "errorDetails": "Detailed failure",
                "requestIdentifier": "request-123",
            },
        )

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(exception_type) as exc_info:
        client.request("GET", "/broken")

    exc = exc_info.value
    assert isinstance(exc, UsptoAPIError)
    assert exc.status_code == status_code
    assert exc.message == "Detailed failure"
    assert exc.request_identifier == "request-123"


def test_429_retry_is_disabled_by_default() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": "Too Many Requests"})

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(UsptoRateLimitError):
        client.request("GET", "/limited")

    assert calls == 1


def test_configured_429_retry_waits_at_least_five_seconds() -> None:
    calls = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={})
        return httpx.Response(200, json={"count": 0})

    client = UsptoClient(
        api_key="test-key",
        base_url="https://retry-five.example.test",
        transport=httpx.MockTransport(handler),
        retry_config=RetryConfig(retry_on_429=True, max_attempts=2),
        pacing_config=PacingConfig(
            request_interval_seconds=0,
            download_interval_seconds=0,
        ),
        sleep=delays.append,
    )

    client.request("GET", "/limited")

    assert calls == 2
    assert delays == [5.0]


def test_429_retry_respects_longer_retry_after() -> None:
    calls = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "9"}, json={})
        return httpx.Response(200, json={"count": 0})

    client = UsptoClient(
        api_key="test-key",
        base_url="https://retry-nine.example.test",
        transport=httpx.MockTransport(handler),
        retry_config=RetryConfig(retry_on_429=True, max_attempts=2),
        pacing_config=PacingConfig(
            request_interval_seconds=0,
            download_interval_seconds=0,
        ),
        sleep=delays.append,
    )

    client.request("GET", "/limited")

    assert delays == [9.0]


def test_configured_5xx_retry_uses_exponential_backoff() -> None:
    calls = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"error": "Unavailable"})
        return httpx.Response(200, json={"count": 0})

    client = UsptoClient(
        api_key="retry-5xx-key",
        base_url="https://retry-5xx.example.test",
        transport=httpx.MockTransport(handler),
        retry_config=RetryConfig(
            retry_on_5xx=True,
            max_attempts=3,
            backoff_initial_seconds=0.25,
        ),
        pacing_config=PacingConfig(
            request_interval_seconds=0,
            download_interval_seconds=0,
        ),
        sleep=delays.append,
    )

    client.request("GET", "/unstable")

    assert calls == 3
    assert delays == [0.25, 0.5]


def test_configured_transport_retry_recovers_from_interrupted_read() -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadError("interrupted", request=request)
        return httpx.Response(200, content=b"%PDF")

    client = UsptoClient(
        api_key="retry-transport-key",
        base_url="https://retry-transport.example.test",
        transport=httpx.MockTransport(handler),
        retry_config=RetryConfig(
            retry_on_transport_error=True,
            max_attempts=2,
            backoff_initial_seconds=0.25,
        ),
        pacing_config=PacingConfig(
            request_interval_seconds=0,
            download_interval_seconds=0,
        ),
        sleep=delays.append,
    )

    download = client.download("/document.pdf")

    assert calls == 2
    assert download.content == b"%PDF"
    assert delays == [0.25]


def test_requests_with_same_api_key_are_serialized_across_clients() -> None:
    active_requests = 0
    max_active_requests = 0
    order: list[str] = []
    state_lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_requests, max_active_requests
        with state_lock:
            active_requests += 1
            max_active_requests = max(max_active_requests, active_requests)
            order.append(str(request.url.path))
        time.sleep(0.01)
        with state_lock:
            active_requests -= 1
        return httpx.Response(200, json={"count": 0})

    client_one = UsptoClient(
        api_key="shared-key",
        transport=httpx.MockTransport(handler),
    )
    client_two = UsptoClient(
        api_key="shared-key",
        transport=httpx.MockTransport(handler),
    )
    threads = [
        threading.Thread(target=client_one.request, args=("GET", "/one")),
        threading.Thread(target=client_two.request, args=("GET", "/two")),
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert max_active_requests == 1
    assert order == ["/one", "/two"]


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.now += delay


def test_default_pacing_waits_ten_milliseconds_between_api_calls() -> None:
    clock = _FakeClock()
    client = UsptoClient(
        api_key="paced-api-key",
        base_url="https://pacing-api.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"count": 0})
        ),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    client.request("GET", "/one")
    client.request("GET", "/two")

    assert clock.delays == [pytest.approx(0.010)]


def test_default_pacing_waits_fifty_milliseconds_between_downloads() -> None:
    clock = _FakeClock()
    client = UsptoClient(
        api_key="paced-download-key",
        base_url="https://pacing-download.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"pdf")
        ),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    client.download("/one.pdf")
    client.download("/two.pdf")

    assert clock.delays == [pytest.approx(0.050)]


def test_pacing_intervals_are_configurable() -> None:
    clock = _FakeClock()
    client = UsptoClient(
        api_key="custom-paced-key",
        base_url="https://custom-pacing.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"count": 0})
        ),
        pacing_config=PacingConfig(
            request_interval_seconds=0.125,
            download_interval_seconds=0.250,
        ),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    client.request("GET", "/one")
    client.request("GET", "/two")

    assert clock.delays == [pytest.approx(0.125)]


def test_pacing_config_rejects_negative_intervals() -> None:
    with pytest.raises(ValueError, match="request interval"):
        PacingConfig(request_interval_seconds=-0.001)
    with pytest.raises(ValueError, match="download interval"):
        PacingConfig(download_interval_seconds=-0.001)
