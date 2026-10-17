# Architecture 141 / RCL-4 — Research Candidate Production Compatibility Assessment

Status: **DESIGN FROZEN; SOURCE NOT IMPLEMENTED**.

## Purpose

Architecture 141 is the next parallel safe-side research milestone after accepted
Architecture 139-B SHADOW and Architecture 140 GUI-A18. It establishes a pure,
deterministic compatibility-assessment artifact between one fully verified
SHADOW research candidate and the repository's currently accepted production
strategy family.

It does **not** establish positive production compatibility. The current research
variant is an exact `HistoricalExperimentVariant` for portfolio optimization,
while the current production contract selects
`MovingAverageCrossoverStrategy` with an exact symbol and
`MovingAverageCrossoverConfig`. No reviewed semantic mapping exists between
those models. Architecture 141 must record that absence instead of inferring a
mapping from variant name, rank, metadata, historical universe, proposal policy
or any other ambient field.

The v1 result is therefore deterministic `NOT_ESTABLISHED` compatibility
evidence. A later architecture is required before any positive compatibility
claim, production-contract construction, `PAPER_CANDIDATE` materialization,
human-promotion eligibility or production selection.

## Isolation and branch

Implementation uses a new isolated worktree:

`F:\AI\worktrees\ai-trading-bot-research-candidate-production-compatibility-current`

on branch:

`feature/research-candidate-production-compatibility-current`

The implementation base is the exact terminal-green Architecture-141 design
freeze on `develop`. D1R9's active one-session authority remains on its
separate accepted feature worktree and must not be inspected, modified, retried,
cleaned up or used as Architecture-141 evidence.

## Frozen artifact

New module:

`src/trading_bot/experiments/research_candidate_production_compatibility.py`

owns:

- schema `research-candidate-production-compatibility/v1`;
- identity version
  `research-candidate-production-compatibility-identity/v1`;
- UUID5 namespace `3a2c0a57-e61a-5b19-bdc2-00e96e732e96`;
- exact enum status `NOT_ESTABLISHED`;
- exact ordered blockers:
  1. `RESEARCH_STRATEGY_FAMILY_UNBOUND`;
  2. `PRODUCTION_SYMBOL_MAPPING_UNBOUND`;
  3. `PRODUCTION_CONFIG_MAPPING_UNBOUND`.

The immutable assessment fields are exactly:

```text
schema
assessment_id
stage
shadow_candidate_id
binding_id
shadow_qualification_id
historical_experiment_result_id
variant_id
candidate_source_head
candidate_source_tree
assessment_source_head
assessment_source_tree
production_schema
production_strategy_id
production_strategy_version
status
blockers
```

`stage` is fixed to `ResearchCandidateStage.SHADOW`. The production fields
are fixed from the existing inert production strategy constants:
`PRODUCTION_STRATEGY_SCHEMA`, `MOVING_AVERAGE_STRATEGY_ID`, and
`MOVING_AVERAGE_STRATEGY_VERSION`.

Every semantic field except `assessment_id` participates in length-framed
UTF-8 UUID5 identity material in the exact field order above. UUID, source
digest, enum, tuple and scalar types are exact; bool-as-int is rejected.
Canonical JSON is compact/sorted, rejects duplicate/unknown/missing fields,
noncanonical UUID/source/status/blocker representations and forged IDs.

Parsing proves only canonical self-consistency. It never proves the external
SHADOW chain or source acceptance.

## Full external assessment boundary

The public assessment entry point must require the complete independently
supplied external evidence needed by the accepted 139-B qualification verifier,
plus the exact SHADOW successor and exact Architecture-141 assessment source
HEAD/TREE.

Before creating an assessment it must:

1. run the accepted full external 139-B SHADOW qualification verification;
2. independently verify the SHADOW successor linkage;
3. resolve the exact original retained `HistoricalExperimentVariant` through
   the accepted 139-A binding/result bridge;
4. require the SHADOW successor, binding, qualification and resolved variant to
   agree on the exact candidate/result/variant lineage;
