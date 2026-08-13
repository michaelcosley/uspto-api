# uspto-client

`uspto-client` is a pure-Python, sync-first client library for USPTO Patent
File Wrapper and Patent Trial and Appeal Board APIs. It supports patent
applications plus PTAB AIA trial proceedings, documents, and decisions.
Trademark APIs are out of scope.

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

HTTP 429 responses are surfaced as `UsptoRateLimitError`. Automatic retry is
disabled by default.

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
