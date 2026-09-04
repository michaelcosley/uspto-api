"""Static endpoint inventory for implemented and planned USPTO APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EndpointStatus = Literal["implemented", "experimental", "future", "out-of-scope"]


@dataclass(frozen=True)
class Endpoint:
    """Documented USPTO endpoint metadata."""

    method_name: str
    http_methods: tuple[str, ...]
    path: str
    status: EndpointStatus
    source: str
    notes: str = ""


APPLICATION_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "applications.search",
        ("GET", "POST"),
        "/api/v1/patent/applications/search",
        "implemented",
        "docs/patent-file-wrapper/search.txt",
    ),
    Endpoint(
        "applications.download_search_results",
        ("GET", "POST"),
        "/api/v1/patent/applications/search/download",
        "implemented",
        "docs/uspto-swagger-api.yaml",
    ),
    Endpoint(
        "applications.get",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}",
        "implemented",
        "docs/uspto-swagger-api.yaml",
    ),
    Endpoint(
        "applications.get_metadata",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/meta-data",
        "implemented",
        "docs/patent-file-wrapper/application-data.txt",
    ),
    Endpoint(
        "applications.get_adjustment",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/adjustment",
        "implemented",
        "docs/patent-file-wrapper/patent-term-adjustment.txt",
    ),
    Endpoint(
        "applications.get_assignment",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/assignment",
        "implemented",
        "docs/patent-file-wrapper/assignments.txt",
    ),
    Endpoint(
        "applications.get_attorney",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/attorney",
        "implemented",
        "docs/patent-file-wrapper/attorney-address.txt",
    ),
    Endpoint(
        "applications.get_continuity",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/continuity",
        "implemented",
        "docs/patent-file-wrapper/continuity.txt",
    ),
    Endpoint(
        "applications.get_foreign_priority",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/foreign-priority",
        "implemented",
        "docs/patent-file-wrapper/foreign-priority.txt",
    ),
    Endpoint(
        "applications.get_transactions",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/transactions",
        "implemented",
        "docs/patent-file-wrapper/transactions.txt",
    ),
    Endpoint(
        "applications.get_documents",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/documents",
        "implemented",
        "docs/patent-file-wrapper/documents.txt",
    ),
    Endpoint(
        "applications.download_document",
        ("GET",),
        "/api/v1/download/applications/{applicationNumberText}/{documentIdentifier}.pdf",
        "implemented",
        "live USPTO document metadata response",
        "Download URL appears in document downloadOptionBag entries.",
    ),
    Endpoint(
        "applications.get_associated_documents",
        ("GET",),
        "/api/v1/patent/applications/{applicationNumberText}/associated-documents",
        "implemented",
        "docs/uspto-swagger-api.yaml",
    ),
    Endpoint(
        "applications.search_status_codes",
        ("GET", "POST"),
        "/api/v1/patent/status-codes",
        "implemented",
        "docs/uspto-swagger-api.yaml",
    ),
)

PTAB_TRIAL_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "ptab.trials.search_proceedings",
        ("GET", "POST"),
        "/api/v1/patent/trials/proceedings/search",
        "implemented",
        "docs/ptab-trials/search-proceedings.txt",
    ),
    Endpoint(
        "ptab.trials.download_proceedings_search_results",
        ("GET",),
        "/api/v1/patent/trials/proceedings/search/download",
        "implemented",
        "docs/ptab-trials/download-proceeding-search-results.txt",
    ),
    Endpoint(
        "ptab.trials.get_proceeding",
        ("GET",),
        "/api/v1/patent/trials/proceedings/{trialNumber}",
        "implemented",
        "docs/ptab-trials/search-proceedings-by-trial-number.txt",
    ),
    Endpoint(
        "ptab.trials.search_documents",
        ("GET", "POST"),
        "/api/v1/patent/trials/documents/search",
        "implemented",
        "docs/ptab-trials/search-documents.txt",
    ),
    Endpoint(
        "ptab.trials.download_documents_search_results",
        ("GET",),
        "/api/v1/patent/trials/documents/search/download",
        "implemented",
        "docs/ptab-trials/download-documents-search-results.txt",
    ),
    Endpoint(
        "ptab.trials.get_documents",
        ("GET",),
        "/api/v1/patent/trials/{trialNumber}/documents",
        "implemented",
        "docs/ptab-trials/search-documents-by-trial-number.txt",
    ),
    Endpoint(
        "ptab.trials.get_document",
        ("GET",),
        "/api/v1/patent/trials/documents/{documentIdentifier}",
        "implemented",
        "docs/ptab-trials/search-documents-by-document-identifier.txt",
    ),
    Endpoint(
        "ptab.trials.search_decisions",
        ("GET", "POST"),
        "/api/v1/patent/trials/decisions/search",
        "implemented",
        "docs/ptab-trials/search-decisions.txt",
    ),
    Endpoint(
        "ptab.trials.download_decisions_search_results",
        ("GET",),
        "/api/v1/patent/trials/decisions/search/download",
        "implemented",
        "docs/ptab-trials/download-decisions-search-results.txt",
    ),
    Endpoint(
        "ptab.trials.get_decisions",
        ("GET",),
        "/api/v1/patent/trials/{trialNumber}/decisions",
        "implemented",
        "docs/ptab-trials/seach-decisions-by-trial-number.txt",
    ),
    Endpoint(
        "ptab.trials.get_decision",
        ("GET",),
        "/api/v1/patent/trials/decisions/{documentIdentifier}",
        "implemented",
        "docs/ptab-trials/search-decisions-by-document-identifier.txt",
    ),
)

ASSIGNMENT_CENTER_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "assignment_center.search_patents",
        ("POST",),
        "/ipas/search/api/v3/public/search/patent",
        "experimental",
        "official Assignment Center public web application",
        "Supports single-field and advanced patent-recordation searches.",
    ),
    Endpoint(
        "assignment_center.get_reel_frame",
        ("POST",),
        "/ipas/search/api/v3/public/search/patent",
        "experimental",
        "official Assignment Center public web application",
    ),
    Endpoint(
        "assignment_center.download_recordation",
        ("GET",),
        "/ipas/search/api/v3/public/download/patent/{reel}/{frame}",
        "experimental",
        "official Assignment Center public web application",
    ),
    Endpoint(
        "assignment_center.export_patent_data",
        ("POST",),
        "/ipas/search/api/v3/public/patent/exportPublicPatentData",
        "experimental",
        "official Assignment Center public web application",
        "The advertised public route returned HTTP 404 during 2026-09-04 verification.",
    ),
)

FUTURE_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "petition_decisions.search",
        ("GET", "POST"),
        "/api/v1/petition/decisions/search",
        "future",
        "docs/uspto-swagger-api.yaml",
        "Petition decisions require separate scope confirmation.",
    ),
    Endpoint(
        "bulk_datasets.search",
        ("GET",),
        "/api/v1/datasets/products/search",
        "future",
        "docs/uspto-swagger-api.yaml",
        "Bulk datasets are not part of the initial client surface.",
    ),
)

OUT_OF_SCOPE_ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint(
        "trademarks",
        tuple(),
        "/api/v1/trademark/*",
        "out-of-scope",
        "project scope",
        "Trademark APIs are intentionally excluded.",
    ),
)

ALL_ENDPOINTS = (
    APPLICATION_ENDPOINTS
    + PTAB_TRIAL_ENDPOINTS
    + ASSIGNMENT_CENTER_ENDPOINTS
    + FUTURE_ENDPOINTS
    + OUT_OF_SCOPE_ENDPOINTS
)
