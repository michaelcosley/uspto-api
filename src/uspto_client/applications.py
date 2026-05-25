"""Patent application endpoint methods."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from uspto_client.filenames import (
    DocumentCodeMapper,
    FilenameFormat,
    build_document_filename,
)
from uspto_client.models import (
    DocumentDownload,
    DownloadSearchRequest,
    PatentApplicationResponse,
    PatentDownloadResponse,
    RangeFilter,
    SearchFilter,
    SearchRequest,
    SearchSort,
    StatusCodeSearchResponse,
)

if TYPE_CHECKING:
    from uspto_client.client import UsptoClient


class ApplicationsClient:
    """Client namespace for Patent File Wrapper application endpoints."""

    def __init__(self, client: UsptoClient) -> None:
        self._client = client

    def search(
        self,
        *,
        q: str | None = None,
        sort: str | list[SearchSort] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        facets: str | list[str] | None = None,
        fields: str | list[str] | None = None,
        filters: str | list[SearchFilter] | None = None,
        range_filters: str | list[RangeFilter] | None = None,
        body: SearchRequest | Mapping[str, Any] | None = None,
    ) -> PatentApplicationResponse:
        """Search patent applications using query params or a JSON body."""

        request = SearchRequest.model_validate(
            {
                "q": q,
                "sort": sort,
                "offset": offset,
                "limit": limit,
                "facets": facets,
                "fields": fields,
                "filters": filters,
                "rangeFilters": range_filters,
            }
        )
        if body is not None:
            return self._client.request(
                "POST",
                "/api/v1/patent/applications/search",
                json=_payload(body),
                response_model=PatentApplicationResponse,
            )
        return self._client.request(
            "GET",
            "/api/v1/patent/applications/search",
            params=request.to_payload(),
            response_model=PatentApplicationResponse,
        )

    def download_search_results(
        self,
        *,
        q: str | None = None,
        sort: str | list[SearchSort] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        fields: str | list[str] | None = None,
        filters: str | list[SearchFilter] | None = None,
        range_filters: str | list[RangeFilter] | None = None,
        format: Literal["json", "csv"] | None = None,
        body: DownloadSearchRequest | Mapping[str, Any] | None = None,
    ) -> PatentDownloadResponse:
        """Download patent application search results."""

        request = DownloadSearchRequest.model_validate(
            {
                "q": q,
                "sort": sort,
                "offset": offset,
                "limit": limit,
                "fields": fields,
                "filters": filters,
                "rangeFilters": range_filters,
                "format": format,
            }
        )
        if body is not None:
            return self._client.request(
                "POST",
                "/api/v1/patent/applications/search/download",
                json=_payload(body),
                response_model=PatentDownloadResponse,
            )
        return self._client.request(
            "GET",
            "/api/v1/patent/applications/search/download",
            params=request.to_payload(),
            response_model=PatentDownloadResponse,
        )

    def get(self, application_number: str) -> PatentApplicationResponse:
        """Get patent application data for an application number."""

        return self._get_application_path(application_number, "")

    def get_metadata(self, application_number: str) -> PatentApplicationResponse:
        """Get application metadata for an application number."""

        return self._get_application_path(application_number, "/meta-data")

    def get_adjustment(self, application_number: str) -> PatentApplicationResponse:
        """Get patent term adjustment data for an application number."""

        return self._get_application_path(application_number, "/adjustment")

    def get_assignment(self, application_number: str) -> PatentApplicationResponse:
        """Get assignment data for an application number."""

        return self._get_application_path(application_number, "/assignment")

    def get_attorney(self, application_number: str) -> PatentApplicationResponse:
        """Get attorney/agent data for an application number."""

        return self._get_application_path(application_number, "/attorney")

    def get_continuity(self, application_number: str) -> PatentApplicationResponse:
        """Get continuity data for an application number."""

        return self._get_application_path(application_number, "/continuity")

    def get_foreign_priority(
        self,
        application_number: str,
    ) -> PatentApplicationResponse:
        """Get foreign priority data for an application number."""

        return self._get_application_path(application_number, "/foreign-priority")

    def get_transactions(self, application_number: str) -> PatentApplicationResponse:
        """Get transaction data for an application number."""

        return self._get_application_path(application_number, "/transactions")

    def get_documents(
        self,
        application_number: str,
        *,
        document_codes: str | None = None,
        official_date_from: str | None = None,
        official_date_to: str | None = None,
    ) -> PatentApplicationResponse:
        """Get document metadata for an application number."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/applications/{application_number}/documents",
            params={
                "documentCodes": document_codes,
                "officialDateFrom": official_date_from,
                "officialDateTo": official_date_to,
            },
            response_model=PatentApplicationResponse,
        )

    def download_document(
        self,
        application_number: str,
        document_identifier: str,
        *,
        output_path: str | Path | None = None,
        filename: str | None = None,
        file_format: Literal["pdf"] = "pdf",
        document: Mapping[str, Any] | None = None,
        filename_format: FilenameFormat = "document_id",
        filename_template: str | None = None,
        patent_number: str | None = None,
        doc_code_mapping_path: str | Path | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download an application document, optionally writing it to disk.

        Pass ``document`` from ``get_documents(...).document_bag`` to build
        names from dates, application numbers, patent numbers, and document code
        mappings. If ``filename`` is provided, it wins over generated names.
        """

        resolved_filename = filename
        if resolved_filename is None and document is not None:
            mapper = (
                DocumentCodeMapper.from_csv_path(doc_code_mapping_path)
                if doc_code_mapping_path is not None
                else DocumentCodeMapper.from_default()
            )
            resolved_filename = build_document_filename(
                dict(document),
                filename_format=filename_format,
                filename_template=filename_template,
                patent_number=patent_number,
                mapper=mapper,
                extension=file_format,
            ).filename

        return self._client.download(
            (
                f"/api/v1/download/applications/{application_number}/"
                f"{document_identifier}.{file_format}"
            ),
            output_path=output_path,
            filename=resolved_filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def get_associated_documents(
        self,
        application_number: str,
    ) -> PatentApplicationResponse:
        """Get associated publication/grant document metadata."""

        return self._get_application_path(application_number, "/associated-documents")

    def search_status_codes(
        self,
        *,
        q: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        body: SearchRequest | Mapping[str, Any] | None = None,
    ) -> StatusCodeSearchResponse:
        """Search patent application status codes."""

        if body is not None:
            return self._client.request(
                "POST",
                "/api/v1/patent/status-codes",
                json=_payload(body),
                response_model=StatusCodeSearchResponse,
            )
        return self._client.request(
            "GET",
            "/api/v1/patent/status-codes",
            params={"q": q, "offset": offset, "limit": limit},
            response_model=StatusCodeSearchResponse,
        )

    def _get_application_path(
        self,
        application_number: str,
        suffix: str,
    ) -> PatentApplicationResponse:
        return self._client.request(
            "GET",
            f"/api/v1/patent/applications/{application_number}{suffix}",
            response_model=PatentApplicationResponse,
        )


def _payload(model_or_mapping: SearchRequest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(model_or_mapping, SearchRequest):
        return model_or_mapping.to_payload()
    return {key: value for key, value in model_or_mapping.items() if value is not None}
