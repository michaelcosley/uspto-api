# Company portfolios and first-detected proceedings

This workflow supports finding patents associated with a company and identifying
newly detected reexaminations/IPRs that may affect it. It preserves recorded
facts, ownership-screen results, and detection evidence separately.

## Example workflow

```console
uspto-library --root data watch-company example "Example Company, Inc." --alias "Example Co."
uspto-library --root data collect-assignments example
uspto-library --root data company-patents example
uspto-library --root data ownership-candidates 12345678
uspto-library --root data patent-history 12345678
uspto-library --root data discover --from 2026-09-01 --to 2026-09-05 --max-records 500
uspto-library --root data matches
```

Use actual identifiers and reviewed company aliases. Names above are synthetic.
`collect-assignments` uses the separately hosted Assignment Center client; it does
not use the ODP key. Bulk assignment imports use ODP. No emails, notifications,
background jobs, or schedules are created by these commands.

Aliases are explicit and retained. Normalization handles case and whitespace,
but does not silently merge corporate suffixes, subsidiaries, similarly named
companies, or typographic variations beyond Unicode normalization. Add each
reviewed alias. Searching all patents assigned to a company requires adequate
source coverage and alias coverage; a filtered local index cannot establish a
complete portfolio of unknown aliases or uncollected records.

## Ownership evidence

`company_patents` returns one row per patent with contributing reel/frame IDs
and either `current_assignee_candidate` or `historical_or_non_title` status.
`patent_history` exposes the known recorded transactions. `ownership_candidates`
uses versioned rules to identify assignees in the latest known recorded ordinary
full assignment. Security interests, liens, licenses, releases and mortgages
do not displace that candidate. Corrections, partial interests, name changes,
mergers, ambiguous conveyances, ties, and incomplete histories need review.
Execution dates and all original fields remain available in source records;
the candidate screen orders ordinary transfers by **recordation date**, not a
legal determination of effective transfer order.

The result is never a definitive title conclusion. Public recordation does not
validate an instrument or establish complete current ownership. An older company
may still appear in historical results after a later assignment away. PADX purge
flags remove that transaction from active lookup relations but preserve its
observations. Same-date conflicting source revisions are retained for review.

Assignment Center searches can return a property's surrounding transaction chain.
The source property-group scope is retained explicitly; transaction-specific
property coverage should be verified before relying on an ownership screen.
Repeated partial search groups accumulate known properties for a reel/frame;
absence from a search group is not treated as a deletion. Full PADX corrections
and purge records provide the authoritative replacement path when collected.
PADX raw XML preserves exact record-level properties and execution dates.
Explicit application-to-patent links from individual PADX properties, Assignment
Center properties, or PFW records connect earlier application-only assignments
to issued patents. A reexamination uses its underlying REX parent application;
its own proceeding number is never treated as the patent's application number.
Unknown links remain unresolved; unrelated applications and patents in the same
transaction are never paired by position or cross-product.

## Detection semantics

`discover` searches a bounded ingestion/modification date window, with a record
budget. It fetches full reexamination metadata when needed to resolve a challenged
patent through its `REX` continuity edge. It records source observations and then
matches either an explicitly reported PTAB patent-owner name or a patent in the
company's current-assignee candidate portfolio. Unknown challenged-patent links
are not guessed. Targeted `collect` also reports unresolved links.

Use overlapping windows to accommodate delayed ingestion and periodically
reconcile selected dockets. The normal offline tests verify pagination and
budgets; the production date-field semantics must be confirmed in a bounded live
pilot before depending on this as a monitoring service. Existing low-level API
404 exceptions remain visible; the library does not turn a failed search into
an assertion of complete empty coverage.

Each company/proceeding receives one immutable first-detection event, containing
its basis, evidence, first-detected time, and the proceeding's first-seen time.
A proceeding can be discovered first and matched later when assignment data is
added. That later match is a new detection, not a new filing. Repeated scans do
not emit duplicate events. `matches` is a historical detection log, not a live
list of confirmed current owners. Re-run portfolio/ownership queries to assess
current evidence. `match_companies(include_historical=True)` is an explicit
Python option for broader historical-assignee screening.

Scheduling and notification delivery belong to the consuming application. The
`new_matches` result is the integration boundary for that later work.
