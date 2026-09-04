from __future__ import annotations

from uspto_client.ptab_search_options import (
    DECISION_TYPE_FIELD,
    DOCUMENT_CATEGORY_FIELD,
    TRIAL_STATUS_FIELD,
    TRIAL_TYPE_FIELD,
    decision_type_filter,
    document_category_filter,
    patent_owner_counsel_query,
    patent_owner_name_query,
    petitioner_counsel_query,
    petitioner_rpi_name_query,
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


def test_ptab_party_query_helpers_build_phrase_queries() -> None:
    assert patent_owner_counsel_query("Latham & Watkins") == (
        'patentOwnerData.counselName:"Latham & Watkins"'
    )
    assert petitioner_counsel_query("Latham & Watkins") == (
        'regularPetitionerData.counselName:"Latham & Watkins"'
    )
    assert patent_owner_name_query("Example Corp.") == (
        'patentOwnerData.patentOwnerName:"Example Corp."'
    )
    assert petitioner_rpi_name_query("Example Corp.") == (
        'regularPetitionerData.realPartyInInterestName:"Example Corp."'
    )
