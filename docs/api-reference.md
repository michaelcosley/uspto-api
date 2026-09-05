# API Reference

## Scope

Supported API families are USPTO Patent File Wrapper / patent application data,
PTAB AIA trial proceedings, and the experimental public Assignment Center
patent search service. Trademark APIs are out of scope. PTAB appeals and
interferences remain future work.

## Authentication

Open Data Portal requests require the `X-API-KEY` header. Create a client with
an explicit key:

```python
client = UsptoClient(api_key="...")
```

`AssignmentCenterClient` uses a separate official public service and does not
accept or send that API key.

## Rate Limits

USPTO documents a burst limit of `1` request per API key and warns against
parallel calls with the same key. The client serializes requests by API key in
the current process and applies default minimum intervals of 10 ms for ordinary
calls and 50 ms for downloads. HTTP 429 responses raise
`UsptoRateLimitError`; all retries are disabled by default. See
`docs/transport-and-retries.md`.

## Model Policy

Request and response objects use Pydantic v2. Models allow undocumented extra
fields so the client can tolerate additive USPTO response changes.

## Patent Application Endpoints

| Method | HTTP | Path | Status | Source |
| --- | --- | --- | --- | --- |
| `client.applications.search(...)` | GET/POST | `/api/v1/patent/applications/search` | Implemented | `docs/patent-file-wrapper/search.txt` |
| `client.applications.download_search_results(...)` | GET/POST | `/api/v1/patent/applications/search/download` | Implemented | `docs/uspto-swagger-api.yaml` |
| `client.applications.get(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}` | Implemented | `docs/uspto-swagger-api.yaml` |
| `client.applications.get_metadata(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/meta-data` | Implemented | `docs/patent-file-wrapper/application-data.txt` |
| `client.applications.get_adjustment(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/adjustment` | Implemented | `docs/patent-file-wrapper/patent-term-adjustment.txt` |
| `client.applications.get_assignment(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/assignment` | Implemented | `docs/patent-file-wrapper/assignments.txt` |
| `client.applications.get_attorney(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/attorney` | Implemented | `docs/patent-file-wrapper/attorney-address.txt` |
| `client.applications.get_continuity(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/continuity` | Implemented | `docs/patent-file-wrapper/continuity.txt` |
| `client.applications.get_foreign_priority(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/foreign-priority` | Implemented | `docs/patent-file-wrapper/foreign-priority.txt` |
| `client.applications.get_transactions(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/transactions` | Implemented | `docs/patent-file-wrapper/transactions.txt` |
| `client.applications.get_documents(application_number, ...)` | GET | `/api/v1/patent/applications/{applicationNumberText}/documents` | Implemented | `docs/patent-file-wrapper/documents.txt` |
| `client.applications.download_document(application_number, document_identifier, ...)` | GET | `/api/v1/download/applications/{applicationNumberText}/{documentIdentifier}.pdf` | Implemented | Live document metadata response |
| `client.applications.get_associated_documents(application_number)` | GET | `/api/v1/patent/applications/{applicationNumberText}/associated-documents` | Implemented | `docs/uspto-swagger-api.yaml` |
| `client.applications.search_status_codes(...)` | GET/POST | `/api/v1/patent/status-codes` | Implemented | `docs/uspto-swagger-api.yaml` |

## PTAB AIA Trial Endpoints

| Method | HTTP | Path |
| --- | --- | --- |
| `client.ptab.trials.search_proceedings(...)` | GET/POST | `/api/v1/patent/trials/proceedings/search` |
| `client.ptab.trials.download_proceedings_search_results(...)` | GET | `/api/v1/patent/trials/proceedings/search/download` |
| `client.ptab.trials.get_proceeding(trial_number)` | GET | `/api/v1/patent/trials/proceedings/{trialNumber}` |
| `client.ptab.trials.search_documents(...)` | GET/POST | `/api/v1/patent/trials/documents/search` |
| `client.ptab.trials.download_documents_search_results(...)` | GET | `/api/v1/patent/trials/documents/search/download` |
| `client.ptab.trials.get_documents(trial_number)` | GET | `/api/v1/patent/trials/{trialNumber}/documents` |
| `client.ptab.trials.get_document(document_identifier)` | GET | `/api/v1/patent/trials/documents/{documentIdentifier}` |
| `client.ptab.trials.search_decisions(...)` | GET/POST | `/api/v1/patent/trials/decisions/search` |
| `client.ptab.trials.download_decisions_search_results(...)` | GET | `/api/v1/patent/trials/decisions/search/download` |
| `client.ptab.trials.get_decisions(trial_number)` | GET | `/api/v1/patent/trials/{trialNumber}/decisions` |
| `client.ptab.trials.get_decision(document_identifier)` | GET | `/api/v1/patent/trials/decisions/{documentIdentifier}` |

