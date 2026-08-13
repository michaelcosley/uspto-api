"""PTAB API namespaces and AIA trial endpoint methods."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from uspto_client.models import (
    DocumentDownload,
    DownloadSearchRequest,
    RangeFilter,
    SearchFilter,
    SearchRequest,
    SearchSort,
    UsptoResponse,
)
from uspto_client.ptab_models import (
    TrialDecisionResponse,
    TrialDocument,
    TrialDocumentData,
    TrialDocumentResponse,
    TrialProceedingResponse,
)

if TYPE_CHECKING:
    from uspto_client.client import UsptoClient

ResponseT = TypeVar("ResponseT", bound=UsptoResponse)


class PtabClient:
    """Top-level namespace for Patent Trial and Appeal Board APIs."""

    def __init__(self, client: UsptoClient) -> None:
        self.trials = PtabTrialsClient(client)


class PtabTrialsClient:
    """Client namespace for PTAB AIA trial proceedings and documents."""

    def __init__(self, client: UsptoClient) -> None:
        self._client = client

    def search_proceedings(
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
    ) -> TrialProceedingResponse:
        """Search public PTAB AIA trial proceedings using GET or POST."""

        return self._search(
            "/api/v1/patent/trials/proceedings/search",
            TrialProceedingResponse,
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            facets=facets,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            body=body,
        )

    def download_proceedings_search_results(
        self,
        *,
        q: str | None = None,
        sort: str | list[SearchSort] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        fields: str | list[str] | None = None,
        filters: str | list[SearchFilter] | None = None,
        range_filters: str | list[RangeFilter] | None = None,
        format: Literal["json", "csv"] = "json",
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download PTAB proceeding search results as JSON or CSV."""

        return self._download_search_results(
            "/api/v1/patent/trials/proceedings/search/download",
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            format=format,
            output_path=output_path,
            filename=filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def get_proceeding(self, trial_number: str) -> TrialProceedingResponse:
        """Retrieve proceeding data for one PTAB trial number."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/trials/proceedings/{trial_number}",
            response_model=TrialProceedingResponse,
        )

    def search_documents(
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
    ) -> TrialDocumentResponse:
        """Search all public documents filed in PTAB AIA trials."""

        return self._search(
            "/api/v1/patent/trials/documents/search",
            TrialDocumentResponse,
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            facets=facets,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            body=body,
        )

    def download_documents_search_results(
        self,
        *,
        q: str | None = None,
        sort: str | list[SearchSort] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        fields: str | list[str] | None = None,
        filters: str | list[SearchFilter] | None = None,
        range_filters: str | list[RangeFilter] | None = None,
        format: Literal["json", "csv"] = "json",
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download PTAB document search results as JSON or CSV."""

        return self._download_search_results(
            "/api/v1/patent/trials/documents/search/download",
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            format=format,
            output_path=output_path,
            filename=filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def get_documents(self, trial_number: str) -> TrialDocumentResponse:
        """Retrieve public documents for one PTAB trial number."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/trials/{trial_number}/documents",
            response_model=TrialDocumentResponse,
        )

    def get_document(self, document_identifier: str) -> TrialDocumentResponse:
        """Retrieve one PTAB trial document by its identifier."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/trials/documents/{document_identifier}",
            response_model=TrialDocumentResponse,
        )

    def search_decisions(
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
    ) -> TrialDecisionResponse:
        """Search public PTAB AIA trial decisions using GET or POST."""

        return self._search(
            "/api/v1/patent/trials/decisions/search",
            TrialDecisionResponse,
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            facets=facets,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            body=body,
        )

    def download_decisions_search_results(
        self,
        *,
        q: str | None = None,
        sort: str | list[SearchSort] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        fields: str | list[str] | None = None,
        filters: str | list[SearchFilter] | None = None,
        range_filters: str | list[RangeFilter] | None = None,
        format: Literal["json", "csv"] = "json",
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download PTAB decision search results as JSON or CSV."""

        return self._download_search_results(
            "/api/v1/patent/trials/decisions/search/download",
            q=q,
            sort=sort,
            offset=offset,
            limit=limit,
            fields=fields,
            filters=filters,
            range_filters=range_filters,
            format=format,
            output_path=output_path,
            filename=filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def get_decisions(self, trial_number: str) -> TrialDecisionResponse:
        """Retrieve public decisions for one PTAB trial number."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/trials/{trial_number}/decisions",
            response_model=TrialDecisionResponse,
        )

    def get_decision(self, document_identifier: str) -> TrialDecisionResponse:
        """Retrieve one PTAB trial decision by its document identifier."""

        return self._client.request(
            "GET",
            f"/api/v1/patent/trials/decisions/{document_identifier}",
            response_model=TrialDecisionResponse,
        )

    def download_document(
        self,
        document: TrialDocument | TrialDocumentData | Mapping[str, Any],
        *,
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download a PTAB document using its returned ``fileDownloadURI``."""

        data = _document_data(document)
        download_uri = data.get("fileDownloadURI")
        if not isinstance(download_uri, str) or not download_uri:
            raise ValueError("document does not include documentData.fileDownloadURI")
        document_name = data.get("documentName")
        resolved_filename = filename or (
            document_name if isinstance(document_name, str) else None
        )
        return self._client.download(
            download_uri,
            output_path=output_path,
            filename=resolved_filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def _search(
        self,
        path: str,
        response_model: type[ResponseT],
        *,
        q: str | None,
        sort: str | list[SearchSort] | None,
        offset: int | None,
        limit: int | None,
        facets: str | list[str] | None,
        fields: str | list[str] | None,
        filters: str | list[SearchFilter] | None,
        range_filters: str | list[RangeFilter] | None,
        body: SearchRequest | Mapping[str, Any] | None,
    ) -> ResponseT:
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
                path,
                json=_payload(body),
                response_model=response_model,
            )
        return self._client.request(
            "GET",
            path,
            params=request.to_payload(),
            response_model=response_model,
        )

    def _download_search_results(
        self,
        path: str,
        *,
        q: str | None,
        sort: str | list[SearchSort] | None,
        offset: int | None,
        limit: int | None,
        fields: str | list[str] | None,
        filters: str | list[SearchFilter] | None,
        range_filters: str | list[RangeFilter] | None,
        format: Literal["json", "csv"],
        output_path: str | Path | None,
        filename: str | None,
        avoid_filename_conflicts: bool,
    ) -> DocumentDownload:
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
        return self._client.download(
            path,
            params=request.to_payload(),
            output_path=output_path,
            filename=filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )


def _payload(model_or_mapping: SearchRequest | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(model_or_mapping, SearchRequest):
        return model_or_mapping.to_payload()
    return {key: value for key, value in model_or_mapping.items() if value is not None}


def _document_data(
    document: TrialDocument | TrialDocumentData | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(document, TrialDocument):
        if document.document_data is None:
            return {}
        return document.document_data.model_dump(by_alias=True, exclude_none=True)
    if isinstance(document, TrialDocumentData):
        return document.model_dump(by_alias=True, exclude_none=True)
    nested = document.get("documentData")
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(document)
