"""SQLite backend. Domain operations are isolated here for future backends."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from uspto_client.library_models import Record, canonical, fingerprint, utc_now

SCHEMA_VERSION = 1


class RecordStorage(Protocol):
    """Minimal backend contract for source observations and normalized records."""

    def observe(
        self,
        source: str,
        external_id: str,
        kind: str,
        payload: Record,
        source_at: str,
        release_id: str,
    ) -> None: ...
    def get_record(self, source: str, external_id: str) -> Record | None: ...
    def close(self) -> None: ...


class SQLiteStorage:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=30000")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            self.db.close()
            raise ValueError("Database was created by a newer uspto-client")
        if (
            version == 0
            and self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchone()
        ):
            self.db.close()
            raise ValueError("Refusing to adopt an unrelated database")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""

            CREATE TABLE IF NOT EXISTS records(source TEXT,id TEXT,kind
            TEXT,payload TEXT,source_at TEXT,first_seen TEXT,last_seen
            TEXT,PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS observations(source TEXT,id TEXT,hash
            TEXT,release_id TEXT,payload TEXT,source_at TEXT,observed_at
            TEXT,PRIMARY KEY(source,id,hash,release_id));
            CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,product
            TEXT,filename TEXT,selection TEXT,details TEXT,result
            TEXT,completed_at TEXT);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,status
            TEXT,started_at TEXT,finished_at TEXT,error TEXT);
            CREATE TABLE IF NOT EXISTS bulk_files(product TEXT,filename
            TEXT,revision TEXT,selection TEXT,sha256 TEXT,bytes INTEGER,path
            TEXT,PRIMARY KEY(product,filename,revision,selection));
            CREATE TABLE IF NOT EXISTS source_conflicts(source TEXT,id
            TEXT,source_at TEXT,hash TEXT,release_id TEXT,PRIMARY
            KEY(source,id,source_at,hash));
            CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,name TEXT);
            CREATE TABLE IF NOT EXISTS aliases(company_id TEXT,alias TEXT,PRIMARY
            KEY(company_id,alias),FOREIGN KEY(company_id) REFERENCES
            companies(id));
            CREATE TABLE IF NOT EXISTS assignments(reel_frame TEXT PRIMARY
            KEY,payload TEXT,source_at TEXT,first_seen TEXT,last_seen TEXT);
            CREATE TABLE IF NOT EXISTS assignment_properties(reel_frame TEXT,kind
            TEXT,number TEXT,PRIMARY KEY(reel_frame,kind,number),FOREIGN
            KEY(reel_frame) REFERENCES assignments(reel_frame));
            CREATE INDEX IF NOT EXISTS assignment_number ON
            assignment_properties(kind,number);
            CREATE TABLE IF NOT EXISTS asset_links(application TEXT,patent TEXT,
            source TEXT,id TEXT,PRIMARY KEY(application,patent,source,id));
            CREATE INDEX IF NOT EXISTS asset_link_patent ON asset_links(patent);
            CREATE VIEW IF NOT EXISTS assignment_patents AS
            SELECT reel_frame,number AS patent FROM assignment_properties
            WHERE kind='patents' UNION
            SELECT p.reel_frame,l.patent FROM assignment_properties p
            JOIN asset_links l ON p.number=l.application
            WHERE p.kind='applications';
            CREATE TABLE IF NOT EXISTS assignment_parties(reel_frame TEXT,role
            TEXT,name TEXT,name_key TEXT,PRIMARY KEY(reel_frame,role,name),FOREIGN
            KEY(reel_frame) REFERENCES assignments(reel_frame));
            CREATE INDEX IF NOT EXISTS assignment_party_name ON
            assignment_parties(name_key,role);
            CREATE TABLE IF NOT EXISTS matches(company_id TEXT,source
            TEXT,proceeding TEXT,basis TEXT,evidence TEXT,first_detected
            TEXT,proceeding_first_seen TEXT,PRIMARY
            KEY(company_id,source,proceeding));
            CREATE TABLE IF NOT EXISTS documents(source TEXT,id TEXT,current_hash
            TEXT,spec TEXT,PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS document_versions(source TEXT,id TEXT,hash
            TEXT,path TEXT,created_at TEXT,PRIMARY KEY(source,id,hash),FOREIGN
            KEY(source,id) REFERENCES documents(source,id));
            CREATE TABLE IF NOT EXISTS derivatives(source TEXT,id
            TEXT,original_hash TEXT,hash TEXT,path TEXT,method TEXT,version
            TEXT,PRIMARY KEY(source,id,original_hash,hash));
            CREATE TABLE IF NOT EXISTS naming_overrides(source TEXT,id
            TEXT,description TEXT,reason TEXT,updated_at TEXT,PRIMARY
            KEY(source,id));
            CREATE TABLE IF NOT EXISTS text_runs(id TEXT PRIMARY KEY,source
            TEXT,document_id TEXT,pdf_hash TEXT,method TEXT,version
            TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY,run_id
            TEXT,page_number INTEGER,text TEXT,FOREIGN KEY(run_id) REFERENCES
            text_runs(id),UNIQUE(run_id,page_number));
            CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING
            fts5(text,content='pages',content_rowid='id');
            CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid,text) VALUES(new.id,new.text); END;
            CREATE TABLE IF NOT EXISTS annotations(id TEXT PRIMARY KEY,source
            TEXT,document_id TEXT,pdf_hash TEXT,page_number INTEGER,field
            TEXT,value TEXT,method TEXT,version TEXT,review_status TEXT,created_at
            TEXT);
            PRAGMA user_version=1;

        """)
        self.db.commit()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def observe(
        self,
        source: str,
        external_id: str,
        kind: str,
        payload: Record,
        source_at: str,
        release_id: str,
    ) -> None:
        now = utc_now()
        encoded = canonical(payload)
        previous = self.db.execute(
            "SELECT source_at,payload FROM records WHERE source=? AND id=?",
            (source, external_id),
        ).fetchone()
        if previous:
            current_payload = json.loads(previous["payload"])
            payload_view = merge_records(current_payload, payload)
        else:
            payload_view = payload
        if (
            previous
            and previous["source_at"] == source_at
            and previous["payload"] != canonical(payload_view)
        ):
            self.db.execute(
                "INSERT OR IGNORE INTO source_conflicts VALUES(?,?,?,?,?)",
                (source, external_id, source_at, fingerprint(payload), release_id),
            )
        self.db.execute(
            "INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)",
            (
                source,
                external_id,
                fingerprint(payload),
                release_id,
                encoded,
                source_at,
                now,
            ),
        )
        self.db.execute(
            """
                INSERT INTO records VALUES(?,?,?,?,?,?,?) ON CONFLICT(source,id) DO
                UPDATE SET
                payload=CASE WHEN excluded.source_at > records.source_at THEN
                excluded.payload ELSE records.payload END,
                kind=CASE WHEN excluded.source_at > records.source_at THEN
                excluded.kind ELSE records.kind END,
                source_at=max(records.source_at,excluded.source_at),last_seen=excluded.last_seen
            """,
            (source, external_id, kind, canonical(payload_view), source_at, now, now),
        )

    def get_record(self, source: str, external_id: str) -> Record | None:
        row = self.db.execute(
            "SELECT payload FROM records WHERE source=? AND id=?", (source, external_id)
        ).fetchone()
        result: Record | None = json.loads(row[0]) if row else None
        return result

    def rows(self, sql: str, parameters: tuple[object, ...] = ()) -> list[Record]:
        return [dict(row) for row in self.db.execute(sql, parameters)]

    def backup(self, destination: Path) -> None:
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(destination) as backup:
            self.db.backup(backup)

    def close(self) -> None:
        self.db.close()


def merge_records(current: Record, incoming: Record) -> Record:
    """A newer sparse projection updates supplied fields, preserving absent fields."""
    result = dict(current)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_records(result[key], value)
        else:
            result[key] = value
    return result
