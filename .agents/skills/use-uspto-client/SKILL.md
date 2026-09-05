---
name: use-uspto-client
description: Use the reusable Python uspto-client package to query USPTO Patent File Wrapper application data, PTAB AIA trial proceedings and filings, or public Assignment Center patent recordations. Trigger when a task needs these APIs, their typed models, search helpers, downloads, pacing, retries, or fixture-backed tests; use the optional Library for evidence-backed assignment candidates and watchlists, without presenting legal title conclusions.
---

# Use USPTO Client

Use the low-level API independently, or the opt-in portable Library for shared
storage, bulk ingestion, readable documents and company watchlists. Keep legal
title conclusions, case-specific reviews and docket deadlines in the consumer.

## Choose the service

- Use `UsptoClient(api_key=...)` for Patent File Wrapper and PTAB AIA trial
  Open Data Portal APIs.
- Use `AssignmentCenterClient()` for the public Assignment Center patent
  search service. It is separately hosted and must not receive the Open Data
  Portal API key.
- Do not add trademark calls; they are outside this package's scope.

Read `../../../docs/developer-usage-guide.md` for examples and
`../../../docs/api-reference.md` for the method inventory. For Assignment
Center semantics and limitations, read `../../../docs/assignment-center.md`.

## Search safely

- Prefer the exported query helpers for nested field paths, including
  `assignee_name_query`, `patent_owner_counsel_query`, and
  `petitioner_counsel_query`.
- Preserve HTTP 404 behavior. Some PTAB searches use 404 for no matches; catch
  `UsptoNotFoundError` in the consuming workflow only when empty-result
  semantics are desired there.
- Treat Assignment Center results as recorded transactions, not proof of
  current ownership. Preserve conveyance text and the complete chain for later
  classification.
- Expect Assignment Center object/list inconsistencies; use `response.results`
  and `result.assignment_records`, which normalize them.

## Pace, retry, and download

Default minimum intervals are 10 ms for ordinary calls and 50 ms for serial
downloads. Configure them with `PacingConfig`. Retries remain opt-in through
`RetryConfig`; use bounded attempts and honor typed failures.

Never print, persist, or forward `USPTO_API_KEY`. The Open Data Portal client
removes the key on cross-origin download redirects, and Assignment Center uses
a separate unauthenticated client.

## Test changes

Normal tests must use `httpx.MockTransport` or saved fixtures and must not open
external sockets. Mark intentional live checks `live` and require
`--live-uspto`. Before completion, run:

```powershell
pytest
ruff check .
black --check .
mypy src
```

## Portable library workflows

Read [the library guide](../../../docs/portable-library.md) for setup and
[company monitoring](../../../docs/company-monitoring.md) for assignment matching.
Bulk support is documented in [bulk ingestion](../../../docs/bulk-ingestion.md).

- Initialization does not authorize a production backfill or consumer migration.
- Preview bulk file sizes and choose a selection and byte budget before execution.
- Treat weekly PFW products as snapshots, daily products as deltas; check gaps.
- Distinguish recorded assignees, ownership candidates and reviewed title findings.
- Match reviewed company aliases and preserve first-detected versus first-seen times.
- Read-only extractors receive scratch PDFs; originals are never OCRed in place.
- Full production archive compatibility and live discovery semantics require a
  bounded pilot before a broad backfill or monitoring service is deployed.
