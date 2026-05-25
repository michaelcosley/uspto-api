# Implementation Progress

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
- Response models currently validate common wrappers and preserve extra fields;
  deeper nested response models should be expanded after the missing USPTO
  OpenAPI component YAML files are obtained.
