from pathlib import Path

from uspto_client.streaming import StreamDownload, stream_download


def test_streaming_accepts_a_public_facade_without_private_client_attributes(
    tmp_path: Path,
) -> None:
    calls = []

    class Facade:
        def stream_download(self, url, destination, **kwargs):
            calls.append((url, destination, kwargs))
            return StreamDownload(destination, 3, "test", False)

    result = stream_download(Facade(), "/file", tmp_path / "file", max_bytes=10)
    assert result.bytes_written == 3
    assert calls[0][2]["max_bytes"] == 10
