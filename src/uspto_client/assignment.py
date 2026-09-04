"""Experimental client for the public USPTO Assignment Center patent API."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from uspto_client.assignment_models import (
    AssignmentDataFilter,
    AssignmentSearchCriterion,
    AssignmentSearchResponse,
)
from uspto_client.client import (
    _error_from_response,
    _filename_from_content_disposition,
    _filename_from_path,
    _json_body,
    _safe_filename,
    _write_download,
)
from uspto_client.errors import UsptoAPIError
from uspto_client.models import DocumentDownload
from uspto_client.rate_limit import (
    DEFAULT_MONOTONIC,
    MonotonicCallable,
    PacingConfig,
    RetryConfig,
    SleepCallable,
    get_request_coordinator,
    retry_after_delay,
)

ASSIGNMENT_CENTER_BASE_URL = "https://assignmentcenter.uspto.gov"
PATENT_SEARCH_PATH = "/ipas/search/api/v3/public/search/patent"
PATENT_EXPORT_PATH = "/ipas/search/api/v3/public/patent/exportPublicPatentData"

APPLICATION_NUMBER_SEARCH = "applicationNumber"
PATENT_NUMBER_SEARCH = "patentNumber"
PUBLICATION_NUMBER_SEARCH = "publicationNumber"
REEL_FRAME_SEARCH = "reelFrame"
EXACT_ASSIGNEE_NAME_SEARCH = "exactAssigneeName"
PARTIAL_ASSIGNEE_NAME_SEARCH = "partialAssigneeName"
EXACT_ASSIGNOR_NAME_SEARCH = "exactAssignorName"
PARTIAL_ASSIGNOR_NAME_SEARCH = "partialAssignorName"
EXACT_CORRESPONDENT_NAME_SEARCH = "exactCorrespondentName"
PARTIAL_CORRESPONDENT_NAME_SEARCH = "partialCorrespondentName"
ASSIGNEE_NAME_EXPORT_SEARCH = "assigneeName"
ASSIGNOR_NAME_EXPORT_SEARCH = "assignorName"
CORRESPONDENT_NAME_EXPORT_SEARCH = "correspondentName"
ROWS_NEEDED_EXPORT_SEARCH = "rowsNeeded"


class AssignmentCenterClient:
    """Sync client for the public Assignment Center patent search service.

    This API is used by the official public web application but does not have
    the same published, versioned contract as the USPTO Open Data Portal APIs.
    Models therefore tolerate additive response fields.
    """

    def __init__(
        self,
        *,
        base_url: str = ASSIGNMENT_CENTER_BASE_URL,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        retry_config: RetryConfig | None = None,
        pacing_config: PacingConfig | None = None,
        sleep: SleepCallable = time.sleep,
        monotonic: MonotonicCallable = DEFAULT_MONOTONIC,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retry_config = retry_config or RetryConfig()
        self.pacing_config = pacing_config or PacingConfig()
        self._sleep = sleep
        self._monotonic = monotonic
        self._coordinator = get_request_coordinator(
            f"assignment-center:{self.base_url}"
        )
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._http.close()

    def __enter__(self) -> AssignmentCenterClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def search_patents(
        self,
        query: str,
        *,
        search_by: str,
        data_filter: AssignmentDataFilter | Mapping[str, Any] | None = None,
    ) -> AssignmentSearchResponse:
        """Search recorded patent transactions using one public search field."""

        if not query:
            raise ValueError("query is required")
        return self._search(
            {
                "property": query,
                "searchBy": search_by,
                "dataFilter": _data_filter_payload(data_filter),
            }
        )

    def search_exact_assignee(
        self,
        name: str,
        *,
        data_filter: AssignmentDataFilter | Mapping[str, Any] | None = None,
    ) -> AssignmentSearchResponse:
        """Search transactions associated with an exact assignee name."""

        return self.search_patents(
            name,
            search_by=EXACT_ASSIGNEE_NAME_SEARCH,
            data_filter=data_filter,
        )

    def search_partial_assignee(
        self,
        name: str,
        *,
        data_filter: AssignmentDataFilter | Mapping[str, Any] | None = None,
    ) -> AssignmentSearchResponse:
        """Search transactions associated with a partial assignee name."""

        return self.search_patents(
            name,
            search_by=PARTIAL_ASSIGNEE_NAME_SEARCH,
            data_filter=data_filter,
        )

    def advanced_search(
        self,
        criteria: Sequence[AssignmentSearchCriterion | Mapping[str, Any]],
        *,
        data_filter: AssignmentDataFilter | Mapping[str, Any] | None = None,
    ) -> AssignmentSearchResponse:
        """Run a multi-criterion public patent assignment search."""

        criteria_payload = _criteria_payload(criteria)
        if not criteria_payload:
            raise ValueError("at least one search criterion is required")
        return self._search(
            {
                "searchCriteria": criteria_payload,
                "dataFilter": _data_filter_payload(data_filter),
            }
        )

    def get_reel_frame(
        self,
        reel_number: int | str,
        frame_number: int | str,
        *,
        data_filter: AssignmentDataFilter | Mapping[str, Any] | None = None,
    ) -> AssignmentSearchResponse:
        """Retrieve public patent assignment details by reel and frame."""

        return self._search(
            {
                "reelNumber": str(reel_number),
                "frameNumber": str(frame_number),
                "searchBy": REEL_FRAME_SEARCH,
                "dataFilter": _data_filter_payload(data_filter),
            }
        )

    def export_patent_data(
        self,
        criteria: Sequence[AssignmentSearchCriterion | Mapping[str, Any]],
        *,
        rows: int = 100,
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Export public patent assignment results for search criteria."""

        criteria_payload = _export_criteria_payload(criteria, rows=rows)
        if not criteria_payload:
            raise ValueError("at least one search criterion is required")
        return self._download(
            "POST",
            PATENT_EXPORT_PATH,
            json={"searchCriteria": criteria_payload},
            output_path=output_path,
            filename=filename,
            default_filename="assignment-center-patent-export.json",
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def download_recordation(
        self,
        reel_number: int | str,
        frame_number: int | str,
        *,
        output_path: str | Path | None = None,
        filename: str | None = None,
        avoid_filename_conflicts: bool = True,
    ) -> DocumentDownload:
        """Download the public recorded document image for a reel/frame."""

        reel = str(reel_number)
        frame = str(frame_number)
        return self._download(
            "GET",
            f"/ipas/search/api/v3/public/download/patent/{reel}/{frame}",
            output_path=output_path,
            filename=filename,
            default_filename=f"{reel}-{frame}.pdf",
            avoid_filename_conflicts=avoid_filename_conflicts,
        )

    def _search(self, body: Mapping[str, Any]) -> AssignmentSearchResponse:
        response = self._send("POST", PATENT_SEARCH_PATH, json=body, download=False)
        data = _json_body(response)
        try:
            parsed = AssignmentSearchResponse.model_validate(data)
        except ValidationError as exc:
            raise UsptoAPIError(
                "Assignment Center response did not match the expected model",
                status_code=response.status_code,
                response_body=data,
            ) from exc
        if parsed.status_code is not None and parsed.status_code >= 400:
            raise UsptoAPIError(
                _assignment_error_message(parsed.error) or "Assignment Center error",
                status_code=parsed.status_code,
                response_body=data,
            )
        return parsed

    def _download(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        output_path: str | Path | None,
        filename: str | None,
        default_filename: str,
        avoid_filename_conflicts: bool,
    ) -> DocumentDownload:
        response = self._send(method, path, json=json, download=True)
        resolved_filename = _safe_filename(
            filename
            or _filename_from_content_disposition(
                response.headers.get("Content-Disposition")
            )
            or default_filename
            or _filename_from_path(str(response.url))
        )
        written_path = _write_download(
            response.content,
            output_path=output_path,
            filename=resolved_filename,
            avoid_filename_conflicts=avoid_filename_conflicts,
        )
        return DocumentDownload(
            content=response.content,
            filename=resolved_filename,
            path=str(written_path) if written_path is not None else None,
            content_type=response.headers.get("Content-Type"),
            status_code=response.status_code,
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        download: bool,
    ) -> httpx.Response:
        attempts = 0
        while True:
            attempts += 1
            interval = (
                self.pacing_config.download_interval_seconds
                if download
                else self.pacing_config.request_interval_seconds
            )
            try:
                with self._coordinator.lock:
                    self._coordinator.wait(
                        interval,
                        sleep=self._sleep,
                        monotonic=self._monotonic,
                    )
                    response = self._http.request(method, path, json=json)
            except httpx.TransportError:
                if not self._should_retry_transport(attempts):
                    raise
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue
            if response.status_code == 429 and self._should_retry_429(attempts):
                delay = retry_after_delay(
                    response.headers.get("Retry-After"),
                    minimum_seconds=self.retry_config.min_429_delay_seconds,
                )
                response.close()
                self._sleep(delay)
                continue
            if response.status_code >= 500 and self._should_retry_5xx(attempts):
                response.close()
                self._sleep(self.retry_config.backoff_delay(attempts))
                continue
            if response.is_error:
                raise _error_from_response(response)
            return response

    def _should_retry_429(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_429 and attempts < self.retry_config.max_attempts
        )

    def _should_retry_5xx(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_5xx and attempts < self.retry_config.max_attempts
        )

    def _should_retry_transport(self, attempts: int) -> bool:
        return (
            self.retry_config.retry_on_transport_error
            and attempts < self.retry_config.max_attempts
        )


def _data_filter_payload(
    value: AssignmentDataFilter | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if value is None:
        model = AssignmentDataFilter()
    elif isinstance(value, AssignmentDataFilter):
        model = value
    else:
        model = AssignmentDataFilter.model_validate(value)
    return model.model_dump(by_alias=True)


def _criteria_payload(
    criteria: Sequence[AssignmentSearchCriterion | Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        (
            criterion.model_dump(by_alias=True)
            if isinstance(criterion, AssignmentSearchCriterion)
            else AssignmentSearchCriterion.model_validate(criterion).model_dump(
                by_alias=True
            )
        )
        for criterion in criteria
    ]


def _export_criteria_payload(
    criteria: Sequence[AssignmentSearchCriterion | Mapping[str, Any]],
    *,
    rows: int,
) -> list[dict[str, Any]]:
    if not 1 <= rows <= 1000:
        raise ValueError("rows must be between 1 and 1000")
    search_key_map = {
        EXACT_ASSIGNEE_NAME_SEARCH: ASSIGNEE_NAME_EXPORT_SEARCH,
        PARTIAL_ASSIGNEE_NAME_SEARCH: ASSIGNEE_NAME_EXPORT_SEARCH,
        EXACT_ASSIGNOR_NAME_SEARCH: ASSIGNOR_NAME_EXPORT_SEARCH,
        PARTIAL_ASSIGNOR_NAME_SEARCH: ASSIGNOR_NAME_EXPORT_SEARCH,
        EXACT_CORRESPONDENT_NAME_SEARCH: CORRESPONDENT_NAME_EXPORT_SEARCH,
        PARTIAL_CORRESPONDENT_NAME_SEARCH: CORRESPONDENT_NAME_EXPORT_SEARCH,
    }
    payload: list[dict[str, Any]] = []
    for criterion in criteria:
        model = (
            criterion
            if isinstance(criterion, AssignmentSearchCriterion)
            else AssignmentSearchCriterion.model_validate(criterion)
        )
        payload.append(
            {
                "property": model.property,
                "searchBy": search_key_map.get(model.search_by, model.search_by),
            }
        )
    payload.append({"property": str(rows), "searchBy": ROWS_NEEDED_EXPORT_SEARCH})
    return payload


def _assignment_error_message(error: Any) -> str | None:
    if isinstance(error, str) and error:
        return error
    if isinstance(error, Mapping):
        for key in ("message", "error", "detail"):
            value = error.get(key)
            if isinstance(value, str) and value:
                return value
    return None
