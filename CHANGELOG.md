# Changelog

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
