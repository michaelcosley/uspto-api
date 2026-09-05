# uspto-client

`uspto-client` is a pure-Python, sync-first client library for USPTO Patent
File Wrapper and Patent Trial and Appeal Board APIs. It also includes a
separate experimental client for the public Assignment Center patent search
service. Trademark APIs are out of scope.

## Portable data library

Version 0.4 adds an opt-in SQLite library with readable IPR/reexamination PDFs,
selective PFW snapshot/delta imports, assignment indexing, company watchlists,
first-detected proceeding matches, and page-text search.

```console
python -m pip install "uspto-client[library]"
uspto-library --root data init
```

Start with the [portable library guide](docs/portable-library.md),
[bulk ingestion guide](docs/bulk-ingestion.md), or
[company monitoring workflow](docs/company-monitoring.md).
Existing API calls remain independent of local storage. Initialization performs
no network calls, bulk downloads, or migrations of another project's data.

## Status

This project is in initial implementation. The public API is being built around
domain namespaces:

```python
from uspto_client import UsptoClient

client = UsptoClient(api_key="your-api-key")
result = client.applications.get_metadata("16330077")
download = client.applications.download_document(
    "90016176",
    "MO1EEHMN101X233",
    output_path="downloads/bib-sheet.pdf",
)
```

Document downloads can also generate filenames from document metadata:

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

PTAB AIA trial operations live under `client.ptab.trials`:

```python
proceeding = client.ptab.trials.get_proceeding("IPR2024-00001")
documents = client.ptab.trials.get_documents("IPR2024-00001")
decisions = client.ptab.trials.get_decisions("IPR2024-00001")

client.ptab.trials.download_document(
    documents.documents[0],
    output_path="downloads/",
)
```

Search supports the same GET parameters and structured POST bodies as Patent
File Wrapper searches:

```python
results = client.ptab.trials.search_proceedings(
    q="trialMetaData.trialTypeCode:IPR",
    limit=25,
)

client.ptab.trials.download_decisions_search_results(
    q="trialNumber:IPR2024-00001",
    format="csv",
    output_path="exports/",
)
```

Search PTAB appearances using explicit party/counsel fields:

```python
from uspto_client import patent_owner_counsel_query, petitioner_counsel_query

owner_side = client.ptab.trials.search_proceedings(
    q=patent_owner_counsel_query("Latham & Watkins"),
)
petitioner_side = client.ptab.trials.search_proceedings(
    q=petitioner_counsel_query("Latham & Watkins"),
)
```

The Assignment Center service does not use the Open Data Portal API key:

```python
from uspto_client import AssignmentCenterClient

with AssignmentCenterClient() as assignments:
    response = assignments.search_exact_assignee("EXAMPLE COMPANY, INC.")
    for result in response.results:
        for patent in result.properties:
            print(patent.patent_number, patent.application_number)
```

Assignment Center search results are recorded transactions, not a current-owner
determination. They may include security interests, name changes, corrections,
and other non-title events, and a party-name search may return the surrounding
transaction history for matched properties. Ownership analysis belongs in the
consuming project. See
[`docs/assignment-center.md`](docs/assignment-center.md).

Structured search payloads are supported:

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

Common online-tool filter options are available as constants:

```python
from uspto_client import (
    APPLICATION_TYPE_LABEL_NAMES,
    Pagination,
    SearchRequest,
    application_type_filter,
    filing_date_sort_desc,
)

request = SearchRequest(
    q="",
    filters=[application_type_filter(*APPLICATION_TYPE_LABEL_NAMES)],
    range_filters=[],
    pagination=Pagination(offset=0, limit=25),
    sort=[filing_date_sort_desc()],
)
```

## API Keys

USPTO requires an Open Data Portal API key. Pass it explicitly when creating the
client:

```python
client = UsptoClient(api_key=os.environ["USPTO_API_KEY"])
```

The library does not automatically load `.env` files. `.env` is only a local
development convenience for live tests and scripts.

## Rate Limits And Request Safety

USPTO documents a burst limit of `1` request per API key. This client serializes
requests by API key in-process so calls made through clients sharing the same
key do not run concurrently.

Ordinary calls are spaced by at least 10 ms and serial downloads by at least
50 ms by default. Both are configurable with `PacingConfig`. HTTP 429 responses
are surfaced as `UsptoRateLimitError`; retries for 429, 5xx, and interrupted
transport operations are opt-in through `RetryConfig`.

## Development

Create a virtual environment and install development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Run the normal test suite:

```powershell
pytest
```

Normal tests must not call the USPTO API. Live tests require an explicit flag
and `USPTO_API_KEY`:

```powershell
pytest -m live --live-uspto
```

Capture a sanitized live fixture intentionally:

```powershell
python scripts/capture_fixture.py get-metadata 16330077 tests/fixtures/live/get_metadata_16330077.json
python scripts/capture_fixture.py ptab-proceeding IPR2024-00001 tests/fixtures/live/ptab_proceeding.json
```

Quality checks expected after each implementation phase:

```powershell
pytest
ruff check .
black --check .
mypy src
```

For a copy-friendly guide to using this package from another project, see
[`docs/developer-usage-guide.md`](docs/developer-usage-guide.md).
