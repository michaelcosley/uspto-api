"""Known patent application search options and filter helpers."""

from __future__ import annotations

from typing import Literal

from uspto_client.models import SearchFilter, SearchSort

ApplicationTypeLabelName = Literal[
    "Utility",
    "Provisional",
    "PCT",
    "Design",
    "Plant",
    "Re-Issue",
    "Re-Examination",
    "Supplemental Examination",
    "Regular",
]
PublicationCategory = Literal[
    "Pre-Grant Publications - PGPub",
    "Granted/Issued",
    "Other",
]
BusinessEntityStatusCategory = Literal[
    "Regular Undiscounted",
    "Small",
    "Micro",
]

APPLICATION_TYPE_LABEL_NAME_FIELD = "applicationMetaData.applicationTypeLabelName"
PUBLICATION_CATEGORY_FIELD = "applicationMetaData.publicationCategoryBag"
BUSINESS_ENTITY_STATUS_CATEGORY_FIELD = (
    "applicationMetaData.entityStatusData.businessEntityStatusCategory"
)
FILING_DATE_FIELD = "applicationMetaData.filingDate"

APPLICATION_TYPE_LABEL_NAMES: tuple[ApplicationTypeLabelName, ...] = (
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
PUBLICATION_CATEGORIES: tuple[PublicationCategory, ...] = (
    "Pre-Grant Publications - PGPub",
    "Granted/Issued",
    "Other",
)
BUSINESS_ENTITY_STATUS_CATEGORIES: tuple[BusinessEntityStatusCategory, ...] = (
    "Regular Undiscounted",
    "Small",
    "Micro",
)


def application_type_filter(
    *values: ApplicationTypeLabelName,
) -> SearchFilter:
    """Build a filter for application type labels."""

    return SearchFilter(name=APPLICATION_TYPE_LABEL_NAME_FIELD, value=list(values))


def publication_category_filter(
    *values: PublicationCategory,
) -> SearchFilter:
    """Build a filter for publication categories."""

    return SearchFilter(name=PUBLICATION_CATEGORY_FIELD, value=list(values))


def business_entity_status_filter(
    *values: BusinessEntityStatusCategory,
) -> SearchFilter:
    """Build a filter for business entity status categories."""

    return SearchFilter(name=BUSINESS_ENTITY_STATUS_CATEGORY_FIELD, value=list(values))


def filing_date_sort_desc() -> SearchSort:
    """Build the common filing-date descending sort."""

    return SearchSort(field=FILING_DATE_FIELD, order="Desc")
