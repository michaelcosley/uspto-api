from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest

_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SOCKET = socket.socket


class NetworkBlockedError(RuntimeError):
    """Raised when a non-live test tries to open a network connection."""


class GuardedSocket(_ORIGINAL_SOCKET):
    def connect(self, address: Any) -> None:  # type: ignore[override]
        raise NetworkBlockedError(
            "External network access is disabled for normal tests. "
            "Use --live-uspto with tests marked live for real API calls."
        )


def _blocked_create_connection(*_args: Any, **_kwargs: Any) -> socket.socket:
    raise NetworkBlockedError(
        "External network access is disabled for normal tests. "
        "Use --live-uspto with tests marked live for real API calls."
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-uspto",
        action="store_true",
        default=False,
        help="Run tests that intentionally call the real USPTO API.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: tests that intentionally call the real USPTO API",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    live_enabled = config.getoption("--live-uspto")
    if live_enabled and not os.environ.get("USPTO_API_KEY"):
        pytest.exit("--live-uspto requires USPTO_API_KEY to be set", returncode=2)
    if live_enabled:
        return

    skip_live = pytest.mark.skip(reason="requires --live-uspto")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def block_network_by_default(request: pytest.FixtureRequest) -> Iterator[None]:
    live_enabled = request.config.getoption("--live-uspto")
    is_live_test = "live" in request.node.keywords
    if live_enabled and is_live_test:
        yield
        return

    socket.create_connection = _blocked_create_connection
    socket.socket = GuardedSocket
    try:
        yield
    finally:
        socket.create_connection = _ORIGINAL_CREATE_CONNECTION
        socket.socket = _ORIGINAL_SOCKET