5. revalidate the resolved exact variant without modifying it;
6. produce only the frozen `NOT_ESTABLISHED` artifact above.

An independent verifier must rebuild the complete assessment from the same
external evidence and require exact equality.

No compatibility may be inferred from:

- `variant_name`;
- `rank`;
- generic `metadata`, including keys or values that spell production strategy
  names, symbols or moving-average parameters;
- one-symbol historical universes;
- proposal/risk/fill policy similarities;
- numeric coincidence with production configuration;
- source branch names, paths or filenames.

Those are evidence or labels, not an explicit semantic bridge.

## Production capability boundary

Architecture 141 may import only the inert production contract constants needed
to identify the target production family. It must not instantiate or serialize
`ProductionStrategyContract`, `MovingAverageCrossoverConfig` or
`MovingAverageCrossoverStrategy`, and must not call
`build_production_strategy`.

It adds no target session, symbol selection, strategy configuration,
desired quantity, production source selection, production decision, PREPARE,
EXECUTE, risk decision, paper fill, broker order or scheduler authority.

No generic compatibility override, caller-supplied compatibility flag,
"verified" flag, stage mutation, promote/advance helper or production-contract
factory may be added.

## Lifecycle boundary

Architecture 141 leaves the lifecycle stopped at `SHADOW`.

It must not construct or serialize:

- `PAPER_CANDIDATE`;
- `AWAITING_HUMAN_PROMOTION`;
- a production strategy contract;
- a production compatibility success artifact;
- approval/promotion eligibility;
- production replacement/selection authority.

A future positive compatibility checkpoint must use a new separately reviewed
schema/contract. This v1 artifact cannot be repurposed into success by changing
a field value.

## Imports and effects

The new domain module is pure/in-memory. Allowed imports are the standard
library plus the minimum accepted experiment interfaces needed to verify the
139-B chain and resolve the bound variant, and the three inert production
identity constants above.

AST/source tests must prohibit filesystem, subprocess, socket/network, provider,
credentials, Robinhood, review-paper runtime, production stores, scheduler,
ACL, broker/execution, GUI composition, clocks/random UUIDs, strategy
construction/evaluation and lifecycle mutation.

Operational accounting for implementation/source tests is exactly zero:

```text
PRODUCTION_SQLITE_READS=0
PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0
PROVIDER_CALLS=0
ROBINHOOD_READS=0
BROKER_CALLS=0
SCHEDULER_CALLS=0
ACL_MUTATIONS=0
PAPER_MUTATIONS=0
REAL_RESEARCH_EXECUTIONS=0
REAL_WALK_FORWARD_EXECUTIONS=0
SHADOW_LIVE_OBSERVATIONS=0
PRODUCTION_CONTRACTS_CREATED=0
STRATEGY_EVALUATIONS=0
STRATEGY_PROMOTIONS=0
PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0
D1R5_OPERATIONS=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

## Publication and source authority

Implementation is one source checkpoint on the isolated Architecture-141 branch.
Compose implementation, focused tests, additive package exports, validation
record and required current inventory/authority overlays completely before one
atomic commit and one ordinary push.

Use exact staging only. No `git add .` or `git add -A`. GitHub source CI is
admission, not debugging. A red push ends that attempt; any bounded mechanical
correction is a separately declared C1 checkpoint and must preserve the failed
evidence.

Run focused tests and affected authority/checkpoint-runner tests locally. Do not
run duplicate broad FULL/ROBINHOOD locally when mapped GitHub CI owns them.
Recompute actual inventory; never guess counts.

The implementation must freeze all predecessor dictionary/overlay digests,
including the accepted Architecture 139-B and Architecture 140 successor
overlays and every current product/D1 overlay present on the exact base. D1R9
source is not merged and must not be introduced by Architecture 141.

After terminal-green CI, stop for ChatGPT exact-source review. No GUI successor,
real acquisition, compatibility-success checkpoint, PAPER_CANDIDATE,
integration, promotion or protected operation is part of the implementation
checkpoint.
