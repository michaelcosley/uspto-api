from __future__ import annotations

from pathlib import Path

from uspto_client.filenames import (
    DocumentCodeMapper,
    build_document_filename,
    unique_path,
)


def _document() -> dict[str, object]:
    return {
        "applicationNumberText": "90015959",
        "officialDate": "2026-05-04T14:32:01.000-0400",
        "documentIdentifier": "ABC123",
        "documentCode": "RXOSUB.R.40",
        "documentCodeDescriptionText": "Receipt Original Ex Parte Reexamination",
    }


def test_default_filename_uses_document_identifier() -> None:
    filename = build_document_filename(_document()).filename

    assert filename == "ABC123.pdf"


def test_date_description_filename_uses_doc_code_mapping_when_available() -> None:
    mapper = DocumentCodeMapper({"RXOSUB.R.40": "Request for Reexam"})

    filename = build_document_filename(
        _document(),
        filename_format="date_description",
        mapper=mapper,
    ).filename

    assert filename == "2026-05-04 Request for Reexam.pdf"


def test_application_date_description_filename() -> None:
    mapper = DocumentCodeMapper({"RXOSUB.R.40": "Request for Reexam"})

    filename = build_document_filename(
        _document(),
        filename_format="application_date_description",
        mapper=mapper,
    ).filename

    assert filename == "90015959 2026-05-04 Request for Reexam.pdf"


def test_application_date_patent_description_filename() -> None:
    mapper = DocumentCodeMapper({"RXOSUB.R.40": "Request for Reexam"})

    filename = build_document_filename(
        _document(),
        filename_format="application_date_patent_description",
        patent_number="11,111,279",
        mapper=mapper,
    ).filename

    assert filename == "90015959 2026-05-04 ('279) Request for Reexam.pdf"


def test_custom_filename_template_can_reorder_parts() -> None:
    mapper = DocumentCodeMapper({"RXOSUB.R.40": "Request for Reexam"})

    filename = build_document_filename(
        _document(),
        filename_template="{short_desc} - {date} - {app_no}",
        mapper=mapper,
    ).filename

    assert filename == "Request for Reexam - 2026-05-04 - 90015959.pdf"


def test_unique_path_appends_counter_before_extension(tmp_path: Path) -> None:
    original = tmp_path / "2026-05-04 Request for Reexam.pdf"
    original.write_bytes(b"existing")
    second = tmp_path / "2026-05-04 Request for Reexam (2).pdf"
    second.write_bytes(b"existing")

    assert unique_path(original) == tmp_path / "2026-05-04 Request for Reexam (3).pdf"
