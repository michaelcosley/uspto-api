from __future__ import annotations

import json
from pathlib import Path

import httpx

from uspto_client import Pagination, SearchRequest, UsptoClient

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ptab_ipr2024_00001"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _client_that_records(
    seen: list[httpx.Request],
    response_json: dict[str, object],
) -> UsptoClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=response_json)

    return UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))


def test_search_proceedings_uses_get_query_params() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen, _fixture("proceeding.json"))

    response = client.ptab.trials.search_proceedings(
        q="trialMetaData.trialTypeCode:IPR",
        limit=5,
    )

    assert response.proceedings[0].trial_number == "IPR2024-00001"
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/v1/patent/trials/proceedings/search"
    assert seen[0].url.params["limit"] == "5"


def test_search_proceedings_uses_post_for_structured_body() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen, _fixture("proceeding.json"))

    client.ptab.trials.search_proceedings(
        body=SearchRequest(
            q="trialNumber:IPR2024-00001",
            pagination=Pagination(offset=0, limit=1),
        )
    )

    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {
        "q": "trialNumber:IPR2024-00001",
        "pagination": {"offset": 0, "limit": 1},
    }


def test_trial_number_lookup_uses_expected_path() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen, _fixture("proceeding.json"))

    client.ptab.trials.get_proceeding("IPR2024-00001")

    assert seen[0].url.path == ("/api/v1/patent/trials/proceedings/IPR2024-00001")


def test_document_methods_use_expected_paths() -> None:
    expected = {
        "search_documents": "/api/v1/patent/trials/documents/search",
        "get_documents": "/api/v1/patent/trials/IPR2024-00001/documents",
        "get_document": "/api/v1/patent/trials/documents/171359735",
    }

    for method_name, path in expected.items():
        seen: list[httpx.Request] = []
        client = _client_that_records(seen, _fixture("documents.json"))
        method = getattr(client.ptab.trials, method_name)
        argument = "171359735" if method_name == "get_document" else "IPR2024-00001"
        if method_name == "search_documents":
            method(q="trialNumber:IPR2024-00001")
        else:
            method(argument)
        assert seen[0].url.path == path


def test_decision_methods_use_expected_paths() -> None:
    expected = {
        "search_decisions": "/api/v1/patent/trials/decisions/search",
        "get_decisions": "/api/v1/patent/trials/IPR2024-00001/decisions",
        "get_decision": "/api/v1/patent/trials/decisions/171359747",
    }

    for method_name, path in expected.items():
        seen: list[httpx.Request] = []
        client = _client_that_records(seen, _fixture("decisions.json"))
        method = getattr(client.ptab.trials, method_name)
        argument = "171359747" if method_name == "get_decision" else "IPR2024-00001"
        if method_name == "search_decisions":
            method(q="trialNumber:IPR2024-00001")
        else:
            method(argument)
        assert seen[0].url.path == path


def test_search_export_uses_content_disposition_filename(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=b"trialNumber\nIPR2024-00001\n",
            headers={
                "Content-Type": "text/csv",
                "Content-Disposition": 'attachment; filename="results.csv"',
            },
        )

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    download = client.ptab.trials.download_proceedings_search_results(
        q="trialNumber:IPR2024-00001",
        format="csv",
        output_path=tmp_path,
    )

    assert seen[0].url.path == ("/api/v1/patent/trials/proceedings/search/download")
    assert seen[0].url.params["format"] == "csv"
    assert download.filename == "results.csv"
    assert (tmp_path / "results.csv").read_bytes() == download.content


def test_document_download_uses_record_uri_and_name(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=b"%PDF-test",
            headers={"Content-Type": "binary/octet-stream"},
        )

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))
    record = _fixture("documents.json")["patentTrialDocumentDataBag"][0]  # type: ignore[index]

    download = client.ptab.trials.download_document(record, output_path=tmp_path)

    assert seen[0].url.path.endswith("/171359735/petition.pdf")
    assert download.filename == "petition.pdf"
    assert download.content == b"%PDF-test"


def test_download_does_not_send_api_key_to_another_origin() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="secret-key", transport=httpx.MockTransport(handler))

    client.download("https://ptab.example.test/doc/123")

    assert "X-API-KEY" not in seen[0].headers


def test_download_strips_api_key_after_cross_origin_redirect() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "api.uspto.gov":
            return httpx.Response(
                302,
                headers={"Location": "https://files.example.test/document.pdf"},
            )
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="secret-key", transport=httpx.MockTransport(handler))

    client.download("/api/v1/patent/ptab-files/IPR/document.pdf")

    assert seen[0].headers["X-API-KEY"] == "secret-key"
    assert "X-API-KEY" not in seen[1].headers
