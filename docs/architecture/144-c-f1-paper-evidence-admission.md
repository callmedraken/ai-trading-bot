# Architecture 144-C — F1 paper-evidence admission successor boundary

Status: **BOUNDARY FROZEN; exact F1 source binding deferred until F1 acceptance.**

Architecture 144 v1 is intentionally historical-D1R9-specific. Its accepted
evidence verifier requires the frozen D1R9 branch/HEAD/TREE, and its v1 session
observation schema encodes `d1r9_source_head`, `d1r9_source_tree`, and
`d1r9_journal_sha256`. Those names and semantics are not generic provenance.

Architecture 144-C exists so current-lineage Architecture 134-F1 evidence can be
admitted truthfully without weakening or reinterpreting v1.

## Frozen compatibility rule

The following Architecture-144 v1 surfaces remain byte/behavior frozen:

- D1R9 facts validation and parser semantics;
- `ResearchStrategyPaperSessionObservation` v1 schema/identity/canonical bytes;
- `ResearchStrategyPaperCandidateEligibility` v1 schema/identity/canonical bytes;
- v1 builders/verifiers and their historical D1R9 source pins.

F1 evidence must continue to fail the v1 D1R9 source-binding check.

## Successor shape

After exact F1 source acceptance, 144-C will pin that final F1 HEAD/TREE and add
a separate pure path with generic paper-authority provenance. The successor must
represent at least:

- authority kind/version (`ARCH134_F1`);
- exact F1 source HEAD/TREE;
- parent-series identity and journal digest;
- child ordinal and target session;
- child identity and journal digest;
- exact D1R7/D1R8 source/proof bindings;
- terminal classification;
- fixed production strategy/target/contract provenance;
- strategy configuration and production source provenance.

The successor must use a new schema/identity namespace. It must not overload
`d1r9_*` names with F1 values.

## Eligibility

The successor may add a v2/generic-authority session observation and matching
eligibility artifact, or an equivalent separately versioned normalized evidence
layer, provided:

- the v1 artifacts remain unchanged;
- five-session policy semantics stay identical unless a separately reviewed
  policy version says otherwise;
- exact consecutive published-session checking remains;
- at least one PAPER_EXECUTED remains required for positive eligibility;
- RISK_REJECTED remains nonqualifying;
- SESSION_MISSED/BLOCKED/INDETERMINATE remain nonqualifying;
- eligibility evaluation remains pure/read-only.

## Source/effect boundary

144-C is a pure `experiments` successor. It may parse supplied bytes/objects but
must not read production files, SQLite, scheduler state, credentials, provider
state or broker state. It may not mutate paper state, create scheduler tasks,
run F1, promote a strategy or grant live authority.

The exact 144-C design/source implementation starts only after final F1
HEAD/TREE are accepted so provenance pins are not circular or provisional.

## Certification

144-C does not automatically require canonical FULL. Its implementation should
use focused tests plus the normal source-gate broad shards. Select a canonical
profile only if the final changed surface materially requires one under the
Architecture-132 workflow. Do not run FULL merely because 144-C extends the
paper-evidence model.

Real-money trading remains **NO-GO**.
