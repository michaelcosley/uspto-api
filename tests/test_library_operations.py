from __future__ import annotations

import io
from pathlib import Path

import httpx

from uspto_client import UsptoClient
from uspto_client.importers import assignment_records, json_records
from uspto_client.library import Library, Release, Selection


def test_padx_corrections_purges_and_security_interests(tmp_path: Path) -> None:
    xml = (
        b'<?xml version="1.0"?>\n'
        b"<!DOCTYPE us-patent-assignments [<!ELEMENT us-patent-assignments ANY>]>\n"
        b"<us-patent-assignments>\n"
        b"<patent-assignments>\n"
        b"<patent-assignment>\n"
        b"<assignment-record>\n"
        b"<reel-no>1</reel-no>\n"
        b"<frame-no>2</frame-no>\n"
        b"<last-update-date>\n"
        b"<date>20260901</date>\n"
        b"</last-update-date>\n"
        b"<recorded-date>\n"
        b"<date>20200101</date>\n"
        b"</recorded-date>\n"
        b"<purge-indicator>N</purge-indicator>\n"
        b"<conveyance-text>ASSIGNMENT OF ASSIGNORS INTEREST</conveyance-text>\n"
        b"</assignment-record>\n"
        b"<patent-assignees>\n"
        b"<patent-assignee>\n"
        b"<name>Example</name>\n"
        b"</patent-assignee>\n"
        b"</patent-assignees>\n"
        b"<patent-properties>\n"
        b"<patent-property>\n"
        b"<document-id>\n"
        b"<country>US</country>\n"
        b"<doc-number>12000001</doc-number>\n"
        b"<kind>X0</kind>\n"
        b"</document-id>\n"
        b"<document-id>\n"
        b"<country>US</country>\n"
        b"<doc-number>12345678</doc-number>\n"
        b"<kind>B2</kind>\n"
        b"</document-id>\n"
        b"</patent-property>\n"
        b"</patent-properties>\n"
        b"</patent-assignment>\n"
        b"</patent-assignments>\n"
        b"</us-patent-assignments>"
    )
    record = next(iter(assignment_records(io.BytesIO(xml))))
    assert record["patents"] == ["12345678"]
    assert record["applications"] == ["12000001"]
    with Library(tmp_path) as lib:
        release = Release("PASDL", "one", "2026-09-01", "2026-09-01", "delta")
        lib.ingest_assignments([record], release=release)
        assert lib.ownership_candidates("12345678")["candidates"] == ["Example"]
        security = {
            **record,
            "reel_frame": "3/4",
            "recorded_date": "2026-01-01",
            "assignees": ["Bank"],
            "conveyance": "SECURITY INTEREST",
        }
        lib.ingest_assignments(
            [security],
            release=Release("PASDL", "two", "2026-09-02", "2026-09-02", "delta"),
        )
        assert lib.ownership_candidates("12345678")["candidates"] == ["Example"]
        purge = {**record, "purged": True, "source_modified": "2026-09-03"}
        lib.ingest_assignments(
            [purge],
            release=Release("PASDL", "three", "2026-09-03", "2026-09-03", "delta"),
            selection=Selection(companies=("Unrelated",)),
        )
        assert lib.ownership_candidates("12345678")["candidates"] == []


def test_json_stream_accepts_individual_records_and_empty_bags() -> None:
    assert list(json_records(io.BytesIO(b'{"patentFileWrapperDataBag":[]}'))) == []
    assert list(
        json_records(
            io.BytesIO(b'{"applicationNumberText":"1"}\n{"applicationNumberText":"2"}')
        )
    ) == [{"applicationNumberText": "1"}, {"applicationNumberText": "2"}]


def test_collect_reexam_resolves_challenged_patent_from_continuity(
    tmp_path: Path,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("documents"):
            return httpx.Response(200, json={"documentBag": []})
        return httpx.Response(
            200,
            json={
                "patentFileWrapperDataBag": [
                    {
                        "applicationNumberText": "90000001",
                        "applicationMetaData": {"applicationTypeCategory": "REEXAM"},
                        "parentContinuityBag": [
                            {
                                "claimParentageTypeCode": "REX",
                                "parentPatentNumber": "12345678",
                            }
                        ],
                    }
                ]
            },
        )

    with (
        Library(tmp_path) as lib,
        UsptoClient(api_key="test", transport=httpx.MockTransport(handle)) as client,
    ):
        lib.collect(client, applications=["90000001"])
        assert lib.patent_for_record(lib.get_record("pfw", "90000001")) == "12345678"


def test_delta_coverage_detects_gap_and_filter_expansion(tmp_path: Path) -> None:
    with Library(tmp_path) as lib:
        selection = Selection()
        lib.ingest(
            [], release=Release("PTFWPRD", "one", "2026-09-01", "2026-09-01", "delta")
        )
        assert lib.coverage(
            "PTFWPRD", selection, date_from="2026-09-01", date_to="2026-09-02"
        )["missing_dates"] == ["2026-09-02"]
        assert lib.coverage(
            "PTFWPRD",
            Selection(all_records=True),
            date_from="2026-09-01",
            date_to="2026-09-01",
        )["missing_dates"] == ["2026-09-01"]
