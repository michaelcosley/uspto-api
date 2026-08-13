from __future__ import annotations

from uspto_client.ptab_search_options import (
    DECISION_TYPE_FIELD,
    DOCUMENT_CATEGORY_FIELD,
    TRIAL_STATUS_FIELD,
    TRIAL_TYPE_FIELD,
    decision_type_filter,
    document_category_filter,
    trial_status_filter,
    trial_type_filter,
)


def test_ptab_filter_helpers_use_documented_field_paths() -> None:
    assert trial_type_filter("IPR", "PGR").model_dump(by_alias=True) == {
        "name": TRIAL_TYPE_FIELD,
        "value": ["IPR", "PGR"],
    }
    assert trial_status_filter("Instituted").name == TRIAL_STATUS_FIELD
    assert document_category_filter("Petition").name == DOCUMENT_CATEGORY_FIELD
    assert decision_type_filter("Final Written Decision").name == DECISION_TYPE_FIELD
