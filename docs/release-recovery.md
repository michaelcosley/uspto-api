# Recovery of the unpublished 0.4.1 and 0.4.2 source

The package source for these versions was recovered from retained release wheels
because the original local commits were not available in the surviving checkouts
or on the remote. The new commits replace those unpublished commit identities;
version numbers and package behavior are preserved.

- Original 0.4.1 identity: `9e9700f749b0dc4dcd75bf151f8681c291169462`.
- Original 0.4.2 identity: `ec47219b1607663b1230346fd3fda54c278d9860`.
- Every package file was compared byte for byte with its retained release wheel.
- The rebuilt 0.4.2 wheel contains identical package files.
- Regression tests were restored from the original development record. They cover
  facade streaming, structured PFW discovery ranges, multiple docket attachments,
  historical files/times/methods, repeated imports, conflicting source observations,
  schema-1 projection backfill, explicit text selection, and derivative history.
- Recovery validation: 106 offline tests for 0.4.1 and 111 for 0.4.2 passed;
  five live tests were excluded. Ruff, Black, mypy, wheel and source-distribution
  builds passed for the recovered 0.4.2 tree.

Consumer repositories must pin the new published commit rather than the unavailable
original identity. Publishing these sources does not change an existing deployment
or authorize opening production databases with the newer schema.
