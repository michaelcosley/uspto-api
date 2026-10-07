import hashlib
from dataclasses import replace

import pytest

from uspto_client.library import DocumentSpec, Library, Selection
from uspto_client.library_history import version_id

STAMP = "2020-01-02T03:04:05+00:00"


def test_same_official_document_keeps_both_proceedings(tmp_path):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 original")
    with Library(tmp_path / "library") as lib:
        first = DocumentSpec("ptab", "shared", "IPR2020-00001", "ipr")
        path = lib.add_document(pdf, first)
        assert lib.add_document(pdf, replace(first, proceeding="IPR2020-00002")) == path
        assert len(lib.history.attachments()) == 2
        assert len(lib.write_index("IPR2020-00002")) == 1
        assert lib.verify()["missing"] == []


def test_historical_files_methods_times_and_repeat_are_preserved(tmp_path):
    original = tmp_path / "Original.pdf"
    derivative = tmp_path / "OCR.pdf"
    original.write_bytes(b"%PDF-1.4 original")
    derivative.write_bytes(b"%PDF-1.4 derivative")
    original_bytes = original.read_bytes()
    spec = DocumentSpec("pfw", "document", "90000001", "reexam")
    with Library(tmp_path / "projection") as lib:

        def ingest():
            mapped = lib.history.register_document(
                original,
                spec,
                created_at=STAMP,
                observed_at=STAMP,
                provenance={"legacy_id": "v1"},
                make_current=True,
            )
            lib.history.attach(
                replace(spec, proceeding="90000002"),
                mapped["sha256"],
                role="exhibit",
                observed_at=STAMP,
                provenance={"legacy_id": "association2"},
            )
            runs = [
                lib.history.add_text(
                    "pfw",
                    "document",
                    ["identical text"],
                    pdf_hash=mapped["sha256"],
                    method=method,
                    version="1",
                    created_at=STAMP,
                    provenance={"legacy_run": method},
                    make_current=method == "ocr",
                    selected_at=STAMP,
                )
                for method in ("native", "ocr")
            ]
            edges = [
                lib.history.add_derivative(
                    "pfw",
                    "document",
                    derivative,
                    original_hash=mapped["sha256"],
                    method=method,
                    version="1",
                    created_at=STAMP,
                    provenance={"validated": True},
                )
                for method in ("ocr-a", "ocr-b")
            ]
            return mapped, runs, edges

        first = ingest()
        before = lib.history.export_manifest()
        assert ingest() == first
        assert lib.history.export_manifest() == before
        assert len(set(first[1])) == 2 and len(set(first[2])) == 2
        assert before["tables"]["active_text"][0]["run_id"] == first[1][1]
        assert first[0]["version_id"] == version_id(
            "pfw", "document", hashlib.sha256(original_bytes).hexdigest()
        )
        assert before["tables"]["document_versions"][0]["created_at"] == STAMP
        assert before["tables"]["document_versions"][0]["path"] == str(original)
        assert lib.verify() == {"integrity": "ok", "missing": [], "changed": []}
        assert len(lib.search_text('"identical text"')) == 2
        other = lib.history.register_document(
            original,
            replace(spec, document_id="distinct-source-record"),
            created_at=STAMP,
            observed_at=STAMP,
            provenance={},
        )
        assert other["version_id"] != first[0]["version_id"]
    assert original.read_bytes() == original_bytes
    assert list((tmp_path / "projection").rglob("*.pdf")) == []


def test_source_import_retains_conflicts_without_claiming_coverage(tmp_path):
    raw = tmp_path / "response.json"
    raw.write_text('{"record":"one"}')
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    with Library(tmp_path / "library") as lib:
        args = dict(
            source="assignment",
            external_id="fetch1",
            endpoint="property",
            request={"application": "12345678"},
            observed_at=STAMP,
            source_at="",
            raw_path=raw,
            raw_sha256=digest,
        )
        first = lib.history.import_source_snapshot(
            payload={"status": "pending"}, **args
        )
        second = lib.history.import_source_snapshot(
            payload={"status": "conflict"}, **args
        )
        assert first != second
        assert len(lib.history.export_manifest()["tables"]["source_snapshots"]) == 2
        assert not lib.coverage(
            "PASDL",
            Selection(all_records=True),
            date_from="2020-01-02",
            date_to="2020-01-02",
        )["complete"]
        raw.write_text("changed")
        with pytest.raises(ValueError, match="changed"):
            lib.history.import_source_snapshot(payload={}, **args)


def test_upgrade_keeps_v1_projection_and_refuses_unknown_external_paths(tmp_path):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 original")
    root = tmp_path / "library"
    with Library(root) as lib:
        lib.add_document(pdf, DocumentSpec("pfw", "doc", "90000001", "reexam"))
        expected = lib.store.rows("SELECT * FROM document_versions")
        with lib.store.transaction():
            lib.store.db.execute("DELETE FROM document_attachments")
            lib.store.db.execute("DELETE FROM history_events")
            lib.store.db.execute("DELETE FROM version_ids")
            lib.store.db.execute("PRAGMA user_version=1")
    with Library(root) as lib:
        assert lib.store.rows("SELECT * FROM document_versions") == expected
        assert len(lib.history.attachments()) == 1
        with pytest.raises(ValueError, match="Unregistered"):
            lib.history.resolve_path(str(pdf))


def test_native_derivative_api_keeps_multiple_methods(tmp_path):
    original = tmp_path / "original.pdf"
    derivative = tmp_path / "derived.pdf"
    original.write_bytes(b"%PDF-1.4 original")
    derivative.write_bytes(b"%PDF-1.4 derivative")
    with Library(tmp_path / "library") as library:
        library.add_document(original, DocumentSpec("pfw", "doc", "90000001", "reexam"))
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        for method in ("ocr-a", "ocr-b"):
            library.add_derivative(
                "pfw",
                "doc",
                derivative,
                original_hash=digest,
                method=method,
                version="1",
            )
        rows = library.history.export_manifest()["tables"]["derivative_events"]
        assert {row["method"] for row in rows} == {"ocr-a", "ocr-b"}
        assert library.verify()["changed"] == []
        before = library.history.export_manifest()
        with pytest.raises(ValueError, match="changed before"):
            library.history.register_document(
                original,
                DocumentSpec("pfw", "new", "90000002", "reexam"),
                created_at=STAMP,
                observed_at=STAMP,
                provenance={},
                expected_sha256="wrong",
            )
        assert library.history.export_manifest() == before
