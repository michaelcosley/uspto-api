from __future__ import annotations

import os

import pytest

from uspto_client import UsptoClient


@pytest.mark.live
def test_live_client_can_be_constructed_with_real_key() -> None:
    client = UsptoClient(api_key=os.environ["USPTO_API_KEY"])

    assert client.api_key