The implementation covers IPR, PGR, CBM, and DER trial data without enforcing
a closed trial-type enum. Search endpoints support the shared USPTO GET syntax
and structured POST bodies.

### Verified PTAB response behavior

Live verification on August 13, 2026 established the following response
contracts:

- Proceedings use `patentTrialProceedingDataBag`.
- Documents use `patentTrialDocumentDataBag`.
- Decisions also currently use `patentTrialDocumentDataBag`, although one USPTO
  example uses `patentTrialDecisionDataBag`. `TrialDecisionResponse` accepts
  both and serializes to the live form.
- JSON search exports use `patentTrialData`; export methods therefore return
  attachment bytes rather than a normal search response model.
- Party bags and nested fields vary by trial type and record. PTAB models allow
  additive fields and make non-universal bags optional.
- Trial document `fileDownloadURI` values currently point to authenticated
  `api.uspto.gov` file endpoints and can return PDFs as
  `binary/octet-stream`.

Representative non-live fixtures are under
`tests/fixtures/ptab_ipr2024_00001/`. The corrected human-readable endpoint
capture is `docs/ptab-trials/search-proceedings.txt`; the self-contained
implemented contract is `docs/ptab-trials/openapi.yaml`.

## Assignment Center Public Patent Endpoints

These methods are exposed on a separate `AssignmentCenterClient` and are marked
experimental because the public web application API does not have a published,
versioned Open Data Portal contract.

| Method | HTTP | Path | Live status on 2026-09-04 |
| --- | --- | --- | --- |
| `search_patents(...)` / assignee conveniences | POST | `/ipas/search/api/v3/public/search/patent` | Verified |
| `advanced_search(...)` | POST | `/ipas/search/api/v3/public/search/patent` | Contract verified from official UI; parsing covered offline |
| `get_reel_frame(...)` | POST | `/ipas/search/api/v3/public/search/patent` | Verified |
| `download_recordation(...)` | GET | `/ipas/search/api/v3/public/download/patent/{reel}/{frame}` | Endpoint live; interrupted-transfer retries are opt-in |
| `export_patent_data(...)` | POST | `/ipas/search/api/v3/public/patent/exportPublicPatentData` | Official UI advertises route; route returned HTTP 404 |

See `docs/assignment-center.md` for request examples, response normalization,
and the important distinction between recorded transactions and current title.

## Search Request Payloads

Search endpoints support simple GET query parameters and structured POST JSON
payloads. The local Swagger file references the full shared schema through
`odp-common-base.yaml`, which is not currently present in this repository, so
the typed models cover the observed/common payload shape and allow extra fields.

Raw body style:

```python
client.applications.search(
    body={
        "q": "9198117",
        "filters": [
            {
                "name": "applicationMetaData.applicationTypeLabelName",
                "value": ["Re-Examination"],
            }
        ],
        "rangeFilters": [
            {
                "field": "applicationMetaData.grantDate",
                "valueFrom": "2010-08-04",
                "valueTo": "2022-08-04",
            }
        ],
        "pagination": {"offset": 0, "limit": 25},
        "sort": [
            {
                "field": "applicationMetaData.filingDate",
                "order": "Desc",
            }
        ],
    }
)
```

Typed model style:

```python
from uspto_client import Pagination, RangeFilter, SearchFilter, SearchRequest, SearchSort

request = SearchRequest(
    q="9198117",
    filters=[
        SearchFilter(
            name="applicationMetaData.applicationTypeLabelName",
            value=["Re-Examination"],
        )
    ],
    range_filters=[
        RangeFilter(
            field="applicationMetaData.grantDate",
            value_from="2010-08-04",
            value_to="2022-08-04",
        )
    ],
    pagination=Pagination(offset=0, limit=25),
    sort=[SearchSort(field="applicationMetaData.filingDate", order="Desc")],
)

client.applications.search(body=request)
```

Supported typed request helpers:

- `SearchRequest`
- `SearchFilter`
- `RangeFilter`
- `SearchSort`
- `Pagination`

Known option helpers are also available for commonly used Patent File Wrapper
filters:

```python
from uspto_client import (
    APPLICATION_TYPE_LABEL_NAMES,
    BUSINESS_ENTITY_STATUS_CATEGORIES,
    PUBLICATION_CATEGORIES,
    Pagination,
    SearchRequest,
    application_type_filter,
    business_entity_status_filter,
    filing_date_sort_desc,
    publication_category_filter,
)

request = SearchRequest(
    q="",
    filters=[
        application_type_filter(*APPLICATION_TYPE_LABEL_NAMES),
        publication_category_filter(*PUBLICATION_CATEGORIES),
        business_entity_status_filter(*BUSINESS_ENTITY_STATUS_CATEGORIES),
    ],
    range_filters=[],
    pagination=Pagination(offset=0, limit=25),
    sort=[filing_date_sort_desc()],
)

client.applications.search(body=request)
```

