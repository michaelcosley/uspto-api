from pathlib import Path

import httpx
import pytest

from uspto_client import RetryConfig, UsptoClient


def test_catalog_and_streamed_download(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("search"):
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "bulkDataProductBag": [
                        {
                            "productIdentifier": "PTFWPRD",
                            "productFileBag": {
                                "count": 1,
                                "fileDataBag": [{"fileName": "day.zip", "fileSize": 3}],
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, content=b"abc", headers={"Content-Length": "3"})

    with UsptoClient(api_key="test", transport=httpx.MockTransport(handle)) as client:
        assert client.bulk.search().products[0].product_identifier == "PTFWPRD"
        result = client.bulk.download_file(
            "PTFWPRD", "day.zip", output_path=tmp_path / "day.zip", expected_size=3
        )
        assert result.bytes_written == 3
        assert (tmp_path / "day.zip").read_bytes() == b"abc"


def test_download_budget_and_redirect_credentials(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.uspto.gov":
            return httpx.Response(
                302, headers={"Location": "https://files.example.test/file"}
            )
        assert "X-API-KEY" not in request.headers
        return httpx.Response(200, content=b"abcdef")

    with (
        UsptoClient(api_key="test", transport=httpx.MockTransport(handle)) as client,
        pytest.raises(ValueError, match="budget"),
    ):
        client.bulk.download_file(
            "PTFWPRD", "day.zip", output_path=tmp_path / "day.zip", max_bytes=3
        )
    assert not (tmp_path / "day.zip").exists()


def test_interrupted_download_resumes_with_etag(tmp_path: Path) -> None:
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * (1024 * 1024)
            raise httpx.ReadError("interrupted")

    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                200,
                stream=Broken(),
                headers={"ETag": '"one"', "Content-Length": "1048579"},
            )
        assert request.headers["Range"] == "bytes=1048576-"
        assert request.headers["If-Range"] == '"one"'
        return httpx.Response(
            206,
            content=b"end",
            headers={"ETag": '"one"', "Content-Range": "bytes 1048576-1048578/1048579"},
        )

    with UsptoClient(
        api_key="test",
        transport=httpx.MockTransport(handle),
        retry_config=RetryConfig(retry_on_transport_error=True, max_attempts=2),
        sleep=lambda _: None,
    ) as client:
        result = client.bulk.download_file(
            "PTFWPRD", "day.zip", output_path=tmp_path / "day.zip"
        )
        assert result.resumed and result.bytes_written == 1048579
