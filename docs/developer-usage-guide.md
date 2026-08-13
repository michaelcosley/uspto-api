# Developer Usage Guide

This guide is for projects that want to use `uspto-client` as a dependency.

## Install From A Local Checkout

From another project, install this client directly from the local checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -e C:\Users\micha\Projects\uspto-client
```

If the consuming project uses a `requirements.txt`, add:

```text
-e C:\Users\micha\Projects\uspto-client
```

For a non-editable install:

```powershell
.\.venv\Scripts\python.exe -m pip install C:\Users\micha\Projects\uspto-client
```

## Configure The API Key

The client expects an explicit API key. It does not automatically load `.env`
files.

In the consuming project, store the key however that project normally manages
secrets. For local scripts, a `.env` file is fine:

```text
USPTO_API_KEY=your-key-here
```

Then load it in application code:

```python
import os

from dotenv import load_dotenv
from uspto_client import UsptoClient

load_dotenv()

client = UsptoClient(api_key=os.environ["USPTO_API_KEY"])
```

## Basic Usage

USPTO reexam control numbers should be passed without punctuation. For example,
Control No. `90/016,176` becomes `90016176`.

```python
from uspto_client import UsptoClient

client = UsptoClient(api_key="your-api-key")

metadata = client.applications.get_metadata("90016176")
record = metadata.patent_file_wrapper_data_bag[0]

print(record["applicationNumberText"])
print(record["applicationMetaData"]["applicationTypeLabelName"])
```

## Search Payloads And Filters

For structured POST searches, you can pass a raw dictionary:

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

Or use typed request models:

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

The downloaded USPTO syntax reference is
`docs/patent-file-wrapper/full-uspto-api-syntax-doc.txt` in the client repo.
The searchable field reference is `docs/patent-file-wrapper/search.txt`.

Common Patent File Wrapper search options are available as constants and helper
functions:

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

Current known values:

- Application types: `Utility`, `Provisional`, `PCT`, `Design`, `Plant`,
  `Re-Issue`, `Re-Examination`, `Supplemental Examination`, `Regular`
- Publication categories: `Pre-Grant Publications - PGPub`, `Granted/Issued`,
  `Other`
- Business entity statuses: `Regular Undiscounted`, `Small`, `Micro`

## Available Application Methods

Initial patent application methods live under `client.applications`:

```python
client.applications.search(q="applicationNumberText:90016176", limit=1)
client.applications.download_search_results(
    q="applicationNumberText:90016176",
    limit=1,
    format="json",
)
client.applications.get("90016176")
client.applications.get_metadata("90016176")
client.applications.get_adjustment("90016176")
client.applications.get_assignment("90016176")
client.applications.get_attorney("90016176")
client.applications.get_continuity("90016176")
client.applications.get_foreign_priority("90016176")
client.applications.get_transactions("90016176")
client.applications.get_documents("90016176")
client.applications.get_documents("90016176", document_codes="BIB")
client.applications.download_document("90016176", "MO1EEHMN101X233")
client.applications.get_associated_documents("90016176")
client.applications.search_status_codes(q="412", limit=1)
```

See `docs/api-reference.md` in this repository for endpoint paths, source docs,
and response-shape notes.

## PTAB AIA Trial Proceedings

PTAB trial operations are grouped under `client.ptab.trials`. Public trial
materials include IPR, PGR, CBM, and DER proceedings from September 2012
forward.

Retrieve one proceeding and its documents and decisions:

```python
proceeding = client.ptab.trials.get_proceeding("IPR2024-00001")
documents = client.ptab.trials.get_documents("IPR2024-00001")
decisions = client.ptab.trials.get_decisions("IPR2024-00001")

print(proceeding.proceedings[0].trial_number)
print(documents.documents[0].document_data.document_title_text)
print(decisions.decisions[0].decision_data.decision_type_category)
```

Search proceedings, documents, or decisions with GET parameters:

```python
proceedings = client.ptab.trials.search_proceedings(
    q="trialMetaData.trialTypeCode:IPR",
    limit=25,
)
documents = client.ptab.trials.search_documents(
    q="trialNumber:IPR2024-00001",
    limit=25,
)
decisions = client.ptab.trials.search_decisions(
    q="decisionData.decisionTypeCategory:\"Final Written Decision\"",
    limit=25,
)
```

The same `SearchRequest`, `SearchFilter`, `RangeFilter`, `SearchSort`, and
`Pagination` models used for Patent File Wrapper searches can be passed as a
structured POST body.

Common PTAB filter helpers are available without restricting future values:

```python
from uspto_client import Pagination, SearchRequest, trial_status_filter, trial_type_filter

request = SearchRequest(
    filters=[
        trial_type_filter("IPR", "PGR"),
        trial_status_filter("Instituted"),
    ],
    pagination=Pagination(offset=0, limit=25),
)

