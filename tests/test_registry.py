from __future__ import annotations

from uspto_client.registry import (
    APPLICATION_ENDPOINTS,
    FUTURE_ENDPOINTS,
    OUT_OF_SCOPE_ENDPOINTS,
)


def test_initial_application_endpoint_inventory_is_complete() -> None:
    method_names = {endpoint.method_name for endpoint in APPLICATION_ENDPOINTS}

    assert method_names == {
        "applications.search",
        "applications.download_search_results",
        "applications.get",
        "applications.get_metadata",
        "applications.get_adjustment",
        "applications.get_assignment",
        "applications.get_attorney",
        "applications.get_continuity",
        "applications.get_foreign_priority",
        "applications.get_transactions",
        "applications.get_documents",
        "applications.download_document",
        "applications.get_associated_documents",
        "applications.search_status_codes",
    }
    assert all(endpoint.status == "implemented" for endpoint in APPLICATION_ENDPOINTS)


def test_trademark_endpoints_are_out_of_scope() -> None:
    assert all(endpoint.status == "out-of-scope" for endpoint in OUT_OF_SCOPE_ENDPOINTS)
    assert any("trademark" in endpoint.path for endpoint in OUT_OF_SCOPE_ENDPOINTS)


def test_future_endpoint_families_are_not_marked_implemented() -> None:
    assert FUTURE_ENDPOINTS
    assert all(endpoint.status == "future" for endpoint in FUTURE_ENDPOINTS)
