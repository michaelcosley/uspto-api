from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from uspto_client import (
    EXACT_ASSIGNEE_NAME_SEARCH,
    AssignmentCenterClient,
    AssignmentSearchCriterion,
    UsptoAPIError,
    UsptoNotFoundError,
)


def _success_response() -> dict[str, object]:
    return {
        "status": "Success",
        "statusCode": 200,
        "error": None,
        "successResponse": {
            "data": [
                {
                    "assignment": [
                        {
                            "assignees": [
                                {
                                    "assigneeName": "GRAND VALLEY STATE UNIVERSITY",
                                    "assigneeSequenceNumber": 1,
                                }
                            ],
                            "assignors": [
                                {
                                    "assignorName": "TAYLOR, MERRITT",
                                    "assignorSequenceNumber": 1,
                                    "executionDate": "06/15/2017",
                                }
                            ],
                            "assignmentSequence": 1,
                            "conveyance": "ASSIGNMENT OF ASSIGNOR'S INTEREST",
                            "conveyanceCode": 23,
                            "recordationDate": "07/18/2018",
                            "reelNumber": 46387,
                            "frameNumber": 180,
                            "unexpectedFutureField": "preserved",
                        }
                    ],
                    "properties": [
                        {
                            "applicationNumber": "15776580",
                            "fillingDate": "05/16/2018",
                            "patentNumber": "11111279",
                            "publicationNumber": "US20180346530A1",
                        }
                    ],
                    "noOfAssignments": 1,
                }
            ],
            "totalRows": 1,
            "backendPagination": False,
            "filteredRowsCount": 0,
            "message": None,
        },
    }


def test_exact_assignee_search_sends_public_contract_and_parses_models() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["api_key"] = request.headers.get("X-API-KEY")
        return httpx.Response(200, json=_success_response())

    client = AssignmentCenterClient(
        base_url="https://assignment.example.test",
        transport=httpx.MockTransport(handler),
    )

    response = client.search_exact_assignee("GRAND VALLEY STATE UNIVERSITY")

    assert seen == {
        "url": (
            "https://assignment.example.test/ipas/search/api/v3/public/" "search/patent"
        ),
        "body": {
            "property": "GRAND VALLEY STATE UNIVERSITY",
            "searchBy": EXACT_ASSIGNEE_NAME_SEARCH,
            "dataFilter": {
                "filterBy": "all",
                "rowsPerPage": 100,
                "currentPage": 1,
            },
        },
        "api_key": None,
    }
    assert response.total_rows == 1
    result = response.results[0]
    assert result.properties[0].patent_number == "11111279"
    assert result.assignment_records[0].assignees[0].assignee_name == (
        "GRAND VALLEY STATE UNIVERSITY"
    )
    assert result.assignment_records[0].model_extra == {
        "unexpectedFutureField": "preserved"
    }


def test_advanced_search_and_reel_frame_use_expected_payloads() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=_success_response())

    client = AssignmentCenterClient(
        base_url="https://assignment-search.example.test",
        transport=httpx.MockTransport(handler),
    )
    criterion = AssignmentSearchCriterion(
        property="Example Corp.",
        search_by="exactAssigneeName",
        match_type="exact",
        order=1,
        relation="AND",
    )

    client.advanced_search([criterion])
    client.get_reel_frame("046387", "0180")

    assert bodies[0]["searchCriteria"] == [
        {
            "property": "Example Corp.",
            "searchBy": "exactAssigneeName",
            "matchType": "exact",
            "order": 1,
            "relation": "AND",
        }
    ]
    assert bodies[1] == {
        "reelNumber": "046387",
        "frameNumber": "0180",
        "searchBy": "reelFrame",
        "dataFilter": {
            "filterBy": "all",
            "rowsPerPage": 100,
            "currentPage": 1,
        },
    }


def test_assignment_center_normalizes_null_empty_results() -> None:
    client = AssignmentCenterClient(
        base_url="https://assignment-empty.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "status": "Success",
                    "statusCode": 200,
                    "successResponse": {"data": None, "totalRows": 0},
                },
            )
        ),
    )

    response = client.search_patents("00000000", search_by="patentNumber")

    assert response.total_rows == 0
    assert response.results == []


def test_assignment_center_normalizes_single_object_result() -> None:
    payload = _success_response()
    success = payload["successResponse"]
    assert isinstance(success, dict)
    data = success["data"]
    assert isinstance(data, list)
    success["data"] = data[0]
    client = AssignmentCenterClient(
        base_url="https://assignment-single.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=payload)
        ),
    )

    response = client.search_patents("11111279", search_by="patentNumber")

    assert len(response.results) == 1
    assert response.results[0].properties[0].patent_number == "11111279"


def test_assignment_center_preserves_http_404_exception_behavior() -> None:
    client = AssignmentCenterClient(
        base_url="https://assignment-404.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(404, json={"message": "Not Found"})
        ),
    )

    with pytest.raises(UsptoNotFoundError):
        client.search_patents("missing", search_by="patentNumber")


def test_assignment_center_raises_for_error_envelope() -> None:
    client = AssignmentCenterClient(
        base_url="https://assignment-error.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "status": "Failure",
                    "statusCode": 400,
                    "error": {"message": "Invalid criterion"},
                },
            )
        ),
    )

    with pytest.raises(UsptoAPIError, match="Invalid criterion") as exc_info:
        client.search_patents("bad", search_by="patentNumber")

    assert exc_info.value.status_code == 400


def test_export_and_recordation_downloads_support_memory_and_disk(
    tmp_path: Path,
) -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if "exportPublicPatentData" in request.url.path:
            return httpx.Response(
                200,
                content=b"csv-data",
                headers={
                    "Content-Type": "text/csv",
                    "Content-Disposition": 'attachment; filename="results.csv"',
                },
            )
        return httpx.Response(
            200, content=b"%PDF", headers={"Content-Type": "application/pdf"}
        )

    client = AssignmentCenterClient(
        base_url="https://assignment-download.example.test",
        transport=httpx.MockTransport(handler),
    )
    criterion = AssignmentSearchCriterion(
        property="Example Corp.",
        search_by="exactAssigneeName",
    )

    exported = client.export_patent_data([criterion])
    recordation = client.download_recordation(
        46387,
        180,
        output_path=tmp_path / "record.pdf",
    )

    assert exported.content == b"csv-data"
    assert exported.filename == "results.csv"
    assert Path(recordation.path or "").read_bytes() == b"%PDF"
    assert requests == [
        (
            "POST",
            "/ipas/search/api/v3/public/patent/exportPublicPatentData",
        ),
        ("GET", "/ipas/search/api/v3/public/download/patent/46387/180"),
    ]


def test_export_uses_public_ui_criteria_shape_and_validates_row_limit() -> None:
    body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(200, content=b"{}")

    client = AssignmentCenterClient(
        base_url="https://assignment-export.example.test",
        transport=httpx.MockTransport(handler),
    )
    criterion = AssignmentSearchCriterion(
        property="Example Corp.",
        search_by="exactAssigneeName",
        match_type="exact",
        order=1,
    )

    client.export_patent_data([criterion], rows=250)

    assert body == {
        "searchCriteria": [
            {"property": "Example Corp.", "searchBy": "assigneeName"},
            {"property": "250", "searchBy": "rowsNeeded"},
        ]
    }
    with pytest.raises(ValueError, match="between 1 and 1000"):
        client.export_patent_data([criterion], rows=1001)
