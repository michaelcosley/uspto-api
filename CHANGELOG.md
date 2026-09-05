# 0.4.0

- Add typed bulk product/file APIs and streamed, budgeted, resumable downloads.
- Add opt-in portable SQLite library and CLI, selective PFW/PADX importers,
  source observations, import receipts, coverage checks and backups.
- Add readable document layouts, original/derivative provenance and FTS5 text.
- Add reviewed company aliases, assignment history/candidate screening,
  bounded proceeding discovery and immutable first-detection matches.
- Preserve existing 0.3 API behavior; no legacy database or consumer migration.
- Document production-validation limits and future adoption boundaries.

# Changelog

## 0.3.0 - 2026-09-04

- Added an experimental, separately hosted, unauthenticated
  `AssignmentCenterClient` for
  the official public patent-assignment search service, including simple and
  advanced search, reel/frame lookup, export-route access, and recorded-document
  downloads.
- Added tolerant typed models that normalize Assignment Center's inconsistent
  object/list response shapes while preserving new fields.
- Added Patent File Wrapper assignment-name/conveyance query helpers and PTAB
  counsel/party-name query helpers.
- Added default in-process pacing of 10 ms between ordinary API calls and 50 ms
  between serial downloads, with configurable intervals.
- Added opt-in retries for HTTP 429, HTTP 5xx, and transport failures with
  `Retry-After` handling and bounded exponential backoff.
- Preserved typed HTTP 404 exceptions; PTAB search may use 404 to mean no
  matching records.
- Added client documentation, a repository-local usage skill, and GitHub Actions
  quality checks.

## 0.2.0 - 2026-08-13

- Added `client.ptab.trials` with proceeding, document, and decision search,
  lookup, export, and file-download operations.
- Added tolerant typed PTAB response models and common PTAB search helpers.
- Accepted both USPTO-documented decision response bag names while serializing
  to the live `patentTrialDocumentDataBag` form.
- Added content-disposition filenames for JSON and CSV exports.
- Limited `X-API-KEY` forwarding to the configured USPTO API origin, including
  across file-download redirects.
- Added representative PTAB fixtures, network-blocked unit tests, and opt-in
  live PTAB smoke tests.

## 0.1.0 - 2026-05-20

- Added the initial Patent File Wrapper application API client.
