from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from uspto_client.library import DocumentSpec, Library, Release, Selection


def application(
    number: str, kind: str = "Re-Examination", patent: str = "12345678"
) -> dict:
    return {
        "applicationNumberText": number,
        "lastIngestionDateTime": "2026-09-01T00:00:00Z",
        "applicationMetaData": {
            "applicationTypeLabelName": kind,
            "patentNumber": patent,
        },
    }


def test_selection_import_idempotence_and_older_snapshot(tmp_path: Path) -> None:
    records = [application("90000001"), application("19000001", "Utility")]
    with Library(tmp_path / "data") as lib:
        selection = Selection(kinds=("reexam",))
        release = Release("PTFWPRD", "day.json", "2026-09-01", "2026-09-01", "delta")
        result = lib.ingest(records, release=release, selection=selection)
        assert (result.retained, result.skipped) == (1, 1)
        assert lib.ingest(
            records, release=release, selection=selection
        ).already_imported
        old = application("90000001", patent="99999999")
        old["lastIngestionDateTime"] = "2026-08-01T00:00:00Z"
        lib.ingest(
            [old],
            release=Release(
                "PTFWPRE", "old.json", "2001-01-01", "2026-08-01", "snapshot"
            ),
            selection=selection,
        )
        assert (
            lib.get_record("pfw", "90000001")["applicationMetaData"]["patentNumber"]
            == "12345678"
        )
        expanded = lib.ingest(
            records,
            release=release,
            selection=Selection(kinds=("reexam", "application")),
        )
        assert not expanded.already_imported
        assert lib.status()["records"] == 2


def test_failed_import_rolls_back_and_can_resume(tmp_path: Path) -> None:
    def broken():
        yield application("90000001")
        raise ValueError("broken archive")

    with Library(tmp_path) as lib:
        release = Release("PTFWPRD", "day", "2026-09-01", "2026-09-01", "delta")
        with pytest.raises(ValueError, match="broken archive"):
            lib.ingest(broken(), release=release)
        assert lib.status()["records"] == 0
        assert lib.ingest([application("90000001")], release=release).retained == 1


def test_documents_versions_text_and_relocation(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")
    root = tmp_path / "data"
    spec = DocumentSpec(
        "ptab",
        "doc-1",
        "IPR2026-00182",
        "ipr",
        "12345934",
        "2026-01-01",
        "Petition",
        paper_number="1",
    )
    with Library(root) as lib:
        first = lib.add_document(source, spec)
        assert first.name == "2026-01-01 (001) IPR2026-00182 ('934) Petition.pdf"
        assert lib.add_document(source, spec) == first
        lib.add_text(
            "ptab", "doc-1", ["A searchable phrase"], method="fixture", version="1"
        )
        assert lib.search_text('"searchable phrase"')[0]["page_number"] == 1
        source.write_bytes(b"%PDF-1.4\nchanged synthetic fixture\n%%EOF")
        second = lib.add_document(source, spec)
        assert first != second and first.exists()
        assert not lib.search_text('"searchable phrase"')  # current version only
    shutil.move(root, tmp_path / "relocated")
    with Library(tmp_path / "relocated") as lib:
        assert lib.verify()["missing"] == []
        assert lib.verify()["changed"] == []


def test_unknown_exhibit_and_no_invented_numbers() -> None:
    spec = DocumentSpec(
        "ptab",
        "d1",
        "IPR2026-00182",
        "ipr",
        description="Reference",
        exhibit_number="1005",
    )
    assert "Unclassified Exhibits" in str(spec.relative_path())
    assert spec.relative_path().name == "Ex 1005 Reference.pdf"
    with pytest.raises(ValueError):
        DocumentSpec("pfw", "d1", "../../outside", "reexam").relative_path()


def test_company_matches_record_first_detection_without_ownership_claim(
    tmp_path: Path,
) -> None:
    with Library(tmp_path) as lib:
        lib.watch_company("client", "Example Company", aliases=["Example Co."])
        lib.ingest(
            [application("90000001")],
            release=Release("api", "first", "2026-09-01", "2026-09-01", "targeted"),
        )
        assert lib.matches() == []
        lib.ingest_assignments(
            [
                {
                    "reel_frame": "1/2",
                    "recorded_date": "2020-01-01",
                    "conveyance": "ASSIGNMENT OF ASSIGNORS INTEREST",
                    "assignees": ["Example Co."],
                    "assignors": ["Inventor"],
                    "patents": ["12345678"],
                    "applications": [],
                }
            ],
            release=Release("PASDL", "assignment", "2026-09-02", "2026-09-02", "delta"),
        )
        matches = lib.match_companies()
        assert len(matches) == 1
        assert matches[0]["basis"] == "recorded_assignee"
        assert len(lib.match_companies()) == 0
        assert lib.company_patents("client")[0]["patent_number"] == "12345678"
        assert lib.patent_history("12345678")[0]["reel_frame"] == "1/2"


def test_pfw_json_zip_and_unknown_records(tmp_path: Path) -> None:
    import zipfile

    path = tmp_path / "input.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "records.json",
            json.dumps(
                {
                    "patentFileWrapperDataBag": [
                        application("90000001"),
                        {"applicationNumberText": "123"},
                    ]
                }
            ),
        )
    with Library(tmp_path / "data") as lib:
        result = lib.import_file(
            path,
            release=Release("PTFWPRD", path.name, "2026-09-01", "2026-09-01", "delta"),
        )
        assert result.retained == 1 and result.unrecognized == 1
        assert not result.complete
