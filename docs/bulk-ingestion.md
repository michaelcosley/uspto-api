# Bulk ingestion and synchronization

## Products

| ID | Meaning | Intended operation |
| --- | --- | --- |
| PTFWPRE | PFW snapshots refreshed weekly, partitioned by broad filing-year ranges | Bootstrap or recover selected metadata |
| PTFWPRD | Daily PFW deltas | Apply subsequent changed records |
| PASYR | Assignment historical backfile | Establish historical assignment coverage |
| PASDL | Daily assignment XML | Catch up with recordations, corrections and purges |

Catalog verified 2026-09-05: PFW snapshot ZIPs total approximately 64.5 GB;
seven listed daily PFW ZIPs total approximately 3.38 GB. These are changing
catalog values, not hard-coded budgets. Catalog descriptions and release dates
are not sufficient to infer a snapshot extraction cutoff. The current PASYR
backfile description and filenames disagree about the coverage endpoint.
Record dates and official release documentation must resolve that before a
production baseline is treated as complete.

A weekly snapshot is the dataset for its covered filing years refreshed weekly,
not one week's activity. Successive snapshots should not be concatenated as if
they were disjoint increments. Weekly snapshots do not guarantee pre-2001 PFW
coverage. A missing historical record can require targeted API collection.

## Inspect, plan, then execute

```console
uspto-library catalog --product PTFWPRD
uspto-library --root data sync-bulk --product PTFWPRD --from 2026-09-01 --to 2026-09-04 --kind reexam --kind reissue --max-download-bytes 3000000000
```

Add `--execute` to download/import the plan. `--discard-archives` removes each
successfully imported archive after its checksum, revision, filter and completion
are committed; failed or uncertain imports keep their archive. Neither flag
starts a recurring schedule. Daily files can be consumed on a weekly/monthly
cadence, subject to the source's available retention window.

The budget covers the advertised sizes of pending files. A retained pending
archive is conservatively included in the plan budget even when no network
transfer will be necessary. Successfully imported files are skipped even when
their ZIPs were discarded. A new selection or catalog revision is a new job.
A catalog revision gets a separate download path, preventing same-name corrected
releases from reusing stale bytes.

The typed API lives under `client.bulk`: `search`, `get_product`, `iter_files`,
and `download_file`. Downloads stream to disk, honor existing pacing/retry
settings, and expose progress/cancellation callbacks. Resume uses Range/If-Range
with a strong ETag or Last-Modified validator. If a server ignores ranges,
the file restarts safely. Credentials are stripped from cross-origin redirects.
A completed file is published only after advertised-size and optional SHA-256
checks. Existing destinations require a supplied matching checksum for reuse.

A per-destination exclusive lock prevents simultaneous downloads. A crash can
leave `.download.lock`; after verifying that no process is using that destination,
remove that lock before resuming. Keep `.part` and `.part.json` together. A stale
or corrupt partial can be restarted with `resume=False`. The small state file
stores a request hash and validators, never API keys or signed URLs.

## Selective local import

```python
from uspto_client import Library, Release, Selection

with Library("data") as library:
    result = library.import_file(
        "patent-filewrapper-delta-json-20260904.zip",
        release=Release("PTFWPRD", "patent-filewrapper-delta-json-20260904.zip",
                        "2026-09-04", "2026-09-04", "delta"),
        selection=Selection(kinds=("reexam", "reissue"), applications=("12345678",)),
        max_expanded_bytes=10_000_000_000,
    )
```

Selections are a union of proceeding types, explicit applications, patents, and
trials. An empty `kinds=()` allows identifier-only selection. `all_records=True`
is an explicit full import. Assignment archive imports require company names,
patents, applications, or `all_records=True`; proceeding-type selection alone
cannot classify assignment records. These filters reduce retained data and
parsing work downstream, not the required download of a mixed archive.

Parsers accept ZIP members, gzip, and uncompressed inputs. PFW supports the
`patentFileWrapperDataBag` envelope, arrays, and individual/concatenated JSON
objects. PADX uses the official `us-patent-assignments` structure, including an
explicit no-data marker. XML entities/external references are prohibited; the
ordinary embedded PADX DTD is allowed. ZIP members are read without extracting
paths into the filesystem. JSON/XML parsing retains one record at a time.

The normalized selection, parser version, release identity, and content hash
form import identity. Newer sparse observations update supplied fields while
preserving absent fields. Older observations cannot replace newer current values.
Equal source-time conflicts retain evidence and mark the import incomplete;
unknown fields remain in raw observations. Records without a usable source
modification time need a verified `source_as_of` on their Release to order updates.
Do not substitute a snapshot's historical filing-year range for its extraction date.

## Coverage and limits

`coverage` reports missing imported daily dates for the exact filter. A parsed
file is not a claim that the entire historical universe has been collected.
Snapshots are tracked individually; 0.4 does not infer global snapshot coverage
or silently bridge missing delta days. An incomplete parse or unrecognized
record does not establish coverage. Date-window discovery and live inventory
refreshes remain necessary for selected dockets and PDFs.

This release was validated with synthetic archives and published schemas.
No large production snapshot was ingested. Before a production backfill, run a
bounded sample, verify record counts/types and timestamp semantics, choose disk
budgets, and establish baseline/delta cutoff coverage explicitly.

Official references:
- https://data.uspto.gov/apis/bulk-data/search
- https://data.uspto.gov/apis/bulk-data/product
- https://www.uspto.gov/learning-and-resources/xml-resources
- https://data.uspto.gov/documents/documents/xml-resources/PADX-File-Description-v2_Hague.doc
