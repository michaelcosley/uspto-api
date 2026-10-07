"""Historical evidence imports that retain existing files and every attachment.

All paths are explicitly registered and hash-verified. Importing makes no HTTP
calls, copies no PDFs, performs no OCR, and never assigns substantive reviews.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from uspto_client.library_models import DocumentSpec, Record, canonical, fingerprint
from uspto_client.storage import SQLiteStorage
from uspto_client.streaming import file_sha256


def version_id(source: str, document_id: str, digest: str) -> str:
    return fingerprint(["document-version-v1", source, document_id, digest])


def _time(value: str) -> None:
    if value:
        datetime.fromisoformat(value.replace("Z", "+00:00"))


class HistoricalCatalog:
    def __init__(self, store: SQLiteStorage, root: Path) -> None:
        self.store = store
        self.root = root

    def _event(self, kind: str, entity_id: str, payload: Record) -> str:
        event = fingerprint([kind, entity_id, payload])
        self.store.db.execute(
            "INSERT OR IGNORE INTO history_events VALUES(?,?,?,?)",
            (event, kind, entity_id, canonical(payload)),
        )
        return event

    def _version(self, source: str, document: str, digest: str) -> str:
        key = version_id(source, document, digest)
        self.store.db.execute(
            "INSERT OR IGNORE INTO version_ids VALUES(?,?,?,?)",
            (key, source, document, digest),
        )
        return key

    def _attach(
        self,
        spec: DocumentSpec,
        digest: str,
        role: str,
        observed_at: str,
        provenance: Record,
    ) -> str:
        key = fingerprint(
            [
                "attachment-v1",
                spec.source,
                spec.document_id,
                spec.proceeding,
                digest,
                role,
            ]
        )
        self.store.db.execute(
            "INSERT OR IGNORE INTO document_attachments VALUES(?,?,?,?,?,?,?,?)",
            (
                key,
                spec.source,
                spec.document_id,
                spec.proceeding,
                digest,
                role,
                canonical(asdict(spec)),
                observed_at,
            ),
        )
        self._event(
            "attachment",
            key,
            {
                "spec": asdict(spec),
                "observed_at": observed_at,
                "provenance": provenance,
            },
        )
        return key

    def backfill(self) -> None:
        """Preserve known v1 relationships; never invent formerly lost attachments."""
        with self.store.transaction():
            pending = self.store.rows(
                "SELECT v.* FROM document_versions v WHERE NOT EXISTS "
                "(SELECT 1 FROM version_ids i WHERE i.source=v.source "
                "AND i.id=v.id AND i.hash=v.hash)"
            )
            legacy = {(row["source"], row["id"]) for row in pending}
            for row in pending:
                self._version(row["source"], row["id"], row["hash"])
            for row in self.store.rows(
                "SELECT d.source,d.id,d.spec,v.hash,v.created_at FROM documents d "
                "JOIN document_versions v ON d.source=v.source AND d.id=v.id "
                "AND d.current_hash=v.hash"
            ):
                if (row["source"], row["id"]) in legacy:
                    self._attach(
                        DocumentSpec(**json.loads(row["spec"])),
                        row["hash"],
                        "",
                        row["created_at"],
                        {"origin": "legacy-library-projection"},
                    )

    def register_document(
        self,
        path: str | Path,
        spec: DocumentSpec,
        *,
        created_at: str,
        observed_at: str,
        provenance: Record,
        make_current: bool = False,
        role: str = "",
        expected_sha256: str | None = None,
    ) -> Record:
        """Register a retained PDF; change current selection only explicitly."""
        _time(created_at)
        _time(observed_at)
        spec.relative_path()  # Validate identifiers without creating paths.
        path = Path(path).resolve()
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("Not a PDF file")
        digest = file_sha256(path)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Retained PDF changed before registration")
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO documents VALUES(?,?,?,?)",
                (spec.source, spec.document_id, digest, canonical(asdict(spec))),
            )
            if make_current:
                self.store.db.execute(
                    "UPDATE documents SET current_hash=?,spec=? WHERE "
                    "source=? AND id=?",
                    (digest, canonical(asdict(spec)), spec.source, spec.document_id),
                )
            self.store.db.execute(
                "INSERT OR IGNORE INTO document_versions VALUES(?,?,?,?,?)",
                (spec.source, spec.document_id, digest, str(path), created_at),
            )
            key = self._version(spec.source, spec.document_id, digest)
            self.store.db.execute(
                "INSERT OR IGNORE INTO retained_locations VALUES(?,?,?,?)",
                (key, str(path), observed_at, canonical(provenance)),
            )
            attachment = self._attach(spec, digest, role, observed_at, provenance)
            event = self._event(
                "document-version",
                key,
                {
                    "path": str(path),
                    "sha256": digest,
                    "created_at": created_at,
                    "observed_at": observed_at,
                    "provenance": provenance,
                },
            )
        return {
            "version_id": key,
            "attachment_id": attachment,
            "event_id": event,
            "sha256": digest,
            "path": str(path),
        }

    def attach(
        self,
        spec: DocumentSpec,
        digest: str,
        *,
        role: str = "",
        observed_at: str,
        provenance: Record,
    ) -> str:
        _time(observed_at)
        if not self.store.rows(
            "SELECT 1 FROM document_versions WHERE source=? AND id=? AND hash=?",
            (spec.source, spec.document_id, digest),
        ):
            raise ValueError("Attachment requires a known document version")
        with self.store.transaction():
            return self._attach(spec, digest, role, observed_at, provenance)

    def resolve_path(self, stored_path: str) -> Path:
        path = Path(stored_path)
        if path.is_absolute():
            if not self.store.rows(
                (
                    "SELECT 1 FROM retained_locations WHERE path=? UNION SELECT 1 FROM "
                    "derivative_events WHERE path=? UNION SELECT 1 FROM "
                    "source_snapshots WHERE raw_path=?"
                ),
                (str(path), str(path), str(path)),
            ):
                raise ValueError("Unregistered external evidence path")
            return path
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("Path escapes library root")
        return resolved

    def add_text(
        self,
        source: str,
        document_id: str,
        pages: Iterable[str],
        *,
        pdf_hash: str,
        method: str,
        version: str,
        created_at: str,
        provenance: Record,
        make_current: bool = False,
        selected_at: str = "",
    ) -> str:
        _time(created_at)
        _time(selected_at)
        if not self.store.rows(
            "SELECT 1 FROM document_versions WHERE source=? AND id=? AND hash=?",
            (source, document_id, pdf_hash),
        ):
            raise ValueError("Text requires a known PDF version")
        texts = list(pages)
        run = fingerprint([source, document_id, pdf_hash, method, version, texts])
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO text_runs VALUES(?,?,?,?,?,?,?)",
                (run, source, document_id, pdf_hash, method, version, created_at),
            )
            for number, text in enumerate(texts, 1):
                self.store.db.execute(
                    "INSERT OR IGNORE INTO "
                    "pages(run_id,page_number,text) VALUES(?,?,?)",
                    (run, number, text),
                )
            self._event(
                "text-run", run, {"created_at": created_at, "provenance": provenance}
            )
            if make_current:
                self.store.db.execute(
                    "INSERT INTO active_text VALUES(?,?,?,?) ON CONFLICT(source,id) "
                    "DO UPDATE SET run_id=excluded.run_id,"
                    "selection_provenance=excluded.selection_provenance",
                    (
                        source,
                        document_id,
                        run,
                        canonical(
                            {"selected_at": selected_at, "provenance": provenance}
                        ),
                    ),
                )
                self._event(
                    "active-text",
                    run,
                    {"selected_at": selected_at, "provenance": provenance},
                )
        return run

    def add_derivative(
        self,
        source: str,
        document_id: str,
        path: str | Path,
        *,
        original_hash: str,
        method: str,
        version: str,
        created_at: str,
        provenance: Record,
        expected_sha256: str | None = None,
    ) -> str:
        _time(created_at)
        if not self.store.rows(
            "SELECT 1 FROM document_versions WHERE source=? AND id=? AND hash=?",
            (source, document_id, original_hash),
        ):
            raise ValueError("Derivative requires a known original version")
        path = Path(path).resolve()
        digest = file_sha256(path)
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Retained derivative changed before registration")
        key = fingerprint(
            [
                source,
                document_id,
                original_hash,
                digest,
                method,
                version,
                created_at,
                provenance,
            ]
        )
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO derivative_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    source,
                    document_id,
                    original_hash,
                    digest,
                    str(path),
                    method,
                    version,
                    created_at,
                    canonical(provenance),
                ),
            )
        return key

    def import_source_snapshot(
        self,
        *,
        source: str,
        external_id: str,
        endpoint: str,
        request: Record,
        payload: Record,
        observed_at: str,
        source_at: str,
        raw_path: str | Path,
        raw_sha256: str,
        provenance: Record | None = None,
    ) -> str:
        """Retain source identity and times without declaring coverage complete."""
        _time(observed_at)
        _time(source_at)
        path = Path(raw_path).resolve()
        if file_sha256(path) != raw_sha256:
            raise ValueError("Raw source file changed")
        value = {
            "source": source,
            "external_id": external_id,
            "endpoint": endpoint,
            "request": request,
            "payload": payload,
            "observed_at": observed_at,
            "source_at": source_at,
            "raw_path": str(path),
            "raw_sha256": raw_sha256,
            "provenance": provenance or {},
        }
        key = fingerprint(value)
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO source_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    source,
                    external_id,
                    endpoint,
                    canonical(request),
                    canonical(payload),
                    observed_at,
                    source_at,
                    str(path),
                    raw_sha256,
                ),
            )
            self._event("source-snapshot", key, {"provenance": provenance or {}})
        return key

    def attachments(
        self,
        *,
        source: str | None = None,
        document_id: str | None = None,
        proceeding: str | None = None,
    ) -> list[Record]:
        predicates, parameters = [], []
        for column, value in (
            ("source", source),
            ("id", document_id),
            ("proceeding", proceeding),
        ):
            if value is not None:
                predicates.append(column + "=?")
                parameters.append(value)
        return self.store.rows(
            "SELECT * FROM document_attachments"
            + (" WHERE " + " AND ".join(predicates) if predicates else "")
            + " ORDER BY proceeding,source,id,observed_at,hash",
            tuple(parameters),
        )

    def export_manifest(self) -> Record:
        """Export historical evidence for import reconciliation."""
        tables = (
            "documents",
            "document_versions",
            "version_ids",
            "retained_locations",
            "document_attachments",
            "history_events",
            "derivative_events",
            "text_runs",
            "active_text",
            "pages",
            "source_snapshots",
        )
        return {
            "schema_version": 1,
            "tables": {
                table: self.store.rows("SELECT * FROM " + table) for table in tables
            },
        }