client.ptab.trials.search_proceedings(body=request)
```

Available trial methods:

```python
client.ptab.trials.search_proceedings(...)
client.ptab.trials.download_proceedings_search_results(...)
client.ptab.trials.get_proceeding(trial_number)
client.ptab.trials.search_documents(...)
client.ptab.trials.download_documents_search_results(...)
client.ptab.trials.get_documents(trial_number)
client.ptab.trials.get_document(document_identifier)
client.ptab.trials.search_decisions(...)
client.ptab.trials.download_decisions_search_results(...)
client.ptab.trials.get_decisions(trial_number)
client.ptab.trials.get_decision(document_identifier)
client.ptab.trials.download_document(document)
```

Search-result downloads use the USPTO `Content-Disposition` filename and return
the same byte/path metadata as application-document downloads:

```python
export = client.ptab.trials.download_proceedings_search_results(
    q="trialNumber:IPR2024-00001",
    format="csv",
    output_path="exports/",
)
```

Download a trial PDF directly from a returned record:

```python
documents = client.ptab.trials.get_documents("IPR2024-00001")
download = client.ptab.trials.download_document(
    documents.documents[0],
    output_path="downloads/",
)
```

The API key is sent only to the configured USPTO API origin. If older metadata
contains a download URL on another host, the client follows it without
forwarding the key.

## Response Models

Methods return Pydantic v2 models. Models allow extra fields because USPTO
responses can include undocumented keys.

Useful common fields:

```python
response.count
response.request_identifier
response.raw_data
```

Patent application responses commonly expose:

```python
response.patent_file_wrapper_data_bag
response.document_bag
```

Search download responses expose:

```python
response.patent_data
```

Status-code responses may expose:

```python
response.status_code_bag
response.status_code_data_bag
```

Document downloads return:

```python
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/bib-sheet.pdf",
)

download.content
download.filename
download.path
download.content_type
download.status_code
```

Filename behavior:

- No `output_path`: returns bytes and writes no file.
- `output_path="downloads/bib-sheet.pdf"`: writes exactly that file.
- `output_path="downloads/"`: writes `MO1EEHMN101X233.pdf`.
- `output_path="downloads/", filename="bib-sheet.pdf"`: writes that filename
  inside the directory.

Generated metadata-based filenames:

```python
documents = client.applications.get_documents("90016176")
bib = documents.document_bag[2]

client.applications.download_document(
    bib["applicationNumberText"],
    bib["documentIdentifier"],
    output_path="downloads/",
    document=bib,
    filename_format="application_date_description",
)
```

Supported `filename_format` values:

- `document_id`
- `date_description`
- `application_date_description`
- `date_patent_description`
- `application_date_patent_description`

For custom ordering:

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

Conflicts are handled automatically: if a filename already exists, the client
writes `filename (2).pdf`, then `filename (3).pdf`, etc. Pass
`avoid_filename_conflicts=False` to overwrite the exact target path.

The default document-code mapping is packaged with the library. To use your own
updated CSV, pass:

```python
doc_code_mapping_path="path/to/doc_code_mapping.csv"
```

## Error Handling

The client raises typed exceptions:

```python
from uspto_client import UsptoAPIError, UsptoRateLimitError

try:
    response = client.applications.get_metadata("90016176")
except UsptoRateLimitError as exc:
    print("Rate limited", exc.status_code, exc.message)
except UsptoAPIError as exc:
    print("USPTO error", exc.status_code, exc.message)
```

Exception objects include:

```python
exc.status_code
exc.message
exc.response_body
exc.request_identifier
```

## Rate Limits

USPTO documents a burst limit of `1` request per API key. This client serializes
requests by API key in the current Python process. If multiple projects or
processes share the same API key, they can still collide externally, so avoid
running live API jobs in parallel with the same key.

HTTP 429 responses raise `UsptoRateLimitError` by default. Automatic retry is
disabled unless configured explicitly.

## Testing In A Consuming Project

For unit tests in another project, do not call USPTO. Mock the client boundary:

```python
from unittest.mock import Mock

client = Mock()
client.applications.get_metadata.return_value.patent_file_wrapper_data_bag = [
    {
        "applicationNumberText": "90016176",
        "applicationMetaData": {"applicationTypeLabelName": "Re-Examination"},
    }
]
```

If you want fixture-backed tests, copy JSON fixtures from:

```text
tests/fixtures/uspto/reexam_90016176/
```

Those fixtures were captured from live USPTO responses and are safe for normal
non-live tests.

## Live Fixture Capture

From this repository, capture a sanitized fixture intentionally:

```powershell
.\.venv\Scripts\python.exe scripts\capture_fixture.py get-metadata 90016176 tests\fixtures\live\get_metadata_90016176.json
```

Live calls require `USPTO_API_KEY` in the environment or `.env`.

## Current Limitations

- The client is sync-only.
- Supported production families are Patent File Wrapper and PTAB AIA trials.
- PTAB appeals and interferences are not yet exposed as client namespaces.
- Trademark APIs are intentionally out of scope.
- Document download supports file URLs exposed by USPTO document metadata.
- Nested response models are still intentionally loose until more real USPTO
  response shapes are collected.
