from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import httpx
import pytest

from uspto_client import UsptoClient
from uspto_client.importers import assignment_records
from uspto_client.library import DocumentSpec, Library, Release, Selection
from uspto_client.library_cli import main


def test_bulk_discard_resume_and_changed_selection(tmp_path: Path) -> None:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "data.json",
            json.dumps(
                {
                    "patentFileWrapperDataBag": [
                        {
                            "applicationNumberText": "90000001",
                            "applicationMetaData": {
                                "applicationTypeCategory": "REEXAM"
                            },
                            "lastIngestionDateTime": "2026-09-01T00:00:00Z",
                        }
                    ]
                }
            ),
        )
    downloads = []

    def handle(request: httpx.Request) -> httpx.Response:
        if "/files/" in request.url.path:
            downloads.append(request)
            return httpx.Response(200, content=data.getvalue())
        return httpx.Response(
            200,
            json={
                "bulkDataProductBag": [
                    {
                        "productIdentifier": "PTFWPRD",
                        "productFileBag": {
                            "fileDataBag": [
                                {
                                    "fileName": "day.zip",
                                    "fileSize": len(data.getvalue()),
                                    "fileTypeText": "Data",
                                    "fileDataFromDate": "2026-09-01",
                                    "fileDataToDate": "2026-09-01",
                                    "fileReleaseDate": "2026-09-02",
                                }
                            ]
                        },
                    }
                ]
            },
        )

    with (
        Library(tmp_path) as lib,
        UsptoClient(api_key="test", transport=httpx.MockTransport(handle)) as client,
    ):
        kwargs = dict(
            product="PTFWPRD",
            date_from="2026-09-01",
            date_to="2026-09-01",
            selection=Selection(),
            max_download_bytes=100000,
        )
        assert not lib.sync_bulk(client, **kwargs)["executed"]
        assert downloads == []
        assert lib.sync_bulk(client, **kwargs, execute=True, retain_archives=False)[
            "complete"
        ]
        assert len(downloads) == 1
        assert not list((tmp_path / "sources").rglob("*.zip"))
        assert lib.sync_bulk(client, **kwargs, execute=True)["already_imported"] == [
            "day.zip"
        ]
        assert len(downloads) == 1
        kwargs["selection"] = Selection(all_records=True)
        assert lib.sync_bulk(client, **kwargs)["advertised_bytes"] > 0


def test_newer_sparse_projection_preserves_continuity(tmp_path: Path) -> None:
    original = {
        "applicationNumberText": "90000001",
        "applicationMetaData": {"applicationTypeCategory": "REEXAM"},
        "parentContinuityBag": [
            {"claimParentageTypeCode": "REX", "parentPatentNumber": "12345678"}
        ],
        "lastIngestionDateTime": "2026-09-01",
    }
    with Library(tmp_path) as lib:
        lib.ingest(
            [original],
            release=Release("api", "one", "2026-09-01", "2026-09-01", "targeted"),
        )
        sparse = {
            key: value
            for key, value in original.items()
            if key != "parentContinuityBag"
        }
        sparse["lastIngestionDateTime"] = "2026-09-02"
        lib.ingest(
            [sparse],
            release=Release("PTFWPRD", "two", "2026-09-02", "2026-09-02", "delta"),
        )
        assert lib.patent_for_record(lib.get_record("pfw", "90000001")) == "12345678"


def test_assignment_away_is_not_a_current_company_match(tmp_path: Path) -> None:
    with Library(tmp_path) as lib:
        lib.watch_company("company", "Example")
        base = {
            "reel_frame": "0001/0002",
            "recorded_date": "2020-01-01",
            "source_modified": "2026-09-01",
            "conveyance": "ASSIGNMENT OF ASSIGNORS INTEREST",
            "assignees": ["Example"],
            "patents": ["12345678"],
        }
        later = {
            **base,
            "reel_frame": "3/4",
            "recorded_date": "2021-01-01",
            "assignees": ["Other"],
        }
        lib.ingest_assignments(
            [base, later],
            release=Release("PASDL", "one", "2026-09-01", "2026-09-01", "delta"),
        )
        assert lib.patent_history("12345678")[0]["reel_frame"] == "1/2"
        assert lib.company_patents("company")[0]["status"] == "historical_or_non_title"
        assert lib.ownership_candidates("12345678")["candidates"] == ["Other"]


