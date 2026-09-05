# Future adoption by USPTO-Tools and other consumers

0.4 adds standalone functionality. It does not migrate existing databases,
rename existing collections, change consumer imports, update a submodule pointer,
install a scheduler, or start bulk downloads.

## Stable integration points

| Existing responsibility | New integration boundary |
| --- | --- |
| API transport | Existing UsptoClient/AssignmentCenterClient APIs, unchanged |
| Metadata persistence | Library.ingest, get_record, collect, discover |
| Bulk catalogs and files | client.bulk and Library.sync_bulk/import_file |
| PDF naming/storage | DocumentSpec, Library.add_document |
| OCR/text reuse | add_derivative, add_text, extract_text, search_text |
| Company candidates | watch_company, collect_assignments, company_patents, ownership_candidates |
| First detection | match_companies and new_matches |
| Local review findings | annotate; project-specific analysis stays in the consumer |

The new schema is not a drop-in replacement for USPTO-Tools' existing metadata,
PTAB library, content, participant, or workflow databases. In particular,
participants and firm affiliation registries remain consumer-managed. The
company/alias registry here is only the portable watchlist capability.

## Later migration work

1. Freeze the implemented public contracts and release version; inventory every
   existing consumer, database schema, document identifier namespace and path rule.
2. Produce a read-only mapping report from old IDs, source endpoints and hashes
   to the new records. Preserve official IDs, observation times, reviewed labels,
   naming overrides, derivatives and original-to-OCR provenance.
3. Copy a representative subset to a new root; do not point the new Library at
   an old database. Import metadata through an explicit adapter and register
   existing files by their known hashes. Do not redownload to discover data already
   present locally.
4. Compare counts, source history, hashes, full-text results and first-detection
   semantics. Old filenames are not immutable identifiers. Resolve unknown
   challenged patents using source evidence, not filenames alone.
5. Adopt one consumer at a time behind its existing adapter. Keep project-specific
   deadlines, labels and review state separate. Verify old resume behavior before
   making the new library authoritative.
6. Cut over only after backups and a rollback path are verified. Update the
   pinned client version separately. Retain old stores until reconciliation and
   rollback requirements are satisfied.

A detailed per-file refactoring plan must be prepared against the then-current
USPTO-Tools checkout. This document is a boundary map, not an executed migration.
