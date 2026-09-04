# Implementation Progress

## 2026-09-04

### Completed

- Added `AssignmentCenterClient` as a separate experimental public-service
  client with patent searches, advanced criteria, reel/frame lookup, the
  advertised export route, and recorded-document downloads.
- Live-verified patent-number search and reel/frame lookup and normalized the
  service's object-for-one/list-for-many response behavior.
- Added Patent File Wrapper assignment query helpers and PTAB counsel/party
  query helpers.
- Added configurable default pacing (10 ms calls, 50 ms downloads) shared by
  matching clients in one process.
- Added opt-in 429, 5xx, and transport retries with bounded backoff.
- Added documentation, offline tests, CI, and the `use-uspto-client` skill.

### Known service limitation

- The public Assignment Center frontend advertises its patent export route, but
  that route returned HTTP 404 during live verification. The wrapper preserves
  the typed error and is documented as experimental.
- Assignment Center recordations do not themselves determine current legal
  ownership; that classification remains deliberately outside this client.

## 2026-08-13

### Completed

- Added `client.ptab.trials` for all documented AIA trial proceeding,
  document, and decision search, export, and record-lookup operations.
- Added PTAB document downloads using returned `fileDownloadURI` metadata.
- Added tolerant typed proceeding, party, trial metadata, document, and
  decision models.
- Accepted both decision bag names present in USPTO documentation and live
  responses.
- Added PTAB search field constants and filter helpers.
- Added content-disposition export filenames and cross-origin API-key
  protection for downloads and redirects.
- Corrected the bad Search Proceedings documentation capture and added a
  self-contained implemented OpenAPI contract.
- Added representative fixtures, mocked tests, and opt-in live PTAB tests.

### Live verification

- Verified proceedings GET/POST search and trial-number lookup.
- Verified document and decision search, trial-number lookup, and
  document-identifier lookup.
- Verified JSON and CSV search exports.
- Verified a byte-range PTAB file request returned a PDF header.

## 2026-05-20

### Completed

- Created the initial phased implementation plan.
- Added project packaging, README, environment example, ignore rules, and
  development conventions.
- Added internal LLM reference documentation.
- Added API reference for initial patent application endpoints.
- Added a sync `UsptoClient` foundation with `client.applications.*`.
- Added Pydantic request/response models with `extra="allow"`.
- Added typed API exceptions.
- Added in-process request serialization by API key.
- Added conservative 429 retry behavior, disabled by default.
- Added normal-test network blocking and live-test opt-in guard.
- Added sanitized fixture capture helper and capture script.
- Added mocked endpoint, error, registry, model, and rate-limit tests.
- Verified live API calls for reexam control number `90/016,176`, normalized as
  application number `90016176`.
- Captured real USPTO response fixtures under
  `tests/fixtures/uspto/reexam_90016176/`.
- Added non-live tests that parse the captured reexam fixtures.
- Expanded models for observed live keys: `documentBag`, `patentdata`, and
  `statusCodeBag`.
- Added `docs/developer-usage-guide.md` for consuming projects.
- Added `client.applications.download_document(...)` for PDF document
  downloads, including byte-only, exact-file, and directory output modes.
- Verified live BIB PDF document download for `90016176` /
  `MO1EEHMN101X233`; USPTO returned a redirect, which the client now follows.
- Added metadata-based document filename generation, packaged document-code
  shorthand mapping, custom mapping-path support, custom filename templates, and
  automatic conflict suffixes.
- Added typed search payload helpers for filters, range filters, pagination,
  and sort clauses.
- Added `full-uspto-api-syntax-doc.txt` as the local source for search payload
  syntax and corrected `RangeFilter` to use `field`, `valueFrom`, and
  `valueTo`.
- Added known search option constants and helper functions for application type,
  publication category, business entity status, and filing-date descending sort.

### Verification

- Created local `.venv/` and installed the project with development extras.
- `pytest`: 47 passed, 1 live test skipped.
- `pytest -m "not live"`: 47 passed, 1 live test deselected.
- `ruff check .`: passed.
- `black --check .`: passed.
- `mypy src`: passed.

### Known Gaps

- Live tests are harnessed but not expected to run without a real
  `USPTO_API_KEY`.
- Patent File Wrapper nested response models remain intentionally loose.
- PTAB appeals and interferences remain outside the implemented namespace.
