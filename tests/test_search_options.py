from __future__ import annotations

from uspto_client import (
    APPLICATION_TYPE_LABEL_NAMES,
    BUSINESS_ENTITY_STATUS_CATEGORIES,
    PUBLICATION_CATEGORIES,
    Pagination,
    SearchRequest,
    application_type_filter,
    business_entity_status_filter,
    filing_date_sort_desc,
    publication_category_filter,
)


def test_documented_search_option_values_are_available() -> None:
    assert APPLICATION_TYPE_LABEL_NAMES == (
        "Utility",
        "Provisional",
        "PCT",
        "Design",
        "Plant",
        "Re-Issue",
        "Re-Examination",
        "Supplemental Examination",
        "Regular",
    )
    assert PUBLICATION_CATEGORIES == (
        "Pre-Grant Publications - PGPub",
        "Granted/Issued",
        "Other",
    )
    assert BUSINESS_ENTITY_STATUS_CATEGORIES == (
        "Regular Undiscounted",
        "Small",
        "Micro",
    )


def test_search_option_helpers_build_online_tool_payload_shape() -> None:
    request = SearchRequest(
        q="",
        filters=[
            application_type_filter("Utility", "Re-Examination"),
            publication_category_filter("Pre-Grant Publications - PGPub", "Other"),
            business_entity_status_filter("Regular Undiscounted", "Small", "Micro"),
        ],
        range_filters=[],
        pagination=Pagination(offset=0, limit=25),
        sort=[filing_date_sort_desc()],
    )

    assert request.to_payload() == {
        "q": "",
        "filters": [
            {
                "name": "applicationMetaData.applicationTypeLabelName",
                "value": ["Utility", "Re-Examination"],
            },
            {
                "name": "applicationMetaData.publicationCategoryBag",
                "value": ["Pre-Grant Publications - PGPub", "Other"],
            },
            {
                "name": (
                    "applicationMetaData.entityStatusData."
                    "businessEntityStatusCategory"
                ),
                "value": ["Regular Undiscounted", "Small", "Micro"],
            },
        ],
        "rangeFilters": [],
        "pagination": {"offset": 0, "limit": 25},
        "sort": [{"field": "applicationMetaData.filingDate", "order": "Desc"}],
    }
