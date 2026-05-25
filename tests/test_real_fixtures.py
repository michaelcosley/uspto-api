from __future__ import annotations

import json
from pathlib import Path

from uspto_client.models import (
    PatentApplicationResponse,
    PatentDownloadResponse,
    StatusCodeSearchResponse,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "uspto" / "reexam_90016176"


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_reexam_metadata_fixture_matches_expected_general_record() -> None:
    response = PatentApplicationResponse.model_validate(_load_fixture("metadata.json"))
    record = response.patent_file_wrapper_data_bag[0]
    metadata = record["applicationMetaData"]

    assert response.count == 1
    assert record["applicationNumberText"] == "90016176"
    assert metadata["applicationTypeLabelName"] == "Re-Examination"
    assert metadata["applicationStatusCode"] == 412


def test_reexam_document_fixtures_parse_expected_document_shapes() -> None:
    all_documents = PatentApplicationResponse.model_validate(
        _load_fixture("documents.json")
    )
    bib_document = PatentApplicationResponse.model_validate(
        _load_fixture("documents_bib.json")
    )

    assert all_documents.count == 18
    assert len(all_documents.document_bag) == 18
    assert bib_document.count == 1
    assert bib_document.document_bag[0]["documentCode"] == "BIB"
    assert bib_document.document_bag[0]["downloadOptionBag"][0][
        "mimeTypeIdentifier"
    ] == ("PDF")


def test_reexam_download_search_fixture_uses_patentdata_key() -> None:
    response = PatentDownloadResponse.model_validate(
        _load_fixture("download_search_results.json")
    )

    assert len(response.patent_data) == 1
    assert "applicationMetaData" in response.patent_data[0]


def test_reexam_status_code_fixture_uses_status_code_bag_key() -> None:
    response = StatusCodeSearchResponse.model_validate(
        _load_fixture("status_codes_412.json")
    )

    assert response.count == 1
    assert response.status_code_bag[0]["applicationStatusCode"] == 412