def test_backup_restore_and_newer_schema_refusal(tmp_path: Path) -> None:
    with Library(tmp_path / "one") as lib:
        lib.watch_company("a", "Example")
        lib.backup(tmp_path / "backup.sqlite3")
    with Library.restore_database(
        tmp_path / "backup.sqlite3", tmp_path / "restored"
    ) as restored:
        assert restored.store.rows("SELECT name FROM companies")[0]["name"] == "Example"
    with sqlite3.connect(tmp_path / "restored/databases/library.sqlite3") as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="newer"):
        Library(tmp_path / "restored")


def test_extractor_only_receives_scratch_copy(tmp_path: Path) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 original")
    with Library(tmp_path / "data") as lib:
        stored = lib.add_document(pdf, DocumentSpec("pfw", "one", "90000001", "reexam"))

        def extractor(path: Path):
            path.write_bytes(b"changed by extractor")
            return ["text"]

        lib.extract_text("pfw", "one", extractor, method="test", version="1")
        assert stored.read_bytes() == b"%PDF-1.4 original"


def test_xml_external_entities_are_rejected() -> None:
    xml = b'<!DOCTYPE us-patent-assignments [<!ENTITY x SYSTEM "file:///secret">]><us-patent-assignments>&x;</us-patent-assignments>'
    with pytest.raises(Exception, match="EntitiesForbidden"):
        list(assignment_records(io.BytesIO(xml)))


def test_cli_initialization_and_search(tmp_path: Path, capsys) -> None:
    assert main(["--root", str(tmp_path), "init"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"] == 0
    assert main(["--root", str(tmp_path), "watch-company", "client", "Example"]) == 0
    assert main(["--root", str(tmp_path), "company-patents", "client"]) == 0


def test_bounded_discovery_and_repeated_detection(tmp_path: Path) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "count": 1,
                "patentTrialProceedingDataBag": [
                    {
                        "trialNumber": "IPR2026-00001",
                        "patentOwnerData": {
                            "patentOwnerName": "Example",
                            "patentNumber": "12345678",
                        },
                        "lastModifiedDateTime": "2026-09-01T00:00:00Z",
                    }
                ],
            },
        )

    with (
        Library(tmp_path) as lib,
        UsptoClient(api_key="test", transport=httpx.MockTransport(handle)) as client,
    ):
        lib.watch_company("company", "Example")
        result = lib.discover(
            client, date_from="2026-09-01", date_to="2026-09-02", kinds=("ipr",)
        )
        assert result["complete"] and len(result["new_matches"]) == 1
        assert (
            lib.discover(
                client, date_from="2026-09-01", date_to="2026-09-02", kinds=("ipr",)
            )["new_matches"]
            == []
        )


def test_application_assignment_links_to_later_patent(tmp_path: Path) -> None:
    with Library(tmp_path) as lib:
        lib.watch_company("example", "Example Inc.")
        lib.ingest_assignments(
            [
                {
                    "reel_frame": "1/1",
                    "applications": ["12345678"],
                    "assignees": ["Example Inc."],
                    "source_modified": "2020-01-01",
                    "recorded_date": "2020-01-01",
                    "conveyance": "ASSIGNMENT OF ASSIGNORS INTEREST",
                }
            ],
            release=Release("PASYR", "old.xml", "2020-01-01", "2020-01-01", "snapshot"),
        )
        assert lib.company_patents("example") == []
        lib.ingest(
            [
                {
                    "applicationNumberText": "90000001",
                    "applicationMetaData": {"applicationTypeCategory": "REEXAM"},
                    "lastIngestionDateTime": "2026-09-01",
                    "parentContinuityBag": [
                        {
                            "claimParentageTypeCode": "REX",
                            "parentApplicationNumberText": "12345678",
                            "parentPatentNumber": "9876543",
                        }
                    ],
                }
            ],
            release=Release("PTFWPRD", "day.json", "2026-09-01", "2026-09-01", "delta"),
        )
        assert lib.patent_history("9876543")[0]["reel_frame"] == "1/1"
        assert lib.company_patents("example")[0]["patent_number"] == "9876543"
        assert len(lib.match_companies()) == 1
        assert lib.patent_history("90000001") == []


def test_partial_assignment_groups_keep_previously_seen_patents(tmp_path: Path) -> None:
    with Library(tmp_path) as lib:
        for index, patent in enumerate(("9876543", "9876544"), start=1):
            lib.ingest_assignments(
                [
                    {
                        "reel_frame": "001/001",
                        "patents": [patent],
                        "source_modified": f"2026-09-0{index}",
                        "property_scope": "search_result_group; verify coverage",
                    }
                ],
                release=Release(
                    "assignment-center",
                    str(index),
                    "2026-09-01",
                    "2026-09-02",
                    "targeted",
                ),
            )
        assert len(lib.patent_history("9876543")) == 1
        assert len(lib.patent_history("9876544")) == 1
