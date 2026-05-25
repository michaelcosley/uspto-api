from __future__ import annotations

import os
import socket

import pytest

from uspto_client import UsptoClient


def test_normal_tests_block_external_sockets() -> None:
    with pytest.raises(RuntimeError, match="External network access is disabled"):
        socket.create_connection(("api.uspto.gov", 443), timeout=1)


def test_mocked_client_does_not_require_environment_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("USPTO_API_KEY", raising=False)

    client = UsptoClient(api_key="test-key")

    assert "USPTO_API_KEY" not in os.environ
    assert client.api_key == "test-key"


def test_import_does_not_load_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USPTO_API_KEY", raising=False)

    __import__("uspto_client")

    assert "USPTO_API_KEY" not in os.environ
