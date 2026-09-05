# Library schema and provenance

Schema version 1 is stored in `PRAGMA user_version`. All data is in
`databases/library.sqlite3`; no PDF bytes are in SQLite.

| Tables | Purpose |
| --- | --- |
| records | Current normalized views, keyed by source and official identifier |
| observations | Immutable payload/hash/release/time evidence |
| source_conflicts | Contradictory observations with equal source timestamps |
| releases, runs | Exact filter, file/hash identity, outcomes and import completion |
| bulk_files | Successful catalog-revision/filter receipts, independent of ZIP retention |
| assignments, assignment_properties, assignment_parties | Current recordation data and indexed lookup relations |
| companies, aliases | Explicitly reviewed watchlist names |
| matches | Immutable first-detection events and original evidence |
| documents, document_versions | Stable document IDs, original hashes and readable locations |
| derivatives | Hash-linked OCR or other derivative artifacts |
| naming_overrides | Reviewed descriptions, reasons and update times |
| text_runs, pages, pages_fts | Extraction provenance, page text and rebuildable FTS5 |
| annotations | Append-only page/version evidence and review status |

Sources distinguish `pfw`, `ptab`, their separate inventory endpoints, and
`assignments`. Source observations are retained for selected records; skipped
bulk records are not retained. Raw API responses/record XML live in observations;
retained bulk archives provide the original full input when that policy is used.
Derived current views may combine non-conflicting fields from several observations.

An import and its completion record commit atomically. Runs are recorded outside
that transaction to preserve failures. SQLite serializes writers using
`BEGIN IMMEDIATE` and a busy timeout. A full archive import can hold that writer
transaction for a long time; use one ingestion process per library. Readers can
continue under WAL. Metadata call pacing remains the low-level client's existing
in-process behavior; separate machines sharing an API key need an external
coordinator. Bulk downloads have an additional per-destination process lock.

Stable IDs and external relative paths are the migration contract. Database
filenames, schemas, and FTS implementation are backend-specific. Do not bind a
consuming project's application code to SQLite SQL if a later database change
is anticipated; use Library operations or contribute an explicit new operation.

`asset_links` retains source-attributed application/patent pairs; the
`assignment_patents` view joins direct patent properties and application-only
assignments through those explicit pairs.
