from __future__ import annotations

import json
from pathlib import Path

import httpx

from uspto_client import UsptoClient
from uspto_client.models import (
    Pagination,
    RangeFilter,
    SearchFilter,
    SearchRequest,
    SearchSort,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _json_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _client_that_records(
    seen: list[httpx.Request],
    response_json: dict[str, object] | None = None,
) -> UsptoClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=response_json or _json_fixture("patent_application_response.json"),
        )

    return UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))


def test_search_uses_get_query_params_and_parses_response() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen)

    response = client.applications.search(
        q="applicationMetaData.applicationTypeLabelName:Utility",
        limit=5,
        range_filters="filingDate:[2024-01-01 TO *]",
    )

    assert response.count == 1
    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/v1/patent/applications/search"
    assert seen[0].url.params["limit"] == "5"
    assert seen[0].url.params["rangeFilters"] == "filingDate:[2024-01-01 TO *]"


def test_search_uses_post_when_body_is_provided() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen)

    client.applications.search(body=SearchRequest(q="Utility", limit=1))

    assert seen[0].method == "POST"
    assert seen[0].url.path == "/api/v1/patent/applications/search"
    assert json.loads(seen[0].content) == {"q": "Utility", "limit": 1}


def test_search_posts_structured_filter_payload() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen)

    client.applications.search(
        body=SearchRequest(
            q="9198117",
            filters=[
                SearchFilter(
                    name="applicationMetaData.applicationTypeLabelName",
                    value=["Re-Examination"],
                )
            ],
            range_filters=[
                RangeFilter(
                    field="applicationMetaData.grantDate",
                    value_from="2010-08-04",
                    value_to="2022-08-04",
                )
            ],
            pagination=Pagination(offset=0, limit=25),
            sort=[SearchSort(field="applicationMetaData.filingDate", order="Desc")],
        )
    )

    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {
        "q": "9198117",
        "filters": [
            {
                "name": "applicationMetaData.applicationTypeLabelName",
                "value": ["Re-Examination"],
            }
        ],
        "rangeFilters": [
            {
                "field": "applicationMetaData.grantDate",
                "valueFrom": "2010-08-04",
                "valueTo": "2022-08-04",
            }
        ],
        "pagination": {"offset": 0, "limit": 25},
        "sort": [{"field": "applicationMetaData.filingDate", "order": "Desc"}],
    }


def test_download_search_results_uses_expected_path() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen)

    client.applications.download_search_results(q="Utility", format="json")

    assert seen[0].method == "GET"
    assert seen[0].url.path == "/api/v1/patent/applications/search/download"
    assert seen[0].url.params["format"] == "json"


def test_single_application_methods_use_expected_paths() -> None:
    methods = {
        "get": "/api/v1/patent/applications/16330077",
        "get_metadata": "/api/v1/patent/applications/16330077/meta-data",
        "get_adjustment": "/api/v1/patent/applications/16330077/adjustment",
        "get_assignment": "/api/v1/patent/applications/16330077/assignment",
        "get_attorney": "/api/v1/patent/applications/16330077/attorney",
        "get_continuity": "/api/v1/patent/applications/16330077/continuity",
        "get_foreign_priority": (
            "/api/v1/patent/applications/16330077/foreign-priority"
        ),
        "get_transactions": "/api/v1/patent/applications/16330077/transactions",
        "get_associated_documents": (
            "/api/v1/patent/applications/16330077/associated-documents"
        ),
    }

    for method_name, expected_path in methods.items():
        seen: list[httpx.Request] = []
        client = _client_that_records(seen)

        getattr(client.applications, method_name)("16330077")

        assert seen[0].method == "GET"
        assert seen[0].url.path == expected_path


def test_get_documents_sends_document_filters() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(seen)

    client.applications.get_documents(
        "16330077",
        document_codes="CLM",
        official_date_from="2024-01-01",
        official_date_to="2024-12-31",
    )

    assert seen[0].url.path == "/api/v1/patent/applications/16330077/documents"
    assert seen[0].url.params["documentCodes"] == "CLM"
    assert seen[0].url.params["officialDateFrom"] == "2024-01-01"
    assert seen[0].url.params["officialDateTo"] == "2024-12-31"


