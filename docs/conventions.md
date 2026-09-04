# Python Project Conventions

## Runtime And Packaging

- Target Python `>=3.11`.
- Use a `src/` layout.
- Keep the public package pure Python.
- Do not load `.env` automatically in library code.

## Public API

- Public entrypoint: `UsptoClient`.
- Initial endpoint namespace: `client.applications`.
- Do not add `client.patent_applications`.
- Keep USPTO-specific URL details inside endpoint modules.

## HTTP And Rate Limits

- Use sync `httpx`.
- Route all HTTP calls through the shared client request method.
- Serialize and pace requests by API key in-process. Defaults are 10 ms for
  ordinary calls and 50 ms for downloads, both configurable.
- Do not retry 429 responses by default.
- If 429 retry is enabled, wait at least five seconds or `Retry-After`,
  whichever is longer.
- Keep 5xx and transport retries opt-in and bounded.
- Preserve HTTP 404 exceptions; do not silently convert search 404s to empty
  results in the API client.

## Models

- Use Pydantic v2 for request and response models.
- Configure models with `extra="allow"` to tolerate USPTO schema drift.
- Use aliases for USPTO JSON fields when Python names differ.
- Keep raw response access possible for debugging.

## Testing

- Write tests before implementation for each new behavior.
- Normal tests must never call external APIs.
- Live tests must be marked `live` and require `--live-uspto`.
- Mocked tests must not require `USPTO_API_KEY`.
- Add fixture-backed tests for endpoint responses.
- Use the fixture capture sanitizer before saving live response captures.
- Keep document-code shorthand data packaged under `src/uspto_client/data/`;
  allow callers to pass a custom CSV path for project-specific updates.

## Quality Checks

Run these before considering a phase complete:

```powershell
pytest
ruff check .
black --check .
mypy src
```
