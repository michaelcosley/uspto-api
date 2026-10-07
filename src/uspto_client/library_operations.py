"""Bounded collection and bulk synchronization operations for a Library."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from uspto_client.assignment import AssignmentCenterClient
from uspto_client.client import UsptoClient
from uspto_client.library_models import (
    DocumentSpec,
    Record,
    Release,
    Selection,
    identifier,
    record_kind,
    utc_now,
)
from uspto_client.streaming import stream_download

if TYPE_CHECKING:
    from uspto_client.library import Library


def collect(
    library: Library,
    client: UsptoClient,
    *,
    applications: Iterable[str] = (),
    trials: Iterable[str] = (),
    download_ids: Iterable[str] = (),
) -> Record:
    selected = set(download_ids)
    found_ids: set[str] = set()
    output: Record = {
        "applications": 0,
        "trials": 0,
        "downloaded": 0,
        "reused": 0,
        "unresolved_patents": [],
    }
    today = date.today().isoformat()
    release = Release(
        "api", uuid.uuid4().hex, today, today, "targeted", source_as_of=utc_now()
    )
    for number in applications:
        number = identifier(number)
        response = client.applications.get(number)
        records = response.patent_file_wrapper_data_bag
        library.ingest(
            records, release=release, selection=Selection(applications=(number,))
        )
        current = library.get_record("pfw", number)
        patent = library.patent_for_record(current)
        if not patent:
            output["unresolved_patents"].append(number)
        documents = client.applications.get_documents(number)
        with library.store.transaction():
            library.store.observe(
                "pfw-inventory",
                number,
                "inventory",
                documents.raw_data,
                utc_now(),
                release.file_name,
            )
        for record in documents.document_bag:
            doc_id = str(record.get("documentIdentifier") or "")
            if doc_id not in selected:
                continue
            found_ids.add(doc_id)
            spec = DocumentSpec(
                "pfw",
                doc_id,
                number,
                record_kind(current or {}),
                patent,
                str(record.get("officialDate") or ""),
                str(
                    record.get("documentCodeDescriptionText")
                    or record.get("documentCode")
                    or "Document"
                ),
                source_metadata=record,
            )
            _download(
                library,
                client,
                f"/api/v1/download/applications/{number}/{doc_id}.pdf",
                spec,
                output,
            )
        output["applications"] += 1
    for trial in trials:
        records = [
            (
                record.raw_data
                if hasattr(record, "raw_data")
                else record.model_dump(by_alias=True)
            )
            for record in client.ptab.trials.get_proceeding(trial).proceedings
        ]
        library.ingest(records, release=release, selection=Selection(trials=(trial,)))
        patent = library.patent_for_record(library.get_record("ptab", trial))
        trial_documents = client.ptab.trials.get_documents(trial)
        with library.store.transaction():
            library.store.observe(
                "ptab-inventory",
                trial,
                "inventory",
                trial_documents.raw_data,
                utc_now(),
                release.file_name,
            )
        for document in trial_documents.documents:
            record = document.model_dump(by_alias=True)
            data = record.get("documentData") or {}
            doc_id = str(data.get("documentIdentifier") or "")
            if doc_id not in selected:
                continue
            found_ids.add(doc_id)
            number = str(data.get("documentNumber") or "")
            exhibit = str(data.get("documentCategory") or "").casefold() == "exhibit"
            party = str(data.get("filingPartyCategory") or "").upper()
            side = (
                "owner"
                if "OWNER" in party
                else (
                    "petitioner"
                    if "PETITIONER" in party
                    else "board" if "BOARD" in party else "unknown"
                )
            )
            spec = DocumentSpec(
                "ptab",
                doc_id,
                trial,
                "ipr" if trial.startswith("IPR") else "ptab",
                patent,
                str(data.get("documentFilingDate") or ""),
                str(
                    data.get("documentTitleText")
                    or data.get("documentTypeDescriptionText")
                    or "Document"
                ),
                paper_number="" if exhibit else number,
                exhibit_number=number if exhibit else "",
                side=side,
                source_metadata=record,
            )
            uri = data.get("fileDownloadURI")
            if not uri:
                raise ValueError(f"Document {doc_id} lacks a download URI")
            _download(library, client, uri, spec, output)
        output["trials"] += 1
    if selected - found_ids:
        raise ValueError(
            "Selected document IDs were absent: "
            + ", ".join(sorted(selected - found_ids))
        )
    output["new_matches"] = library.match_companies()
    return output


def _download(
    library: Library, client: UsptoClient, uri: str, spec: DocumentSpec, output: Record
) -> None:
    existing = library.store.rows(
        "SELECT current_hash FROM documents WHERE source=? AND id=?",
        (spec.source, spec.document_id),
    )
    if existing:
        from uspto_client.streaming import file_sha256

        locations = library.store.rows(
            "SELECT path FROM document_versions WHERE source=? AND id=? AND hash=?",
            (spec.source, spec.document_id, existing[0]["current_hash"]),
        )
        if not locations:
            raise ValueError("Registered document has no stored version")
        original = library._path(locations[0]["path"])
        if (
            not original.exists()
            or file_sha256(original) != existing[0]["current_hash"]
        ):
            raise ValueError("Registered document is missing or changed")
        output["reused"] += 1
        return
    temporary = library.root / "runs" / f"{uuid.uuid4().hex}.pdf"
    stream_download(client, uri, temporary)
    library.add_document(temporary, spec)
    temporary.unlink()
    output["downloaded"] += 1


def collect_assignments(
    library: Library,
    client: AssignmentCenterClient,
    *,
    company_id: str,
    max_pages: int = 100,
) -> Record:
    from uspto_client.assignment_models import AssignmentDataFilter

    aliases = library.store.rows(
        "SELECT alias FROM aliases WHERE company_id=?", (company_id,)
    )
    if not aliases:
        raise ValueError("Register the company and its reviewed aliases first")
    total = 0
    for alias in aliases:
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            response = client.search_exact_assignee(
                alias["alias"], data_filter=AssignmentDataFilter(currentPage=page)
            )
            records = []
            for group in response.results:
                for assignment in group.assignment_records:
                    raw = assignment.model_dump(by_alias=True)
                    key = str(
                        assignment.reel_frame
                        or f"{assignment.reel_number}/{assignment.frame_number}"
                    )
                    # The public search returns a property group and surrounding chain.
                    records.append(
                        {
                            "reel_frame": key,
                            "conveyance": assignment.conveyance or "",
                            "recorded_date": assignment.recordation_date or "",
                            "source_modified": utc_now(),
                            "assignees": [
                                p.assignee_name
                                for p in assignment.assignees
                                if p.assignee_name
                            ],
                            "assignors": [
                                p.assignor_name
                                for p in assignment.assignors
                                if p.assignor_name
                            ],
                            "patents": [
                                identifier(p.patent_number)
                                for p in group.properties
                                if p.patent_number
                            ],
                            "applications": [
                                identifier(p.application_number)
                                for p in group.properties
                                if p.application_number
                            ],
                            "raw": {
                                "assignment": raw,
                                "properties": [
                                    p.model_dump(by_alias=True)
                                    for p in group.properties
                                ],
                            },
                            "property_links": [
                                {
                                    "application": identifier(p.application_number),
                                    "patent": identifier(p.patent_number),
                                }
                                for p in group.properties
                                if p.application_number and p.patent_number
                            ],
                            "property_scope": (
                                "search_result_group; verify "
                                "transaction-specific coverage"
                            ),
                        }
                    )
            signature = json.dumps(
                [record["raw"] for record in records], sort_keys=True
            )
            if signature in seen and records:
                raise ValueError("Assignment pagination made no progress")
            seen.add(signature)
            today = date.today().isoformat()
            result = library.ingest_assignments(
                records,
                release=Release(
                    "assignment-center",
                    uuid.uuid4().hex,
                    today,
                    today,
                    "targeted",
                    source_as_of=utc_now(),
                ),
            )
            total += result.retained
            success = response.success_response
            if (
                not records
                or (success and success.backend_pagination is False)
                or (success and page * 100 >= success.total_rows)
            ):
                break
        else:
            raise ValueError("Assignment page limit reached; collection is incomplete")
    return {"records": total, "new_matches": library.match_companies()}


def sync_bulk(
    library: Library,
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
    from uspto_client.library_models import fingerprint
    from uspto_client.streaming import file_sha256

    if product not in {"PTFWPRD", "PASDL", "PTFWPRE", "PASYR"}:
        raise ValueError("Unsupported bulk import product")
    if date.fromisoformat(date_from) > date.fromisoformat(date_to):
        raise ValueError("Date range is reversed")
    files = [
        file
        for file in client.bulk.iter_files(
            product, date_from=date_from, date_to=date_to
        )
        if file.file_type != "Document" and file.file_name.lower().endswith(".zip")
    ]
    pending = []
    skipped = []
    for file in files:
        if file.file_size is None:
            raise ValueError("Cannot enforce a budget without listed file sizes")
        revision = fingerprint([file.modified, file.release_date, file.file_size])
        imported = library.store.rows(
            (
                "SELECT sha256 FROM bulk_files WHERE product=? AND filename=? AND "
                "revision=? AND selection=?"
            ),
            (product, file.file_name, revision, selection.fingerprint),
        )
        if imported:
            skipped.append(file.file_name)
        else:
            pending.append((file, revision))
    total = sum(file.file_size or 0 for file, _ in pending)
    plan: Record = {
        "product": product,
        "files": [file.model_dump(by_alias=True) for file, _ in pending],
        "already_imported": skipped,
        "advertised_bytes": total,
        "within_budget": total <= max_download_bytes,
        "executed": False,
    }
    if not execute:
        return plan
    if total > max_download_bytes:
        raise ValueError("Bulk plan exceeds download budget")
    if not files:
        raise ValueError("No listed data files; synchronization cannot claim coverage")
    results = []
    for file, revision in sorted(
        pending, key=lambda item: (item[0].data_from or "", item[0].file_name)
    ):
        if Path(file.file_name).name != file.file_name or "\\" in file.file_name:
            raise ValueError("Unsafe bulk filename")
        if not file.data_from or not file.data_to:
            raise ValueError("Release lacks coverage dates")
        # Catalog revisions get separate paths: same-name corrections cannot reuse
        # old bytes.
        destination = (
            library.root / "sources" / "bulk" / product / revision[:16] / file.file_name
        )
        receipt = destination.with_suffix(destination.suffix + ".receipt.json")
        if destination.exists():
            saved = json.loads(receipt.read_text()) if receipt.exists() else {}
            if destination.stat().st_size != file.file_size or saved.get(
                "sha256"
            ) != file_sha256(destination):
                raise ValueError("Existing archive lacks a valid download receipt")
        else:
            downloaded = client.bulk.download_file(
                product,
                file.file_name,
                output_path=destination,
                expected_size=file.file_size,
                max_bytes=max_download_bytes,
            )
            receipt.write_text(
                json.dumps({"sha256": downloaded.sha256, "revision": revision}),
                encoding="utf-8",
            )
        release = Release(
            product,
            file.file_name,
            file.data_from,
            file.data_to,
            "delta" if product in {"PTFWPRD", "PASDL"} else "snapshot",
        )
        result = library.import_file(destination, release=release, selection=selection)
        results.append(asdict(result))
        if result.complete:
            with library.store.transaction():
                library.store.db.execute(
                    "INSERT OR REPLACE INTO bulk_files VALUES(?,?,?,?,?,?,?)",
                    (
                        product,
                        file.file_name,
                        revision,
                        selection.fingerprint,
                        file_sha256(destination),
                        file.file_size,
                        destination.relative_to(library.root).as_posix(),
                    ),
                )
            if not retain_archives:
                destination.unlink()
    plan.update(
        {"executed": True, "results": results, "new_matches": library.match_companies()}
    )
    if product in {"PTFWPRD", "PASDL"}:
        plan["coverage"] = library.coverage(
            product, selection, date_from=date_from, date_to=date_to
        )
    plan["complete"] = all(item["complete"] for item in results) and plan.get(
        "coverage", {}
    ).get("complete", True)
    return plan


def discover(
    library: Library,
    client: UsptoClient,
    *,
    date_from: str,
    date_to: str,
    kinds: tuple[str, ...],
    max_records: int,
) -> Record:
    """Search a bounded ingestion window. Repeat overlapping windows to reconcile."""
    if date.fromisoformat(date_from) > date.fromisoformat(date_to) or max_records < 1:
        raise ValueError("Invalid discovery bounds")
    selection = Selection(kinds=kinds)
    window_start = date_from + "T00:00:00Z"
    window_end = (
        date.fromisoformat(date_to) + timedelta(days=1)
    ).isoformat() + "T00:00:00Z"
    page_size = min(100, max_records)
    fetched = 0
    queries = []
    labels = {"reexam": "Re-Examination", "reissue": "Re-Issue"}
    wanted = [labels[kind] for kind in kinds if kind in labels]
    if wanted:
        label_query = " OR ".join('"' + label + '"' for label in wanted)
        queries.append(
            (
                "pfw",
                f"applicationMetaData.applicationTypeLabelName:({label_query})",
            )
        )
    if "ipr" in kinds:
        queries.append(
            (
                "ptab",
                "trialMetaData.trialTypeCode:IPR "
                f"AND lastModifiedDateTime:[{window_start} TO {window_end}]",
            )
        )
    if not queries:
        raise ValueError("Discovery supports reexam, reissue, and ipr kinds")
    for source, query in queries:
        offset = 0
        seen: set[str] = set()
        while True:
            limit = min(page_size, max_records - fetched)
            if limit <= 0:
                return {
                    "records": fetched,
                    "complete": False,
                    "reason": "record_budget",
                    "new_matches": library.match_companies(),
                }
            if source == "pfw":
                response = client.applications.search(
                    body={
                        "q": query,
                        "rangeFilters": [
                            {
                                "field": "lastIngestionDateTime",
                                "valueFrom": date_from + "T00:00:00",
                                "valueTo": date_to + "T23:59:59",
                            }
                        ],
                        "pagination": {"offset": offset, "limit": limit},
                    }
                )
                records = response.patent_file_wrapper_data_bag
                count = response.count
            else:
                trial_response = client.ptab.trials.search_proceedings(
                    q=query, offset=offset, limit=limit
                )
                records = [
                    record.model_dump(by_alias=True)
                    for record in trial_response.proceedings
                ]
                count = trial_response.count
            if not records:
                if count is not None and offset < count:
                    raise ValueError("Search ended before its reported count")
                break
            ids = {
                str(record.get("applicationNumberText") or record.get("trialNumber"))
                for record in records
            }
            if not ids - seen:
                raise ValueError("Discovery pagination made no progress")
            seen.update(ids)
            if len(records) > limit:
                raise ValueError("Search exceeded its requested record budget")
            # Search projections can omit continuity needed to identify a challenged
            # patent.
            enriched = []
            for record in records:
                if record_kind(record) == "reexam" and not library.patent_for_record(
                    record
                ):
                    enriched.extend(
                        client.applications.get(
                            str(record["applicationNumberText"])
                        ).patent_file_wrapper_data_bag
                    )
                else:
                    enriched.append(record)
            release = Release(
                "api-discovery",
                uuid.uuid4().hex,
                date_from,
                date_to,
                "targeted",
                source_as_of=utc_now(),
            )
            imported = library.ingest(enriched, release=release, selection=selection)
            if not imported.complete:
                return {
                    "records": fetched,
                    "complete": False,
                    "reason": "unrecognized_records",
                }
            fetched += len(records)
            offset += len(records)
            if count is not None and offset >= count:
                break
            if count is None and len(records) < limit:
                break
    return {
        "records": fetched,
        "complete": True,
        "scope": {"from": date_from, "to": date_to, "kinds": kinds},
        "new_matches": library.match_companies(),
    }
