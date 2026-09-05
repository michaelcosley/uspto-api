# Portable USPTO library (0.4)

The opt-in `Library` API adds SQLite storage, readable PDFs, selective bulk
imports, text indexing, and company watchlists. Existing `UsptoClient` and
`AssignmentCenterClient` calls keep their 0.3 behavior. They do not create a
library or import data automatically.

## Install and initialize

```console
python -m pip install "uspto-client[library]"
uspto-library --root data init
uspto-library --root data status
```

`USPTO_DATA_ROOT` supplies the default root. Otherwise the default is `data`
under the current directory, independent of Git or USPTO-Tools. Supply
`USPTO_API_KEY` only for ODP calls. Library code never loads `.env` files.
Catalog queries create no local database. Other commands open/initialize the
explicit library; `sync-bulk` plans by default and needs `--execute` to download.

The initial schema uses **one SQLite file** with separate logical table groups.
This makes metadata, source observations, import completion and watchlist state
transactionally consistent. PDFs and archives remain external. SQLite-specific
code is isolated in `storage.py` and the library implementation; `RecordStorage`
provides the observation contract for later backend work. Other backends and a
fully backend-neutral query/search interface are not implemented in 0.4.

```text
data/
  config/library.json
  databases/library.sqlite3
  reexams/90000001 ('678)/
    index.html
    2026-01-01 90000001 ('678) Request for EPR.pdf
    Request Exhibits/Ex 1003 Declaration.pdf
  reissues/[application-number]/
  applications/[application-number]/
  iprs/IPR2026-00001 ('678)/
    index.html
    2026-01-01 (001) IPR2026-00001 ('678) Petition.pdf
    Pet. Exhibits/Ex 1001 Patent.pdf
    PO Exhibits/
    Board Exhibits/
    Unclassified Exhibits/
  derivatives/[original-hash]/[derivative-hash].pdf
  sources/bulk/[product]/[catalog-revision]/[filename].zip
  runs/
  exports/
  backups/
```

All stored file locations are relative to the root. Close library connections
before relocating the directory. Reopen at its new path and run `verify`.
Use local storage for the live WAL database; do not share it among computers
through a network or synchronization folder. A future server backend can address
that use case.

## Collect selected matters

```python
import os
from uspto_client import Library, UsptoClient

with Library("data") as library, UsptoClient(api_key=os.environ["USPTO_API_KEY"]) as client:
    result = library.collect(client, applications=["90000001"], trials=["IPR2026-00001"])
```

The identifiers above are illustrative. This collects metadata and document
inventories. PDFs require explicit `download_ids=[...]`; the CLI equivalent is
repeatable `--download-id`. Known document identifiers are reused. Deliberate
source revisions can be registered with `add_document`; an ordinary resume does
not redownload every existing original. Missing selected IDs are reported as an
error rather than silently treated as downloaded.

Reexamination challenged-patent identification uses an explicit `REX` continuity
edge when the main patent field is absent. Unresolved links are reported. Do not
infer a challenged patent from inventor names or arbitrary ancestors.

## Readable originals and text

```python
from uspto_client import DocumentSpec, Library

spec = DocumentSpec(
    source="ptab", document_id="official-document-id",
    proceeding="IPR2026-00001", kind="ipr", patent="12345678",
    official_date="2026-01-01", description="Petition", paper_number="1",
)
with Library("data") as library:
    original = library.add_document("download.pdf", spec)
    library.add_text("ptab", "official-document-id", ["Page one text"],
                     method="my-extractor", version="1")
    results = library.search_text('"Page one"')
```

`DocumentSpec` supports actual paper/exhibit numbers, filing side, part number,
status, and untouched source metadata. No numbers or filing sides are inferred.
Missing sides go to `Unclassified Exhibits`; filenames omit missing dates and
paper numbers. Descriptions are explicit, so callers can supply approved short
names. Unknown exhibit numbers can be retained as ordinary unnumbered documents
with a descriptive title; they are not assigned fictional exhibit numbers.

Originals are copied without changing their bytes. SHA-256 identifies each
version. Same-identifier/same-hash registration reuses the original; changed
bytes receive a separate version path. Different official identifiers remain
distinct even if their contents are equal. PDF validation checks the signature
and stored hashes; it is not a substitute for a full PDF structural validator.

`set_description(..., reason=...)` stores a reviewed override for subsequent
registrations. It does not rename existing PDFs. `write_index(proceeding)`
regenerates the local index. Existing collections can be organized explicitly
by their consuming project during the later migration.

`add_derivative` records its original hash, method and version. `extract_text`
passes a scratch copy to an external extractor, preserving originals even if the
extractor performs OCR. It does not install or invoke an OCR engine itself.
`annotate` stores append-only page/version-linked findings and review status.
`search_text` searches current PDF versions; older extraction evidence remains
stored. `rebuild-text-index` rebuilds FTS5 from page text.

## Recovery and database operations

```console
uspto-library --root data verify
uspto-library --root data backup backups/library-2026-09-05.sqlite3
uspto-library --root restored-data restore-database backups/library-2026-09-05.sqlite3
```

A database backup is consistent even with WAL enabled. It does **not** contain
PDFs, derivatives, or retained archives. Back up those files as well. Restore
requires an empty/new root; copy the corresponding external files and then
verify. A newer unknown schema or an unrelated database is rejected. Schema
version 1 initializes fresh libraries; no legacy USPTO-Tools database migration
is included. Future schema migrations must back up before altering existing
schemas and must refuse downgrades.

An interrupted import rolls back that file's database transaction. Retry starts
parsing the file from its beginning, skips no uncommitted records, and remains
memory-bounded. Completed files are remembered. Failed runs are recorded; a hard
process termination may leave a `running` run entry, but never a committed
completion marker for a rolled-back import.

See [bulk ingestion](bulk-ingestion.md), [company monitoring](company-monitoring.md),
[schema](library-schema.md), and [future adoption](library-adoption.md).
