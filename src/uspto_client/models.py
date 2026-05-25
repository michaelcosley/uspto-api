"""Pydantic request and response models for USPTO APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UsptoModel(BaseModel):
    """Base Pydantic model that tolerates additive USPTO schema changes."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


SortOrder = Literal["Asc", "Desc", "asc", "desc", "ASC", "DESC"]


class SearchFilter(UsptoModel):
    """USPTO search filter clause."""

    name: str
    value: list[Any]


class RangeFilter(UsptoModel):
    """USPTO range filter clause.

    Range values are inclusive per the USPTO syntax guide.
    """

    field: str
    value_from: str | int | float = Field(alias="valueFrom")
    value_to: str | int | float = Field(alias="valueTo")


class SearchSort(UsptoModel):
    """USPTO search sort clause."""

    field: str
    order: SortOrder


class Pagination(UsptoModel):
    """USPTO search pagination object."""

    offset: int = 0
    limit: int = 25


class SearchRequest(UsptoModel):
    """Structured search request for USPTO search endpoints."""

    q: str | None = None
    sort: str | list[SearchSort] | None = None
    offset: int | None = None
    limit: int | None = None
    facets: str | list[str] | None = None
    fields: str | list[str] | None = None
    filters: str | list[SearchFilter] | None = None
    range_filters: str | list[RangeFilter] | None = Field(
        default=None,
        alias="rangeFilters",
    )
    pagination: Pagination | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a USPTO-compatible payload or query-param dictionary."""

        return self.model_dump(by_alias=True, exclude_none=True)


class DownloadSearchRequest(SearchRequest):
    """Structured request for search download endpoints."""

    format: Literal["json", "csv"] | None = None


class UsptoResponse(UsptoModel):
    """Common USPTO response wrapper."""

    count: int | None = None
    request_identifier: str | None = Field(default=None, alias="requestIdentifier")

    @property
    def raw_data(self) -> dict[str, Any]:
        """Return the complete model data using USPTO field aliases."""

        return self.model_dump(by_alias=True)


class PatentApplicationResponse(UsptoResponse):
    """Response model for Patent File Wrapper application data."""

    patent_file_wrapper_data_bag: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="patentFileWrapperDataBag",
    )
    document_bag: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="documentBag",
    )


class PatentDownloadResponse(UsptoResponse):
    """Response model for patent search download endpoints."""

    patent_data: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="patentdata",
    )


class StatusCodeSearchResponse(UsptoResponse):
    """Response model for patent status-code search results."""

    status_code_data_bag: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="statusCodeDataBag",
    )
    status_code_bag: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="statusCodeBag",
    )


class DocumentDownload(UsptoModel):
    """Downloaded patent application document content."""

    content: bytes
    filename: str
    path: str | None = None
    content_type: str | None = None
    status_code: int