Current documented option values:

| Field | Values |
| --- | --- |
| `applicationMetaData.applicationTypeLabelName` | `Utility`, `Provisional`, `PCT`, `Design`, `Plant`, `Re-Issue`, `Re-Examination`, `Supplemental Examination`, `Regular` |
| `applicationMetaData.publicationCategoryBag` | `Pre-Grant Publications - PGPub`, `Granted/Issued`, `Other` |
| `applicationMetaData.entityStatusData.businessEntityStatusCategory` | `Regular Undiscounted`, `Small`, `Micro` |

Search syntax and payload rules are documented locally at
`docs/patent-file-wrapper/full-uspto-api-syntax-doc.txt`. Known searchable
fields come from `docs/patent-file-wrapper/search.txt`, which lists the large
set of response/search fields, including nested names such as
`applicationMetaData.applicationTypeLabelName` and
`applicationMetaData.filingDate`.

## Document Downloads

Document metadata from `get_documents(...)` includes document identifiers and,
where available, a USPTO `downloadUrl`. The client exposes PDF download through:

```python
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
)
```

If `output_path` is omitted, no file is written and `download.content` contains
the bytes. The default filename is `{document_identifier}.pdf`.

Write to an exact file path:

```python
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/bib-sheet.pdf",
)
```

Write into a directory using the default filename:

```python
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/",
)
```

Write into a directory using a custom filename:

```python
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/",
    filename="reexam-bib-sheet.pdf",
)
```

The returned `DocumentDownload` model includes `content`, `filename`, `path`,
`content_type`, and `status_code`.

USPTO document downloads redirect to short-lived signed PDF URLs. The client
follows that redirect automatically.

### Generated Document Filenames

`download_document(...)` can generate filenames from document metadata returned
by `get_documents(...)`. Pass the document dictionary and choose a built-in
format:

```python
documents = client.applications.get_documents("90016176")
bib = documents.document_bag[2]

download = client.applications.download_document(
    bib["applicationNumberText"],
    bib["documentIdentifier"],
    output_path="downloads/",
    document=bib,
    filename_format="application_date_description",
)
```

Built-in formats:

- `document_id`: `MO1EEHMN101X233.pdf`
- `date_description`: `2026-04-16 Bibliographic Data.pdf`
- `application_date_description`: `90016176 2026-04-16 Bibliographic Data.pdf`
- `date_patent_description`: `2026-04-16 ('279) Bibliographic Data.pdf`
- `application_date_patent_description`:
  `90016176 2026-04-16 ('279) Bibliographic Data.pdf`

For patent-number formats, pass `patent_number="11111279"` or similar.

For custom ordering, pass a template:

```python
client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/",
    document=bib,
    patent_number="11111279",
    filename_template="{app_no} {date} {patent_last_three} {short_desc}",
)
```

Available template fields: `app_no`, `application_number`, `date`,
`patent_last_three`, `short_desc`, `description`, `doc_code`,
`document_code`, `document_id`, and `document_identifier`.

When writing to disk, filename conflicts are avoided by default with ` (2)`,
` (3)`, and so on before the extension. Set
`avoid_filename_conflicts=False` to overwrite the exact target path.

Document code shorthand comes from packaged data at
`src/uspto_client/data/doc_code_mapping.csv`. To use an updated mapping without
changing the package, pass `doc_code_mapping_path="path/to/doc_code_mapping.csv"`.

## Live Fixture Notes

Initial live fixtures were captured for reexam control number `90/016,176`,
normalized as application number `90016176`, under
`tests/fixtures/uspto/reexam_90016176/`.

Observed response-shape details:

- Application search and most application-detail endpoints return
  `patentFileWrapperDataBag`.
- Search-result download returns lowercase `patentdata`.
- Document lookup returns `documentBag`; filtered `documentCodes=BIB` returned
  one Bibliographic Data Sheet with a PDF `downloadUrl`.
- Live BIB PDF download for `MO1EEHMN101X233` followed the USPTO redirect and
  returned `35,697` bytes starting with the `%PDF` header.
- Status-code search for status `412` returned `statusCodeBag`.

## Future Documentation Work

The aggregate USPTO Swagger capture still references separate appeal and
interference component files that are outside the current client scope. Add
those contracts when those PTAB namespaces are implemented.

## Bulk and portable library (0.4)

`client.bulk.search`, `get_product`, `iter_files`, and `download_file` expose ODP
product catalogs and streamed file downloads.

`Library`, `Selection`, `Release`, and `DocumentSpec` are exported from
`uspto_client`. See [portable-library.md](portable-library.md) for the library
API and CLI, including collection, import, text indexing, backups and watchlists.
