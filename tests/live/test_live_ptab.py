from __future__ import annotations

import os

import pytest

from uspto_client import UsptoClient

TRIAL_NUMBER = "IPR2024-00001"


@pytest.mark.live
def test_live_ptab_trial_endpoint_families() -> None:
    with UsptoClient(api_key=os.environ["USPTO_API_KEY"]) as client:
        proceedings = client.ptab.trials.search_proceedings(limit=1)
        proceeding = client.ptab.trials.get_proceeding(TRIAL_NUMBER)
        documents = client.ptab.trials.get_documents(TRIAL_NUMBER)
        decisions = client.ptab.trials.get_decisions(TRIAL_NUMBER)

    assert proceedings.proceedings
    assert proceeding.proceedings[0].trial_number == TRIAL_NUMBER
    assert documents.documents
    assert decisions.decisions


@pytest.mark.live
def test_live_ptab_record_lookups_and_pdf_download() -> None:
    with UsptoClient(api_key=os.environ["USPTO_API_KEY"]) as client:
        documents = client.ptab.trials.get_documents(TRIAL_NUMBER)
        record = documents.documents[0]
        assert record.document_data is not None
        assert record.document_data.document_identifier
        looked_up = client.ptab.trials.get_document(
            record.document_data.document_identifier
        )
        download = client.ptab.trials.download_document(looked_up.documents[0])

    assert looked_up.documents
    assert download.content.startswith(b"%PDF")


@pytest.mark.live
def test_live_ptab_search_export_is_an_attachment() -> None:
    with UsptoClient(api_key=os.environ["USPTO_API_KEY"]) as client:
        download = client.ptab.trials.download_proceedings_search_results(
            q=f"trialNumber:{TRIAL_NUMBER}",
            limit=1,
            format="csv",
        )

    assert download.filename.endswith(".csv")
    assert download.content.startswith(b"trialNumber,")
