from __future__ import annotations

from uspto_client.models import (
    Pagination,
    PatentApplicationResponse,
    RangeFilter,
    SearchFilter,
    SearchRequest,
    SearchSort,
)


def test_search_request_uses_uspto_aliases() -> None:
    request = SearchRequest(q="test", range_filters="filingDate:[2024-01-01 TO *]")

    assert request.to_payload() == {
        "q": "test",
        "rangeFilters": "filingDate:[2024-01-01 TO *]",
    }


def test_response_models_allow_extra_fields() -> None:
    response = PatentApplicationResponse.model_validate(
        {
            "count": 1,
            "patentFileWrapperDataBag": [],
            "unexpectedFutureField": "preserved",
        }
    )

    assert response.count == 1
    assert response.raw_data["unexpectedFutureField"] == "preserved"


def test_structured_search_request_matches_uspto_post_payload_shape() -> None:
    request = SearchRequest(
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

    assert request.to_payload() == {
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
