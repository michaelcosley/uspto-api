# LLM Reference For `uspto-client`

Use this file to orient future coding agents.

## Project Intent

Build a reusable pure-Python USPTO client library. The initial implementation
supports USPTO Patent File Wrapper / patent application APIs. PTAB/AIA
proceedings are future scope. Trademark APIs are out of scope.

## Source Documentation

Downloaded USPTO source material currently lives under `docs/`:

- `docs/getting-started.txt`: API key/header basics.
- `docs/api-rate-limits.txt`: rate limits and sequential-call requirements.
- `docs/uspto-swagger-api.yaml`: OpenAPI entrypoint.
- `docs/patent-file-wrapper/`: Patent File Wrapper page captures.
- `docs/patent-file-wrapper/full-uspto-api-syntax-doc.txt`: Search payload,
  query syntax, filters, range filters, sort, fields, pagination, and facets.
- `docs/ptab-trials/`: PTAB page captures, with at least one known mismatch.

Known documentation issues:

- `docs/uspto-swagger-api.yaml` is not self-contained. It references missing
  files such as `odp-common-base.yaml`, `trial-proceedings.yaml`,
  `trial-decisions.yaml`, `trial-documents.yaml`,
  `trial-appeal-decisions.yaml`, and `trial-interferences.yaml`.
- `docs/ptab-trials/search-proceedings.txt` appears to describe Final Petition
  Decisions, not PTAB Trial Proceedings.
- Raw copied docs contain encoding artifacts. Authored docs should normalize
  them, but raw source captures should be left untouched unless requested.

## Implementation Map

- `src/uspto_client/client.py`: public `UsptoClient` and shared request path.
- `src/uspto_client/applications.py`: `client.applications.*` methods.
- `src/uspto_client/models.py`: Pydantic request/response models.
- `src/uspto_client/errors.py`: typed exception hierarchy.
- `src/uspto_client/rate_limit.py`: API-key serialization and retry config.
- `src/uspto_client/registry.py`: endpoint inventory used by docs/tests.
- `tests/conftest.py`: normal-test network blocking and live-test guard.

## Non-Negotiables

- Do not add trademark APIs.
- Do not allow normal tests to make network calls.
- Do not require `USPTO_API_KEY` for mocked tests.
- Do not add async APIs in v1.
- Keep `client.applications.*` as the public namespace.
