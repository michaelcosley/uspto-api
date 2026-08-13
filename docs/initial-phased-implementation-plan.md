# Initial Phased Implementation Plan For `uspto-client`

This project will build a pure-Python, sync-first USPTO client library focused
initially on Patent File Wrapper / patent application APIs. The public interface
will use `client.applications.*`, enforce USPTO's one-request-at-a-time API-key
rule, use Pydantic v2 models for request/response data, and make accidental
external API calls impossible during normal tests.

## Phase 1: Project Foundation, Tooling, And Network Safety

Create the project skeleton, `.env.example`, `.gitignore`, `pyproject.toml`,
README, conventions documentation, LLM reference, progress tracking, source
package skeleton, test skeleton, and no-network test guard.

## Phase 2: USPTO Documentation Audit And API Reference

Create a verified project-owned API reference, endpoint registry, and tests that
confirm the supported initial patent application endpoints are represented while
trademark and future endpoints remain out of implementation scope.

## Phase 3: Core Client, Transport, Errors, And Models Foundation

Implement `UsptoClient`, sync HTTP transport, typed exceptions, Pydantic model
base classes, and the `client.applications` namespace.

## Phase 4: Sequential Request Enforcement And 429 Handling

Serialize requests by API key in-process and handle 429 responses gracefully.
Retries remain disabled by default; when enabled, 429 retry waits at least five
seconds unless `Retry-After` is longer.

## Phase 5: Patent Application API Methods

Implement initial Patent File Wrapper methods under `client.applications` with
mocked fixture tests for paths, parameters, response parsing, and error paths.

## Phase 6: Fixture Capture And Live API Test Harness

Add opt-in live tests and fixture capture workflow. Normal `pytest` must never
call USPTO.

## Phase 7: Documentation Polish And Developer Workflow

Finalize README, API usage examples, testing workflow, error examples, supported
endpoint matrix, rate-limit behavior, and internal LLM reference.

## Phase 8: Future Expansion Planning Only

PTAB/AIA trial support was implemented in version 0.2.0 under
`client.ptab.trials`. Trademark APIs, PTAB appeals and interferences, OpenAPI
codegen, and async APIs remain future work.
