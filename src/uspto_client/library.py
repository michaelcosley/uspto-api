"""Opt-in portable data library. Opening it never contacts USPTO."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from uspto_client.assignment import AssignmentCenterClient
from uspto_client.client import UsptoClient
from uspto_client.importers import read_records
from uspto_client.library_models import (
    DocumentSpec,
    ImportResult,
    Record,
    Release,
    Selection,
    canonical,
    company_key,
    fingerprint,
    identifier,
    record_kind,
    utc_now,
)
from uspto_client.storage import SQLiteStorage
from uspto_client.streaming import file_sha256

__all__ = ["DocumentSpec", "ImportResult", "Library", "Release", "Selection"]


def _source_time(value: str) -> str:
    if not value:
        return ""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed.replace(tzinfo=UTC).isoformat()
        if parsed.tzinfo is None
        else parsed.astimezone(UTC).isoformat()
    )


class Library:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root or os.environ.get("USPTO_DATA_ROOT", "data"))
            .expanduser()
            .resolve()
        )
        self.store = SQLiteStorage(self.root / "databases" / "library.sqlite3")
        from uspto_client.library_history import HistoricalCatalog

        self.history = HistoricalCatalog(self.store, self.root)
        self.history.backfill()
        for directory in (
            "config",
            "sources/bulk",
            "derivatives",
            "runs",
            "exports",
            "backups",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        config = self.root / "config" / "library.json"
        if not config.exists():
            config.write_text(
                canonical(
                    {
                        "format_version": 1,
                        "database": "databases/library.sqlite3",
                        "layout": "readable-v1",
                    }
                ),
                encoding="utf-8",
            )

    def __enter__(self) -> Library:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def collect(
        self,
        client: UsptoClient,
        *,
        applications: Iterable[str] = (),
        trials: Iterable[str] = (),
        download_ids: Iterable[str] = (),
    ) -> Record:
        from uspto_client.library_operations import collect

        return collect(
            self,
            client,
            applications=applications,
            trials=trials,
            download_ids=download_ids,
        )

    def collect_assignments(
        self, client: AssignmentCenterClient, *, company_id: str, max_pages: int = 100
    ) -> Record:
        from uspto_client.library_operations import collect_assignments

        return collect_assignments(
            self, client, company_id=company_id, max_pages=max_pages
        )

    def sync_bulk(
        self,
        client: UsptoClient,
        *,
        product: str,
        date_from: str,
        date_to: str,
        selection: Selection,
        max_download_bytes: int,
        execute: bool = False,
        retain_archives: bool = True,
    ) -> Record:
        from uspto_client.library_operations import sync_bulk

        return sync_bulk(
            self,
            client,
            product=product,
            date_from=date_from,
            date_to=date_to,
            selection=selection,
            max_download_bytes=max_download_bytes,
            execute=execute,
            retain_archives=retain_archives,
        )

    def get_record(self, source: str, external_id: str) -> Record | None:
        return self.store.get_record(source, external_id)

    def _ingest(
        self,
        records: Iterable[Record],
        release: Release,
        selection: Selection,
        *,
        assignments: bool = False,
        cancelled: Callable[[], bool] | None = None,
    ) -> ImportResult:
        release_id = fingerprint(
            {
                "release": asdict(release),
                "selection": selection.fingerprint,
                "parser": 1,
            }
        )
        previous = self.store.rows(
            "SELECT result FROM releases WHERE id=?", (release_id,)
        )
        if previous:
            return ImportResult(
                **{**json.loads(previous[0]["result"]), "already_imported": True}
            )
        result = ImportResult()
        run_id = uuid.uuid4().hex
        self.store.db.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?)", (run_id, "running", utc_now(), "", "")
        )
        self.store.db.commit()
        try:
            with self.store.transaction():
                for payload in records:
                    if cancelled and cancelled():
                        raise InterruptedError("Import cancelled")
                    if assignments:
                        payload = dict(payload)
                        external_id = str(payload.get("reel_frame", ""))
                        valid = len(external_id.split("/")) == 2 and all(
                            part.isdigit() for part in external_id.split("/")
                        )
                        if not valid:
                            result.unrecognized += 1
                            continue
                        external_id = "/".join(
                            str(int(part)) for part in external_id.split("/")
                        )
                        payload["reel_frame"] = external_id
                        if payload.get("property_scope", "").startswith(
                            "search_result_group"
                        ):
                            # A search page is a partial property projection. A later
                            # group for the same reel/frame must not erase other assets.
                            prior = self.store.get_record("assignments", external_id)
                            if prior and not prior.get("purged"):
                                for field in (
                                    "patents",
                                    "applications",
                                    "publications",
                                    "property_links",
                                ):
                                    combined = [
                                        *prior.get(field, []),
                                        *payload.get(field, []),
                                    ]
                                    payload[field] = list(
                                        {
                                            canonical(value): value
                                            for value in combined
                                        }.values()
                                    )
                        # Apply corrections/purges for already retained transactions
                        # even when they no longer match the filter.
                        known = bool(
                            self.store.rows(
                                "SELECT 1 FROM assignments WHERE reel_frame=?",
                                (external_id,),
                            )
                        )
                        accepted = known or selection.accepts_assignment(payload)
                        source, kind = "assignments", "assignment"
                        modified = str(
                            payload.get("source_modified") or release.source_as_of or ""
                        )
                    else:
                        source = "ptab" if payload.get("trialNumber") else "pfw"
                        kind = record_kind(payload)
                        external_id = str(
                            payload.get("trialNumber")
                            or payload.get("applicationNumberText")
                            or ""
                        )
                        if not external_id or kind == "unknown":
                            result.unrecognized += 1
                            if not external_id or not selection.accepts(payload):
                                continue
                        accepted = selection.accepts(payload)
                        modified = str(
                            payload.get("lastIngestionDateTime")
                            or payload.get("lastModifiedDateTime")
                            or release.source_as_of
                            or ""
                        )
                    if not accepted:
                        result.skipped += 1
                        continue
                    source_at = _source_time(modified)
                    self.store.observe(
                        source, external_id, kind, payload, source_at, release_id
                    )
                    if assignments:
                        self._save_assignment(payload, source_at)
                    current = self.store.get_record(source, external_id)
                    if current:
                        self._save_asset_links(source, external_id, current)
                    result.retained += 1
                    if payload.get("unrecognized_properties"):
                        result.unrecognized += 1
                result.complete = result.unrecognized == 0
                if self.store.rows(
                    "SELECT 1 FROM source_conflicts WHERE release_id=? LIMIT 1",
                    (release_id,),
                ):
                    result.complete = False
                self.store.db.execute(
                    "INSERT INTO releases VALUES(?,?,?,?,?,?,?)",
                    (
                        release_id,
                        release.product,
                        release.file_name,
                        selection.fingerprint,
                        canonical(asdict(release)),
                        canonical(asdict(result)),
                        utc_now(),
                    ),
                )
                self.store.db.execute(
                    "UPDATE runs SET status=?,finished_at=? WHERE id=?",
                    (
                        "complete" if result.complete else "needs_review",
                        utc_now(),
                        run_id,
                    ),
                )
        except BaseException as error:
            self.store.db.execute(
                "UPDATE runs SET status='failed',finished_at=?,error=? WHERE id=?",
                (utc_now(), type(error).__name__, run_id),
            )
            self.store.db.commit()
            raise
        return result

    def ingest(
        self,
        records: Iterable[Record],
        *,
        release: Release,
        selection: Selection | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> ImportResult:
        return self._ingest(
            records, release, selection or Selection(), cancelled=cancelled
        )

    def ingest_assignments(
        self,
        records: Iterable[Record],
        *,
        release: Release,
        selection: Selection | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> ImportResult:
        return self._ingest(
            records,
            release,
            selection or Selection(all_records=True),
            assignments=True,
            cancelled=cancelled,
        )

    def import_file(
        self,
        path: str | Path,
        *,
        release: Release,
        selection: Selection | None = None,
        max_expanded_bytes: int | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> ImportResult:
        path = Path(path).resolve()
        digest = file_sha256(path)
        if release.sha256 and release.sha256 != digest:
            raise ValueError("Archive checksum mismatch")
        release = replace(release, sha256=digest)
        assignments = release.product in {"PASDL", "PASYR"}
        if assignments and (
            selection is None
            or not (
                selection.all_records
                or selection.companies
                or selection.patents
                or selection.applications
            )
        ):
            raise ValueError(
                "Assignment archives require explicit companies/identifiers "
                "or all_records=True"
            )
        return self._ingest(
            read_records(
                path, assignments=assignments, max_expanded_bytes=max_expanded_bytes
            ),
            release,
            selection or Selection(),
            assignments=assignments,
            cancelled=cancelled,
        )

    def _save_assignment(self, record: Record, source_at: str) -> None:
        key = record["reel_frame"]
        old = self.store.rows(
            "SELECT source_at FROM assignments WHERE reel_frame=?", (key,)
        )
        if old and source_at <= old[0]["source_at"]:
            return
        now = utc_now()
        self.store.db.execute(
            (
                "INSERT INTO assignments VALUES(?,?,?,?,?) ON "
                "CONFLICT(reel_frame) DO UPDATE SET "
                "payload=excluded.payload,source_at=excluded.source"
                "_at,last_seen=excluded.last_seen"
            ),
            (key, canonical(record), source_at, now, now),
        )
        self.store.db.execute(
            "DELETE FROM assignment_properties WHERE reel_frame=?", (key,)
        )
        self.store.db.execute(
            "DELETE FROM assignment_parties WHERE reel_frame=?", (key,)
        )
        if record.get("purged"):
            return
        for kind in ("patents", "applications", "publications"):
            for number in record.get(kind, []):
                self.store.db.execute(
                    "INSERT OR IGNORE INTO assignment_properties VALUES(?,?,?)",
                    (key, kind, identifier(str(number))),
                )
        for role in ("assignees", "assignors"):
            for name in record.get(role, []):
                self.store.db.execute(
                    "INSERT OR IGNORE INTO assignment_parties VALUES(?,?,?,?)",
                    (key, role, name, company_key(name)),
                )

    def _save_asset_links(self, source: str, external_id: str, record: Record) -> None:
        links = []
        if source == "assignments" and not record.get("purged"):
            links = record.get("property_links", [])
        elif source == "pfw":
            metadata = record.get("applicationMetaData") or {}
            # A reexam's application number is not the underlying patent application.
            if record_kind(record) != "reexam" and metadata.get("patentNumber"):
                links.append(
                    {"application": external_id, "patent": metadata["patentNumber"]}
                )
            for edge in record.get("parentContinuityBag", []):
                if (
                    edge.get("claimParentageTypeCode") == "REX"
                    and edge.get("parentApplicationNumberText")
                    and edge.get("parentPatentNumber")
                ):
                    links.append(
                        {
                            "application": edge["parentApplicationNumberText"],
                            "patent": edge["parentPatentNumber"],
                        }
                    )
        self.store.db.execute(
            "DELETE FROM asset_links WHERE source=? AND id=?", (source, external_id)
        )
        for link in links:
            application = identifier(str(link.get("application") or ""))
            patent = identifier(str(link.get("patent") or ""))
            if application and patent:
                self.store.db.execute(
                    "INSERT OR IGNORE INTO asset_links VALUES(?,?,?,?)",
                    (application, patent, source, external_id),
                )

    def watch_company(
        self, company_id: str, name: str, *, aliases: Iterable[str] = ()
    ) -> None:
        with self.store.transaction():
            self.store.db.execute(
                (
                    "INSERT INTO companies VALUES(?,?) ON CONFLICT(id) DO UPDATE SET "
                    "name=excluded.name"
                ),
                (company_id, name),
            )
            for alias in [name, *aliases]:
                self.store.db.execute(
                    "INSERT OR IGNORE INTO aliases VALUES(?,?)",
                    (company_id, company_key(alias)),
                )

    def patent_history(self, patent: str) -> list[Record]:
        rows = self.store.rows(
            (
                "SELECT DISTINCT a.payload FROM assignments a "
                "JOIN assignment_patents p "
                "USING(reel_frame) WHERE p.patent=?"
            ),
            (identifier(patent),),
        )
        return sorted(
            [json.loads(row["payload"]) for row in rows],
            key=lambda row: row.get("recorded_date", ""),
        )

    def ownership_candidates(self, patent: str) -> Record:
        """Conservative, versioned screen of the locally known recordation history."""
        history = self.patent_history(patent)
        transfers, review = [], []
        non_title = ("SECURITY", "RELEASE", "LICENSE", "LIEN", "MORTGAGE")
        for event in history:
            conveyance = str(event.get("conveyance", "")).upper().replace("'", "")
            if any(term in conveyance for term in non_title):
                continue
            if "ASSIGNMENT OF ASSIGNORS INTEREST" in conveyance and not any(
                term in conveyance for term in ("PART", "UNDIVIDED", "CORRECT", "NUNC")
            ):
                transfers.append(event)
            else:
                review.append(event["reel_frame"])
        latest_date = max(
            (str(event.get("recorded_date", "")) for event in transfers), default=""
        )
        latest = [
            event
            for event in transfers
            if event.get("recorded_date", "") == latest_date
        ]
        candidates = sorted(
            {name for event in latest for name in event.get("assignees", [])}
        )
        if len(latest) > 1 or (transfers and not latest_date):
            review.extend(event["reel_frame"] for event in latest)
        return {
            "patent_number": identifier(patent),
            "candidates": candidates,
            "basis": "latest_known_recorded_full_assignment",
            "evidence": [event["reel_frame"] for event in latest],
            "requires_review": True,
            "ambiguous_events": sorted(set(review)),
            "rules_version": "ownership-screen-1",
            "coverage": "local records only; not a title determination",
        }

    @staticmethod
    def patent_for_record(record: Record | None) -> str:
        if not record:
            return ""
        metadata = (
            record.get("patentOwnerData") or record.get("applicationMetaData") or {}
        )
        direct = str(metadata.get("patentNumber") or "")
        # Reexaminations commonly omit patentNumber but supply a REX parent edge.
        parents = {
            identifier(str(edge.get("parentPatentNumber")))
            for edge in record.get("parentContinuityBag", [])
            if edge.get("claimParentageTypeCode") == "REX"
            and edge.get("parentPatentNumber")
        }
        if record_kind(record) == "reexam" and len(parents) == 1:
            return next(iter(parents))
        return identifier(direct)

    def company_patents(self, company_id: str) -> list[Record]:
        rows = self.store.rows(
            """
                SELECT DISTINCT p.patent AS patent_number,a.reel_frame,a.payload FROM
                aliases n
                JOIN assignment_parties t ON n.alias=t.name_key AND t.role='assignees'
                JOIN assignments a ON a.reel_frame=t.reel_frame
                JOIN assignment_patents p ON p.reel_frame=a.reel_frame
                WHERE n.company_id=?
            """,
            (company_id,),
        )
        aliases = {
            row["alias"]
            for row in self.store.rows(
                "SELECT alias FROM aliases WHERE company_id=?", (company_id,)
            )
        }
        grouped: dict[str, list[Record]] = {}
        for row in rows:
            grouped.setdefault(row["patent_number"], []).append(row)
        result = []
        for patent, records in sorted(grouped.items()):
            candidates = self.ownership_candidates(patent)
            candidate = bool(
                aliases & {company_key(name) for name in candidates["candidates"]}
            )
            result.append(
                {
                    "patent_number": patent,
                    "reel_frames": sorted({row["reel_frame"] for row in records}),
                    "basis": "recorded_assignee",
                    "status": (
                        "current_assignee_candidate"
                        if candidate
                        else "historical_or_non_title"
                    ),
                    "ownership_screen": candidates,
                }
            )
        return result

    def match_companies(self, *, include_historical: bool = False) -> list[Record]:
        new: list[Record] = []
        with self.store.transaction():
            companies = self.store.rows("SELECT * FROM companies")
            for company in companies:
                company_id = company["id"]
                aliases = {
                    row["alias"]
                    for row in self.store.rows(
                        "SELECT alias FROM aliases WHERE company_id=?", (company_id,)
                    )
                }
                portfolio: dict[str, list[Record]] = {}
                for asset in self.company_patents(company_id):
                    if (
                        include_historical
                        or asset["status"] == "current_assignee_candidate"
                    ):
                        portfolio.setdefault(asset["patent_number"], []).append(asset)
                for row in self.store.rows(
                    "SELECT * FROM records WHERE kind IN ('reexam','ipr')"
                ):
                    payload = json.loads(row["payload"])
                    metadata = (
                        payload.get("patentOwnerData")
                        or payload.get("applicationMetaData")
                        or {}
                    )
                    patent = self.patent_for_record(payload)
                    owner = company_key(str(metadata.get("patentOwnerName") or ""))
                    basis = (
                        "reported_patent_owner"
                        if owner and owner in aliases
                        else "recorded_assignee" if patent in portfolio else ""
                    )
                    if not basis:
                        continue
                    evidence = {
                        "patent_number": patent,
                        "reported_owner": metadata.get("patentOwnerName"),
                        "assignments": portfolio.get(patent, []),
                        "requires_review": True,
                    }
                    cursor = self.store.db.execute(
                        "INSERT OR IGNORE INTO matches VALUES(?,?,?,?,?,?,?)",
                        (
                            company_id,
                            row["source"],
                            row["id"],
                            basis,
                            canonical(evidence),
                            utc_now(),
                            row["first_seen"],
                        ),
                    )
                    if cursor.rowcount:
                        new.extend(
                            self.store.rows(
                                (
                                    "SELECT * FROM matches WHERE company_id=? "
                                    "AND source=? AND "
                                    "proceeding=?"
                                ),
                                (company_id, row["source"], row["id"]),
                            )
                        )
        return new

    def matches(self) -> list[Record]:
        return self.store.rows("SELECT * FROM matches ORDER BY first_detected")

    def status(self) -> Record:
        result = {
            table: self.store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "records",
                "observations",
                "releases",
                "documents",
                "assignments",
                "matches",
                "pages",
            )
        }
        result["runs"] = self.store.rows(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT 20"
        )
        result["database_bytes"] = self.store.path.stat().st_size
        return result

    def coverage(
        self, product: str, selection: Selection, *, date_from: str, date_to: str
    ) -> Record:
        covered: set[str] = set()
        for row in self.store.rows(
            "SELECT details,result FROM releases WHERE product=? AND selection=?",
            (product, selection.fingerprint),
        ):
            details, result = json.loads(row["details"]), json.loads(row["result"])
            if not result["complete"] or details["kind"] != "delta":
                continue
            current, end = date.fromisoformat(details["data_from"]), date.fromisoformat(
                details["data_to"]
            )
            while current <= end:
                covered.add(current.isoformat())
                current += timedelta(days=1)
        missing = []
        current, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
        while current <= end:
            if current.isoformat() not in covered:
                missing.append(current.isoformat())
            current += timedelta(days=1)
        return {
            "product": product,
            "selection": selection.fingerprint,
            "missing_dates": missing,
            "complete": not missing,
            "scope": "imported delta dates only; no claim of historical completeness",
        }

    def _path(self, relative: str | Path) -> Path:
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Path escapes library root")
        return target

    def add_document(self, source_path: str | Path, spec: DocumentSpec) -> Path:
        source_path = Path(source_path)
        with source_path.open("rb") as handle:
            if not handle.read(5).startswith(b"%PDF"):
                raise ValueError("Not a PDF file")
        digest = file_sha256(source_path)
        with self.store.transaction():
            previous = self.store.rows(
                "SELECT path FROM document_versions WHERE source=? AND id=? AND hash=?",
                (spec.source, spec.document_id, digest),
            )
            if previous:
                existing = self.history.resolve_path(previous[0]["path"])
                if not existing.exists() or file_sha256(existing) != digest:
                    raise ValueError("Registered original is missing or changed")
                self.history._version(spec.source, spec.document_id, digest)
                self.history._attach(
                    spec, digest, "", utc_now(), {"origin": "add_document"}
                )
                self.write_index(spec.proceeding)
                return existing
            override = self.store.rows(
                "SELECT description FROM naming_overrides WHERE source=? AND id=?",
                (spec.source, spec.document_id),
            )
            display = (
                replace(spec, description=override[0]["description"])
                if override
                else spec
            )
            relative = display.relative_path()
            target = self._path(relative)
            if target.exists() and file_sha256(target) != digest:
                relative = relative.with_name(
                    relative.stem + f" (Version {digest[:12]}).pdf"
                )
                target = self._path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and file_sha256(target) != digest:
                raise FileExistsError(target)
            if not target.exists():
                temporary = target.with_name(
                    target.name + "." + uuid.uuid4().hex + ".part"
                )
                shutil.copyfile(source_path, temporary)
                if file_sha256(temporary) != digest:
                    temporary.unlink()
                    raise ValueError("Source changed while copying")
                os.replace(temporary, target)
            self.store.db.execute(
                (
                    "INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(source,id) DO "
                    "UPDATE SET current_hash=excluded.current_hash,spec=excluded.spec"
                ),
                (spec.source, spec.document_id, digest, canonical(asdict(spec))),
            )
            self.store.db.execute(
                "INSERT INTO document_versions VALUES(?,?,?,?,?)",
                (spec.source, spec.document_id, digest, relative.as_posix(), utc_now()),
            )
            self.history._version(spec.source, spec.document_id, digest)
            self.history._attach(
                spec, digest, "", utc_now(), {"origin": "add_document"}
            )
        self.write_index(spec.proceeding)
        return target

    def set_description(
        self, source: str, document_id: str, description: str, *, reason: str
    ) -> None:
        if not reason.strip():
            raise ValueError("A reviewed naming override requires a reason")
        with self.store.transaction():
            self.store.db.execute(
                (
                    "INSERT INTO naming_overrides VALUES(?,?,?,?,?) ON "
                    "CONFLICT(source,id) DO UPDATE SET "
                    "description=excluded.description,reason=excluded.r"
                    "eason,updated_at=excluded.updated_at"
                ),
                (source, document_id, description, reason, utc_now()),
            )

    def add_text(
        self,
        source: str,
        document_id: str,
        pages: Iterable[str],
        *,
        method: str,
        version: str,
    ) -> str:
        document = self.store.rows(
            "SELECT current_hash FROM documents WHERE source=? AND id=?",
            (source, document_id),
        )
        if not document:
            raise KeyError(document_id)
        texts = list(pages)
        run = fingerprint(
            [source, document_id, document[0]["current_hash"], method, version, texts]
        )
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO text_runs VALUES(?,?,?,?,?,?,?)",
                (
                    run,
                    source,
                    document_id,
                    document[0]["current_hash"],
                    method,
                    version,
                    utc_now(),
                ),
            )
            for number, text in enumerate(texts, 1):
                self.store.db.execute(
                    (
                        "INSERT OR IGNORE INTO pages(run_id,page_number,text) "
                        "VALUES(?,?,?)"
                    ),
                    (run, number, text),
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
    ) -> Path:
        known = self.store.rows(
            "SELECT hash FROM document_versions WHERE source=? AND id=? AND hash=?",
            (source, document_id, original_hash),
        )
        if not known:
            raise ValueError("Derivative requires a registered original hash")
        path = Path(path)
        digest = file_sha256(path)
        relative = Path("derivatives") / original_hash / (digest + path.suffix.lower())
        target = self._path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".part")
            shutil.copyfile(path, temporary)
            if file_sha256(temporary) != digest:
                temporary.unlink()
                raise ValueError("Derivative changed while copying")
            os.replace(temporary, target)
        elif file_sha256(target) != digest:
            raise ValueError("Registered derivative has changed")
        with self.store.transaction():
            self.store.db.execute(
                "INSERT OR IGNORE INTO derivatives VALUES(?,?,?,?,?,?,?)",
                (
                    source,
                    document_id,
                    original_hash,
                    digest,
                    relative.as_posix(),
                    method,
                    version,
                ),
            )
        self.history.add_derivative(
            source,
            document_id,
            target,
            original_hash=original_hash,
            method=method,
            version=version,
            created_at=utc_now(),
            provenance={"origin": "add_derivative"},
        )
        return target

    def extract_text(
        self,
        source: str,
        document_id: str,
        extractor: Callable[[Path], Iterable[str]],
        *,
        method: str,
        version: str,
    ) -> str:
        rows = self.store.rows(
            (
                "SELECT v.path FROM document_versions v JOIN documents d ON "
                "v.source=d.source AND v.id=d.id AND v.hash=d.current_hash WHERE "
                "d.source=? AND d.id=?"
            ),
            (source, document_id),
        )
        if not rows:
            raise KeyError(document_id)
        path = self.history.resolve_path(rows[0]["path"])
        before = file_sha256(path)
        import tempfile

        with tempfile.TemporaryDirectory(dir=self.root / "runs") as temporary:
            working = Path(temporary) / path.name
            shutil.copyfile(path, working)
            pages = list(extractor(working))
        if before != file_sha256(path):
            raise ValueError("Extractor modified an original PDF")
        return self.add_text(source, document_id, pages, method=method, version=version)

    def annotate(
        self,
        source: str,
        document_id: str,
        *,
        pdf_hash: str,
        page_number: int,
        field: str,
        value: Any,
        method: str,
        version: str,
        review_status: str = "unreviewed",
    ) -> str:
        if page_number < 1 or review_status not in {
            "unreviewed",
            "reviewed",
            "rejected",
        }:
            raise ValueError("Invalid evidence annotation")
        if not self.store.rows(
            "SELECT 1 FROM document_versions WHERE source=? AND id=? AND hash=?",
            (source, document_id, pdf_hash),
        ):
            raise ValueError("Annotation requires a registered document version")
        annotation_id = uuid.uuid4().hex
        with self.store.transaction():
            self.store.db.execute(
                "INSERT INTO annotations VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    annotation_id,
                    source,
                    document_id,
                    pdf_hash,
                    page_number,
                    field,
                    canonical(value),
                    method,
                    version,
                    review_status,
                    utc_now(),
                ),
            )
        return annotation_id

    def rebuild_text_index(self) -> None:
        with self.store.transaction():
            self.store.db.execute("INSERT INTO pages_fts(pages_fts) VALUES('rebuild')")

    def search_text(self, query: str, *, limit: int = 50) -> list[Record]:
        return self.store.rows(
            """
                SELECT
                r.source,r.document_id,r.pdf_hash,p.page_number,p.text,r.method,r.version
                FROM pages_fts
                JOIN pages p ON p.id=pages_fts.rowid JOIN text_runs r ON r.id=p.run_id
                JOIN documents d ON d.source=r.source AND d.id=r.document_id AND
                d.current_hash=r.pdf_hash
                WHERE pages_fts MATCH ? LIMIT ?
            """,
            (query, limit),
        )

    def verify(self) -> Record:
        result: Record = {
            "missing": [],
            "changed": [],
            "integrity": self.store.db.execute("PRAGMA integrity_check").fetchone()[0],
        }
        for row in self.store.rows(
            "SELECT hash,path FROM document_versions UNION SELECT hash,path "
            "FROM derivatives UNION SELECT hash,path FROM "
            "derivative_events UNION SELECT v.hash,l.path FROM "
            "retained_locations l JOIN version_ids v "
            "USING(version_id) UNION SELECT raw_sha256 AS "
            "hash,raw_path AS path FROM source_snapshots"
        ):
            path = self.history.resolve_path(row["path"])
            if not path.exists():
                result["missing"].append(row["path"])
            elif file_sha256(path) != row["hash"]:
                result["changed"].append(row["path"])
        return result

    def backup(self, destination: str | Path) -> Path:
        destination = Path(destination).resolve()
        self.store.backup(destination)
        return destination

    @classmethod
    def restore_database(cls, backup: str | Path, root: str | Path) -> Library:
        """Restore a database to a new root; originals must be copied separately."""
        import sqlite3

        from uspto_client.storage import SCHEMA_VERSION

        root = Path(root).resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError("Restore requires a new or empty library root")
        source = Path(backup).resolve()
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup failed integrity check")
            if connection.execute("PRAGMA user_version").fetchone()[0] not in range(
                1, SCHEMA_VERSION + 1
            ):
                raise ValueError("Unsupported backup schema version")
            if not connection.execute(
                "SELECT name FROM sqlite_master WHERE name='releases'"
            ).fetchone():
                raise ValueError("Not a uspto-client library backup")
            destination = root / "databases" / "library.sqlite3"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(destination) as restored:
                connection.backup(restored)
        return cls(root)

    def discover(
        self,
        client: UsptoClient,
        *,
        date_from: str,
        date_to: str,
        kinds: tuple[str, ...] = ("reexam", "reissue", "ipr"),
        max_records: int = 1000,
    ) -> Record:
        from uspto_client.library_operations import discover

        return discover(
            self,
            client,
            date_from=date_from,
            date_to=date_to,
            kinds=kinds,
            max_records=max_records,
        )

    def write_index(self, proceeding: str) -> list[Path]:
        """Generate a readable docket index linking retained proceeding attachments."""
        import html
        from urllib.parse import quote

        entries = []
        folders: set[Path] = set()
        for row in self.store.rows(
            (
                "SELECT a.spec,v.path,a.source,a.id,a.hash FROM "
                "document_attachments a JOIN document_versions v ON "
                "a.source=v.source AND a.id=v.id AND a.hash=v.hash WHERE "
                "a.proceeding=?"
            ),
            (proceeding,),
        ):
            spec = json.loads(row["spec"])
            relative = Path(row["path"])
            layout = DocumentSpec(**spec).relative_path()
            folder = self._path(Path(*layout.parts[:2]))
            folder.mkdir(parents=True, exist_ok=True)
            folders.add(folder)
            entries.append((folder, relative, spec))
        written = []
        for folder in folders:
            items = []
            for entry_folder, relative, _spec in sorted(
                entries, key=lambda item: item[1].as_posix()
            ):
                if entry_folder != folder:
                    continue
                target = self.history.resolve_path(str(relative))
                try:
                    href = quote(Path(os.path.relpath(target, folder)).as_posix())
                except ValueError:
                    href = target.as_uri()
                items.append(
                    f'<li><a href="{href}">{html.escape(relative.name)}</a></li>'
                )
            output = folder / "index.html"
            output.write_text(
                '<!doctype html><meta charset="utf-8"><title>'
                + html.escape(proceeding)
                + "</title><h1>"
                + html.escape(proceeding)
                + "</h1><ul>"
                + "".join(items)
                + "</ul>",
                encoding="utf-8",
            )
            written.append(output)
        return written
