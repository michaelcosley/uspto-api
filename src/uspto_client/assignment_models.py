"""Models for the public USPTO Assignment Center patent search service."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from uspto_client.models import UsptoModel


class AssignmentDataFilter(UsptoModel):
    """Assignment Center result filtering and paging options."""

    filter_by: str = Field(default="all", alias="filterBy")
    rows_per_page: int = Field(default=100, alias="rowsPerPage", ge=1)
    current_page: int = Field(default=1, alias="currentPage", ge=1)


class AssignmentSearchCriterion(UsptoModel):
    """One criterion in an Assignment Center advanced search."""

    property: str
    search_by: str = Field(alias="searchBy")
    match_type: str = Field(default="", alias="matchType")
    order: int = 0
    relation: str = ""


class AssignmentAssignee(UsptoModel):
    """An assignee named in a recorded transaction."""

    assignee_name: str | None = Field(default=None, alias="assigneeName")
    assignee_sequence_number: int | None = Field(
        default=None,
        alias="assigneeSequenceNumber",
    )
    address_line_1: str | None = Field(default=None, alias="addressLine1")
    address_line_2: str | None = Field(default=None, alias="addressLine2")
    address_line_3: str | None = Field(default=None, alias="addressLine3")
    address_line_4: str | None = Field(default=None, alias="addressLine4")
    city: str | None = None
    state: str | None = None
    zip_code: str | None = Field(default=None, alias="zipCode")
    country: str | None = None
    ict_state_code: str | None = Field(default=None, alias="ictStateCode")
    ict_country_code: str | None = Field(default=None, alias="ictCountryCode")


class AssignmentAssignor(UsptoModel):
    """An assignor named in a recorded transaction."""

    assignor_name: str | None = Field(default=None, alias="assignorName")
    assignor_sequence_number: int | None = Field(
        default=None,
        alias="assignorSequenceNumber",
    )
    execution_date: str | None = Field(default=None, alias="executionDate")
    acknowledged_date: str | None = Field(default=None, alias="acknowledgedDate")


class AssignmentCorrespondent(UsptoModel):
    """Correspondent information associated with a recorded transaction."""

    name: str | None = None
    address_line_1: str | None = Field(default=None, alias="addressLine1")
    address_line_2: str | None = Field(default=None, alias="addressLine2")
    address_line_3: str | None = Field(default=None, alias="addressLine3")
    address_line_4: str | None = Field(default=None, alias="addressLine4")
    city: str | None = None
    state: str | None = None
    zip_code: str | None = Field(default=None, alias="zipCode")
    country: str | None = None


class AssignmentRecord(UsptoModel):
    """One document recorded against one or more patent properties."""

    assignees: list[AssignmentAssignee] = Field(default_factory=list)
    assignors: list[AssignmentAssignor] = Field(default_factory=list)
    assignment_sequence: int | None = Field(default=None, alias="assignmentSequence")
    assignor_execution_date: str | None = Field(
        default=None,
        alias="assignorExecutionDate",
    )
    conveyance: str | None = None
    conveyance_code: int | None = Field(default=None, alias="conveyanceCode")
    correspondent: AssignmentCorrespondent | None = None
    reel_number: int | str | None = Field(default=None, alias="reelNumber")
    frame_number: int | str | None = Field(default=None, alias="frameNumber")
    reel_frame: str | None = Field(default=None, alias="reelFrame")
    page_count: int | None = Field(default=None, alias="pageCount")
    recordation_date: str | None = Field(default=None, alias="recordationDate")
    receipt_date: str | None = Field(default=None, alias="receiptDate")
    mail_date: str | None = Field(default=None, alias="mailDate")
    attorney_docket_number: str | None = Field(
        default=None,
        alias="attorneyDocketNumber",
    )
    image_available: bool | None = Field(
        default=None,
        alias="imageAvailableStatusCode",
    )
    image_url: str | None = Field(default=None, alias="imageURL")


class AssignmentPatentProperty(UsptoModel):
    """Patent or application identified by an Assignment Center result."""

    application_number: str | None = Field(default=None, alias="applicationNumber")
    filing_date: str | None = Field(default=None, alias="fillingDate")
    invention_title: str | None = Field(default=None, alias="inventionTitle")
    inventors: str | None = None
    issue_date: str | None = Field(default=None, alias="issueDate")
    patent_number: str | None = Field(default=None, alias="patentNumber")
    publication_number: str | None = Field(default=None, alias="publicationNumber")
    publication_date: str | None = Field(default=None, alias="publicationDate")
    pct_number: str | None = Field(default=None, alias="pctNumber")
    property_sequence_number: int | None = Field(
        default=None,
        alias="propertySequenceNumber",
    )


class AssignmentSearchResult(UsptoModel):
    """One result grouping returned by Assignment Center."""

    assignment: AssignmentRecord | list[AssignmentRecord] | None = None
    properties: list[AssignmentPatentProperty] = Field(default_factory=list)
    number_of_assignments: int | None = Field(default=None, alias="noOfAssignments")

    @field_validator("properties", mode="before")
    @classmethod
    def normalize_single_property(cls, value: Any) -> Any:
        """Normalize the API's object-for-one/list-for-many property shape."""

        if isinstance(value, dict):
            return [value]
        return value

    @property
    def assignment_records(self) -> list[AssignmentRecord]:
        """Return the result's assignment value as a consistently shaped list."""

        if self.assignment is None:
            return []
        if isinstance(self.assignment, list):
            return self.assignment
        return [self.assignment]


class AssignmentSearchSuccess(UsptoModel):
    """Successful Assignment Center patent search response body."""

    data: list[AssignmentSearchResult] | None = None
    total_rows: int = Field(default=0, alias="totalRows")
    backend_pagination: bool | None = Field(default=None, alias="backendPagination")
    filtered_rows_count: int | None = Field(default=None, alias="filteredRowsCount")
    message: str | None = None

    @field_validator("data", mode="before")
    @classmethod
    def normalize_single_result(cls, value: Any) -> Any:
        """Normalize the API's object-for-one/list-for-many response shape."""

        if isinstance(value, dict):
            return [value]
        return value

    @property
    def results(self) -> list[AssignmentSearchResult]:
        """Return results, normalizing the service's null empty-result value."""

        return self.data or []


class AssignmentSearchResponse(UsptoModel):
    """Top-level Assignment Center public API response envelope."""

    status: str | None = None
    status_code: int | None = Field(default=None, alias="statusCode")
    error: Any | None = None
    success_response: AssignmentSearchSuccess | None = Field(
        default=None,
        alias="successResponse",
    )

    @property
    def results(self) -> list[AssignmentSearchResult]:
        """Return normalized search results from the nested service envelope."""

        if self.success_response is None:
            return []
        return self.success_response.results

    @property
    def total_rows(self) -> int:
        """Return the service-reported result total."""

        if self.success_response is None:
            return 0
        return self.success_response.total_rows
