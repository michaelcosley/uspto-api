# Assignment Center Public Patent API

## Status and boundary

`AssignmentCenterClient` wraps the public patent search service used by the
official [USPTO Assignment Center](https://assignmentcenter.uspto.gov/). It is
kept separate from `UsptoClient` because it uses a different origin and does
not require or receive the Open Data Portal API key.

The client is marked experimental. The endpoints are public and live, but the
USPTO does not currently publish the same stable, versioned API contract for
them that it publishes for Open Data Portal APIs. Response models allow extra
fields and normalize observed object/list inconsistencies.

## Basic searches

```python
from uspto_client import AssignmentCenterClient

with AssignmentCenterClient() as client:
    exact = client.search_exact_assignee("EXAMPLE COMPANY, INC.")
    partial = client.search_partial_assignee("EXAMPLE COMPANY")

print(exact.total_rows)
for result in exact.results:
    for record in result.assignment_records:
        print(record.reel_frame, record.recordation_date, record.conveyance)
    for patent in result.properties:
        print(patent.patent_number, patent.application_number)
```

Generic single-field search is available for patent, publication, application,
party, correspondent, and reel/frame fields:

```python
from uspto_client import AssignmentCenterClient, PATENT_NUMBER_SEARCH

with AssignmentCenterClient() as client:
    response = client.search_patents(
        "11111279",
        search_by=PATENT_NUMBER_SEARCH,
    )
```

Public search constants include:

- `APPLICATION_NUMBER_SEARCH`
- `PATENT_NUMBER_SEARCH`
- `PUBLICATION_NUMBER_SEARCH`
- `REEL_FRAME_SEARCH`
- `EXACT_ASSIGNEE_NAME_SEARCH` and `PARTIAL_ASSIGNEE_NAME_SEARCH`
- `EXACT_ASSIGNOR_NAME_SEARCH` and `PARTIAL_ASSIGNOR_NAME_SEARCH`
- `EXACT_CORRESPONDENT_NAME_SEARCH` and
  `PARTIAL_CORRESPONDENT_NAME_SEARCH`

## Advanced search

```python
from uspto_client import (
    AssignmentCenterClient,
    AssignmentDataFilter,
    AssignmentSearchCriterion,
)

criteria = [
    AssignmentSearchCriterion(
        property="EXAMPLE COMPANY, INC.",
        search_by="exactAssigneeName",
        match_type="exact",
        order=1,
        relation="AND",
    )
]

with AssignmentCenterClient() as client:
    response = client.advanced_search(
        criteria,
        data_filter=AssignmentDataFilter(rows_per_page=100, current_page=1),
    )
```

The public service may return all matching records in one response and report
`backendPagination=false`; callers should honor the returned shape rather than
assuming `rowsPerPage` is always enforced.

## Reel/frame and document images

```python
with AssignmentCenterClient() as client:
    details = client.get_reel_frame(46387, 180)
    document = client.download_recordation(
        46387,
        180,
        output_path="downloads/",
    )
```

`download_recordation` returns a `DocumentDownload`, matching the other client
download methods. If `output_path` is omitted, the bytes are returned without
writing a file.

## Export route

The deployed public web application advertises
`/ipas/search/api/v3/public/patent/exportPublicPatentData`, and
`export_patent_data(...)` mirrors its request contract, including the required
row-count criterion (1-1000). During live verification on September 4, 2026,
the advertised route itself returned HTTP 404. The method therefore remains
experimental and will surface a typed `UsptoNotFoundError` while that service
route is unavailable.

## What this client does not decide

The Assignment Center records documents and transactions; it does not provide
a legal conclusion about present title. Results may include assignments,
security interests, releases, mergers, name changes, address changes,
corrections, nunc pro tunc instruments, and other recorded events. A search for
an assignee can also return other transactions in the matched property's chain.

Accordingly, this library intentionally does not label a party as the current
owner, discard non-assignment conveyances, resolve corporate-name variants, or
decide whether a later transaction transferred title. Those are higher-level
analysis functions for a consuming project, with review of the actual recorded
documents where necessary.

## Optional local portfolio index

Since 0.4, the separate `Library` interface can retain assignment observations,
index company/patent relationships, screen current-assignee candidates and record
first-detected proceedings. See [company-monitoring.md](company-monitoring.md).
These functions do not change the low-level AssignmentCenterClient contract or
turn a recorded transaction into a legal title conclusion.

USPTO announced that Assignment Center patent export searches moved to ODP on
July 24, 2026. Existing experimental export behavior is retained for compatibility;
use ODP bulk products or targeted searches for the new library workflow.
Source: https://www.uspto.gov/system-status/20260707-assignment-center-patent-search-service-alert
