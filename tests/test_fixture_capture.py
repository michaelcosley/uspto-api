from __future__ import annotations

from uspto_client.fixture_capture import REDACTED, sanitize_capture


def test_fixture_capture_sanitizes_sensitive_headers_and_secret_values() -> None:
    capture = {
        "request": {
            "headers": {
                "X-API-KEY": "secret-key",
                "Accept": "application/json",
            },
            "url": "https://api.uspto.gov/path?token=secret-key",
        },
        "response": {"value": "safe"},
    }

    sanitized = sanitize_capture(capture, secret_values=["secret-key"])

    assert sanitized["request"]["headers"]["X-API-KEY"] == REDACTED
    assert sanitized["request"]["headers"]["Accept"] == "application/json"
    assert sanitized["request"]["url"] == (
        f"https://api.uspto.gov/path?token={REDACTED}"
    )
