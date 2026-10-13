# Architecture 137 / RCL-1 — Research candidate lifecycle foundation

Status: implemented for exact GitHub review; source acceptance belongs to ChatGPT.

## Provenance and frozen operational boundary

The exact base is the GUI-A15 docs closeout: HEAD
`778151fe8f91632a1af66384a3ab0a85d8d65069`, TREE
`03c50482427b04ebfc6ed061d048bb95e86edeae`. Accepted GUI-A15 executable/test
source remains HEAD `1dd46169deb69d7a381687b6ba835af9d6c12e5a`, TREE
`383b237aebfc553b10c7a5ef121a0191559c3f11`. Dedicated GUI CI
[38343026765](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343026765)
and repository source gate
[38343142780](https://github.com/callmedraken/ai-trading-bot/actions/runs/38343142780)
are accepted terminal SUCCESS evidence; RCL-1 does not replace that identity.

R1 remains `6bf8753b0cc8950ae27b32b6858b64d454c512f0`; R2 remains
`2f122958366d1db282fea51abbd461b83fa893d9`. The first manual D1
production-paper session remains an independent protected operational boundary.
RCL-1 adds no ACTIVE production checkpoint, GUI integration or D2 supervisor.

## Frozen conceptual lifecycle

The exact ordered `ResearchCandidateStage` vocabulary is:

1. EXPERIMENTAL: pre-canonical hypothesis state.
2. BACKTESTED: explicit selection from one completed exact canonical report.
3. WALK_FORWARD_PASSED: reserved until an explicit deterministic qualification policy.
4. SHADOW: reserved until canonical no-effect live-observation evidence exists.
5. PAPER_CANDIDATE: reserved until canonical paper evidence and soak policy exist.
6. AWAITING_HUMAN_PROMOTION: reserved until every prior research gate is defined;
   eligible for human review, without approval or promotion.

Only **BACKTESTED** can be materialized by v1. Stage and schema are fixed
non-constructor fields. There is no set-stage, advance, promote or generic
transition API. Enum adjacency is conceptual and grants no authority.

Existing `HistoricalExperimentWalkForwardResult` is deterministic research
evidence. Its existence does not establish WALK_FORWARD_PASSED. No threshold,
selection-frequency, positive-return or rank policy is inferred. Architecture
138 must separately freeze `ResearchCandidateWalkForwardQualificationPolicy`.

## Candidate and deterministic identity

`src/trading_bot/experiments/research_candidate.py` owns the frozen immutable
`ResearchStrategyCandidate`, schema `research-strategy-candidate/v1`.
The exact JSON fields are schema, candidate_id, stage, source_head, source_tree,
report_id, experiment_result_id, variant_id, caller_ordinal, variant_name and rank.

The candidate UUID5 namespace is `c914e214-9553-56ce-978a-ddd33bf6210f`.
Identity material is the ordered sequence:

```text
research-strategy-candidate-identity/v1
schema
stage.value
source_head
source_tree
str(report_id)
str(experiment_result_id)
str(variant_id)
str(caller_ordinal)
variant_name
"none" if rank is None else str(rank)
```

Every value is framed as `<UTF-8 byte length>:<value>` and concatenated before
UUID5. Every retained semantic field except candidate_id participates. It does
not depend on JSON bytes, filesystem paths, clocks, object identity, Decimal
context, ambient configuration or downstream analysis.

HEAD/TREE must be exact lowercase 40-hex strings. They identify research source
only; no production source authority or external source verification is granted.
The three retained IDs must be exact UUID objects. Ordinal is an exact int in
0..1,000,000; rank is None or an exact int in 1..1,000,000. Bool is rejected.
Name is exact stripped nonblank UTF-8 text of at most 256 characters. Untrimmed
and over-bound input fails; no truncation or normalization is performed.

## Explicit selection and independent reconciliation

`build_backtested_research_candidate(report, *, selected_variant_id,
source_head, source_tree)` requires exactly `HistoricalExperimentReport`,
revalidates its existing report identity/relationships and locates exactly one
matching UUID. It retains report_id, experiment_result_id, variant_id,
caller_ordinal, variant_name and rank without reinterpretation.

Rank is evidence, never authority. Rank-1, rank-2 and unranked variants are
equally selectable when the caller explicitly supplies their variant ID. There
is no automatic rank selection or optional selection argument.

`verify_research_candidate_against_report(candidate, report)` revalidates exact
types and invariants, recomputes candidate identity and requires exact agreement
on all six retained report/row fields. Any mismatch fails closed. Report
validation operates on a defensive copy and rejects normalization drift, leaving
the caller's evidence unchanged even on failure.

`from_json()` proves only canonical/self-consistent candidate material. It does
not establish external report verification, research qualification, or source
acceptance. No verified flag or mutable approval metadata is retained.

## Canonical JSON and capability boundary

JSON is compact with sorted keys and no trailing newline. Parsing rejects
duplicate, unknown or missing fields, NaN/Infinity, noncanonical UUID/source/
stage/name/type representations and forged candidate IDs. Recomputed identity
and exact `to_json()` equality are mandatory, rejecting alternate whitespace,
field order and numerical representation.

The module is pure and in memory. Its imports are restricted to the standard
library plus existing experiment exceptions and report models. It has no
filesystem, credentials, network/provider, broker, production store, scheduler,
runtime operator, research execution or walk-forward execution capability.

Historical portfolio variants are not equivalent to the production
MovingAverageCrossoverStrategy contract. No production strategy module is
imported, no ProductionStrategyContract is created, and no compatibility or
production-readiness claim is made. A separately reviewed research-to-production
compatibility bridge must precede any possible human promotion. RCL-1 cannot
select, replace, ARM or execute production strategy, create live/paper authority
or infer human approval. Real-money broker placement remains **NO-GO**.

## Current inventory and review route

Canonical discovery yields ACTIVE 62, FULL 170, ROBINHOOD 94, LEGACY 215,
EXHAUSTIVE 385 and tests/gui 44. The new experiments test enters supported FULL
automatically. Current count assertions and the full-profile expected module set
are reconciled. Only three directly affected retained test-file blob pins are
refreshed with LF-normalized Git-blob hashing; executable/native/AST pins,
ACTIVE tuple/digest and historical publication-recovery pins remain frozen.

The research branch is intentionally outside the production push allowlist.
After ordinary push, dispatch Checkpoint Source Gates against exactly
`feature/research-candidate-lifecycle-foundation`. Expected route: source-static,
four full-tests shards, active-tests/certification-tests skipped, terminal
source-gates success. No dedicated GUI run or local broad certification is
required by RCL-1. ChatGPT owns exact final GitHub review and acceptance/closeout.