def test_download_document_returns_bytes_without_writing_file() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=b"%PDF-test",
            headers={"Content-Type": "application/pdf"},
        )

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    response = client.applications.download_document(
        "90016176",
        "MO1EEHMN101X233",
    )

    assert seen[0].url.path == (
        "/api/v1/download/applications/90016176/MO1EEHMN101X233.pdf"
    )
    assert response.content == b"%PDF-test"
    assert response.filename == "MO1EEHMN101X233.pdf"
    assert response.path is None
    assert response.content_type == "application/pdf"


def test_download_document_follows_redirects() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.startswith("/api/v1/download/"):
            return httpx.Response(
                302,
                headers={"Location": "https://example.test/signed/document.pdf"},
            )
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    response = client.applications.download_document(
        "90016176",
        "MO1EEHMN101X233",
    )

    assert seen == [
        "https://api.uspto.gov/api/v1/download/applications/90016176/MO1EEHMN101X233.pdf",
        "https://example.test/signed/document.pdf",
    ]
    assert response.status_code == 200
    assert response.content == b"%PDF-test"


def test_download_document_writes_to_specific_file(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))
    destination = tmp_path / "custom.pdf"

    response = client.applications.download_document(
        "90016176",
        "MO1EEHMN101X233",
        output_path=destination,
    )

    assert destination.read_bytes() == b"%PDF-test"
    assert response.path == str(destination)
    assert response.filename == "MO1EEHMN101X233.pdf"


def test_download_document_writes_to_directory_with_custom_filename(
    tmp_path: Path,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    response = client.applications.download_document(
        "90016176",
        "MO1EEHMN101X233",
        output_path=tmp_path,
        filename="bib-sheet.pdf",
    )

    expected_path = tmp_path / "bib-sheet.pdf"
    assert expected_path.read_bytes() == b"%PDF-test"
    assert response.path == str(expected_path)
    assert response.filename == "bib-sheet.pdf"


def test_download_document_can_generate_filename_from_document_metadata(
    tmp_path: Path,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-test")

    document = {
        "applicationNumberText": "90015959",
        "officialDate": "2026-05-04T14:32:01.000-0400",
        "documentIdentifier": "ABC123",
        "documentCode": "RXOSUB.R.40",
        "documentCodeDescriptionText": "Receipt Original Ex Parte Reexamination",
    }
    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))

    response = client.applications.download_document(
        "90015959",
        "ABC123",
        output_path=tmp_path,
        document=document,
        filename_format="application_date_patent_description",
        filename_template="{app_no} {date} {patent_last_three} {short_desc}",
        patent_number="11,111,279",
    )

    expected_path = (
        tmp_path
        / "90015959 2026-05-04 ('279) Receipt Original Ex Parte Reexamination.pdf"
    )
    assert expected_path.read_bytes() == b"%PDF-test"
    assert response.path == str(expected_path)


def test_download_document_avoids_filename_conflicts(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF-test")

    client = UsptoClient(api_key="test-key", transport=httpx.MockTransport(handler))
    existing = tmp_path / "ABC123.pdf"
    existing.write_bytes(b"existing")

    response = client.applications.download_document(
        "90015959",
        "ABC123",
        output_path=tmp_path,
    )

    expected_path = tmp_path / "ABC123 (2).pdf"
    assert expected_path.read_bytes() == b"%PDF-test"
    assert response.path == str(expected_path)


def test_search_status_codes_parses_status_response() -> None:
    seen: list[httpx.Request] = []
    client = _client_that_records(
        seen,
        response_json=_json_fixture("status_code_response.json"),
    )

    response = client.applications.search_status_codes(q="150")

    assert response.count == 1
    assert response.status_code_data_bag[0]["applicationStatusCode"] == 150
    assert seen[0].url.path == "/api/v1/patent/status-codes"
