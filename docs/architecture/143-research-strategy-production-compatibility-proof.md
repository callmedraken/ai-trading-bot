# Architecture 143 / RCL-6 — Research Strategy Production Compatibility Proof

Status: **ARCHITECTURE 143 / RCL-6 SOURCE/CERTIFICATION ACCEPTED; R3I-C1 CLOSEOUT**.

The current acceptance is a bounded documentation/workflow closeout on
`develop`. It records acceptance of the pure strategy-native compatibility
proof while preserving the original design contract below as frozen
pre-implementation provenance. It grants no production, paper, broker,
scheduler, D1, D1R9, D2, provider, credential, deployment, or live authority.

## Acceptance / closeout — 2026-10-18

Architecture 143 / RCL-6 is **SOURCE/CERTIFICATION ACCEPTED**. The design
authority is the frozen Architecture-143 design record at
`3d66d1a3a7629eb07fcdef9fd1d6ed9f68d1bd87`; the accepted executable
predecessor is Architecture 142-B at
`e88f38f8deeb834ac3f162b6a82e328dc4708ad0` /
`23f63ed62e67460edce5b9296893bdcfe49a25f7`.

The Architecture-143 semantic implementation is accepted at HEAD
`33b14eab4e9577f15b2afa559918415e4d471d55`, TREE
`d19ef77620881343cc38010290029865fd43c1f4`. The Architecture-132-R3I source
checkpoint is `9fb082d21f00326bc98103abb8d357e6368df72f`; the final R3I-C1
descendant is HEAD
`c5225d8f3f584eb0eb60d62e5381f1caa3c56cb2`, TREE
`bf7019b1610c29563282ccb5f19be2bcb6501849`, parent
`9fb082d21f00326bc98103abb8d357e6368df72f`.

Checkpoint Source Gates #630, run `39117841927`, push, attempt 1, is terminal
SUCCESS. Its terminal jobs were `source-static`, `full-tests (0)`,
`full-tests (1)`, `full-tests (2)`, `full-tests (3)`, and `source-gates`;
`active-tests` and `certification-tests` were skipped. The final canonical FULL
evidence was run exactly once after source acceptance because this feature
checkpoint was unmapped and required materially distinct timing evidence. It
passed 12,354 cases: 12,351 passed, 3 skipped, 0 failed, 0 errors, in 287.176
seconds, with four whole-module lanes of 46 / 47 / 46 / 47 modules and child
elapsed values 282.944 / 282.968 / 282.991 / 283.018 seconds. The 300-second
hygiene ceiling remains unchanged. The later reporting-wrapper `.error`
property issue occurred after certification had completed and is not a
certification failure.

R3I changes current FULL only to four deterministic nonempty whole-module
timing-aware lanes. ROBINHOOD remains exactly two deterministic lanes with the
accepted R3H placement overlay. LEGACY/EXHAUSTIVE retain their historical
two-broad-plus-serial topology. No tests were dropped or reclassified, and no
test ownership or effect boundary changed. The feature source remains
intentionally unmerged into `develop`; `develop` is the bounded startup and
documentation integration reference, while the accepted executable/certified
source is identified separately above.

Architecture 143 remains a pure compatibility proof. It does not create
`ProductionStrategyContract`, `PAPER_CANDIDATE`,
`AWAITING_HUMAN_PROMOTION`, promotion authority, provider/credential
authority, paper/broker authority, scheduler authority, deployment authority,
D1/D1R9/D2 authority, or live authority. Architecture 141 remains the
immutable old `SHADOW` / `NOT_ESTABLISHED` path. D1R9 remains an independent
primary operational progression: its one-session authorization is active and
consumed while its supervisor waits for the Monday `2026-10-19` market
session. Do not re-authorize D1R9 or manually create/run/update/delete/recreate
its scheduler task. Safe-side progression may continue while the supervisor
waits.

The immediate safe-side next step is ChatGPT-led Architecture-144/next-RCL
design selection and contract freezing. This closeout does not implement
Architecture 144.

## Frozen design provenance

The following design-freeze text records the prospective contract that governed
the implementation. Its former future-implementation language is historical
provenance; the acceptance section above is the current status.

## Decision and boundary

Architecture 143 consumes only the accepted Architecture-142 strategy-native
research chain:

1. one `ResearchStrategyDefinition`;
2. one `ResearchStrategyEvaluationPolicy`;
3. one completed `CompletedResearchStrategyWalkForward`;
4. one `ResearchStrategyWalkForwardQualificationPolicy`;
5. one `ResearchStrategyWalkForwardQualification`; and
6. one `WalkForwardPassedResearchStrategy`.

The future implementation must externally replay and reconcile the complete
142-B PASS chain before constructing or accepting a positive compatibility
proof. It then validates one explicit inert production semantic target and
compares every frozen semantic dimension exactly.

Architecture 141 remains an immutable old portfolio-candidate assessment. Its
artifact remains `SHADOW` / `NOT_ESTABLISHED`, and its blockers remain the
historical truth for that old path. Architecture 143 does not consume or
reinterpret that artifact.

The original design freeze was admitted from this exact clean checkout:

```text
worktree F:\AI\worktrees\ai-trading-bot-architecture-143-design-freeze
branch   develop
upstream origin/develop
base HEAD  a0defb4a5c568e6afc78a76a325509396a9d327e
base TREE  50f6e193e917132dd596155115bbc1fc73691f4f
```

Architecture 142 remains complete and source accepted on its isolated feature
lineage. The accepted 142-B source is consumed as an external interface only;
its feature source remains intentionally unmerged into `develop`.

## Implementation lineage and source-authority overlay

The future Architecture-143 executable checkpoint has two deliberately
separate authorities:

```text
executable predecessor  e88f38f8deeb834ac3f162b6a82e328dc4708ad0
design authority        3d66d1a3a7629eb07fcdef9fd1d6ed9f68d1bd87
```

The executable predecessor is the exact accepted Architecture-142 feature
source on `feature/research-strategy-native-evaluation-current`, with TREE
`23f63ed62e67460edce5b9296893bdcfe49a25f7`. Architecture 143 must be developed
from a new isolated branch/worktree descending directly from that commit:

```text
branch   feature/research-strategy-production-compatibility-current
worktree F:\AI\worktrees\ai-trading-bot-research-strategy-production-compatibility-current
```

It must not use `develop` commit `3d66d1a` as its executable base. The future
implementation reads these frozen design and validation documents from exact
design commit `3d66d1a3a7629eb07fcdef9fd1d6ed9f68d1bd87` using read-only
`git show` or an equivalent read-only retrieval. It must not merge, cherry-pick,
rebase, or copy the accepted 142 source into `develop`, and it must not
merge/cherry-pick the 143 docs commit into the feature source merely to obtain
documentation. Reports must identify the executable predecessor and design
authority separately.

The current-inventory/checkpoint-runner boundary is narrow source-authority
bookkeeping, not operational authority. Workflow YAML remains prohibited, as
do D1R9 and all operational authority. `scripts/checkpoint_runner.py` remains
unchanged unless actual local inventory recomputation and affected
current-authority tests prove that a new supported Architecture-143 test
surface mechanically requires a successor overlay. If required, the only
permitted change is an additive, fail-closed Architecture-143 overlay that
composes after the frozen Architecture-142-B overlay. The accepted 142-A and
142-B dictionaries/digests remain frozen and byte unchanged. The overlay may
cover only exact current inventory/authority test blobs that actually changed
because of Architecture-143 inventory admission. No historical pin may be
rewritten in place, no unrelated source pin may change, and actual inventory
must be recomputed rather than guessed. Current inventory tests may change only
for mechanically measured membership/count effects of the new supported test
surface. If no successor overlay is mechanically required, the checkpoint
runner remains unchanged.

## Frozen production semantic target

The next source checkpoint will add the inert model
`ProductionStrategySemanticTarget` in:

```text
src/trading_bot/experiments/research_strategy_production_compatibility.py
```

It is comparison material only. It is not `ProductionStrategyContract`, has no
`target_session_date`, and its existence or validity cannot select a production
strategy or authorize execution.

Freeze these exact constants:

```text
schema                 production-strategy-semantic-target/v1
identity version       production-strategy-semantic-target-identity/v1
UUID5 namespace        16be4a92-15d8-5db1-9f92-17a3dbd195f3
```

The exact target field set is:

```text
schema
target_id
production_source_head
production_source_tree
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
```

`production_strategy_schema`, `strategy_id`, and `strategy_version` are fixed
by construction from `PRODUCTION_STRATEGY_SCHEMA`,
`MOVING_AVERAGE_STRATEGY_ID`, and `MOVING_AVERAGE_STRATEGY_VERSION`.
`symbol` must be the exact `Symbol` value object. `strategy_config` must be the
exact `MovingAverageCrossoverConfig` value object. No name, metadata, rank,
optimizer setting, historical universe, branch name, filename, proposal
behavior, numeric coincidence, or ambient state may be mapped into either
value.

`production_source_head` and `production_source_tree` are exact lowercase
40-hex Git provenance strings. They are provenance material for semantic
comparison; they do not by themselves prove GitHub/source acceptance,
deployment authority, release installation, scheduler binding, or runtime
readiness.

### Target identity and transport

`target_id` is a deterministic UUID5 under the frozen namespace. Its name is a
concatenation of length-framed UTF-8 fields in this exact order:

```text
production-strategy-semantic-target-identity/v1
schema
production_source_head
production_source_tree
production_strategy_schema
strategy_id
strategy_version
str(symbol)
str(strategy_config.short_window)
str(strategy_config.long_window)
canonical_decimal(strategy_config.desired_quantity)
```

Each field is encoded as `<UTF-8 byte length>:<UTF-8 text>` before
concatenation. The identity material is semantic model material, never
serialized Python object bytes. `target_id` itself is excluded from its own
input.

The future canonical JSON representation uses exactly the frozen field set,
compact separators, sorted object keys, and no non-JSON constants. Unknown,
missing, or duplicate fields are rejected. UUIDs must be canonical lowercase
text and source digests must be lowercase 40-hex text.

The target implementation must reject floats, nonfinite `Decimal` values,
`bool` values accepted as integers, noncanonical Decimal text, random UUIDs,
clocks, `repr()`, Python hash/object identity, paths, and serialized Python
object bytes. Canonical Decimal rendering must have the same meaning as the
accepted production and Architecture-142 contracts and must not depend on the
ambient Decimal context. Parsing proves only canonical self-consistency; it
does not execute research or establish compatibility.

## Frozen compatibility proof

The future positive artifact is
`ResearchStrategyProductionCompatibilityProof`.

It is positive-proof-only. There is no caller-supplied compatibility flag,
generic override, mutable status transition, blocker suppression, or persisted
`verified` flag. Proof existence is the positive assertion. A semantic or
provenance mismatch raises and must not create a proof artifact.

Freeze these exact constants:

```text
schema                 research-strategy-production-compatibility-proof/v1
identity version       research-strategy-production-compatibility-proof-identity/v1
UUID5 namespace        f9f82ac4-219d-512d-bfe9-a1c07c9427a1
```

The exact final field set is frozen now, before implementation:

```text
schema
proof_id
definition_id
evaluation_policy_id
walk_forward_evidence_id
qualification_id
walk_forward_passed_id
production_target_id
research_strategy_source_head
research_strategy_source_tree
production_source_head
production_source_tree
production_strategy_schema
strategy_id
strategy_version
symbol
strategy_config
proof_source_head
proof_source_tree
```

The proof retains all provenance and semantic values even when another UUID
transitively binds them. `research_strategy_source_head/tree` copy the exact
source provenance from `completed.definition.strategy_source_head/tree`;
`production_source_head/tree` copy the target provenance; and
`proof_source_head/tree` identify the exact proof implementation source. All
three pairs are exact lowercase 40-hex values. Proof-source provenance does
not grant source acceptance or deployment authority.

### Proof identity material

`proof_id` is a deterministic UUID5 under the frozen proof namespace. Its
length-framed UTF-8 name uses this exact order, excluding the derived
`proof_id`:

```text
research-strategy-production-compatibility-proof-identity/v1
schema
str(definition_id)
str(evaluation_policy_id)
str(walk_forward_evidence_id)
str(qualification_id)
str(walk_forward_passed_id)
str(production_target_id)
research_strategy_source_head
research_strategy_source_tree
production_source_head
production_source_tree
production_strategy_schema
strategy_id
strategy_version
str(symbol)
str(strategy_config.short_window)
str(strategy_config.long_window)
canonical_decimal(strategy_config.desired_quantity)
proof_source_head
proof_source_tree
```

Every value is framed by UTF-8 byte length before concatenation. The proof
identity is stable for identical semantic inputs and exact provenance,
independent of clocks, paths, object identity, Python hashes, UUID4/randomness,
or serialized artifact bytes.

Canonical JSON contains exactly the frozen proof fields, uses compact
sorted-key JSON, and rejects unknown, missing, duplicate, or noncanonical
fields. A parsed proof is only self-consistent; it is not externally verified
and cannot satisfy the compatibility boundary by itself.

## Full external verification contract

Public construction and public verification must receive enough independently
supplied inputs to verify the complete 142-B chain. The future implementation
must consume the accepted verifier boundary, or an exactly equivalent one:

```python
verify_walk_forward_passed_research_strategy(
    passed,
    qualification,
    completed,
    qualification_policy,
    qualification_source_head=...,
    qualification_source_tree=...,
)
```

Before any positive proof is constructed or accepted, the implementation must:

1. externally verify the entire 142-B passed chain;
2. replay every underlying training/test fold and backtest;
3. reconcile the completed definition, evidence, qualification, policy, and
   passed lineage exactly;
4. validate the explicit semantic target;
5. compare every frozen semantic and source dimension exactly;
6. reject on any mismatch without constructing a proof; and
7. construct or accept the deterministic proof only after all checks pass.

The independent verifier repeats the full chain verification and semantic
comparison, rebuilds the expected proof from independently supplied inputs, and
requires exact equality. Parsing the target or proof must not execute research,
replay walk-forward, acquire data, inspect external state, or grant verified,
compatible, paper, production, or execution authority. There is no persisted
verification flag.

## Exact semantic comparison

The future constructor and verifier must require all of these exact equalities:

```text
completed.definition.production_strategy_schema == target.production_strategy_schema
completed.definition.strategy_id              == target.strategy_id
completed.definition.strategy_version         == target.strategy_version
completed.definition.symbol                   == target.symbol
completed.definition.strategy_config          == target.strategy_config
completed.definition.strategy_source_head     == target.production_source_head
completed.definition.strategy_source_tree     == target.production_source_tree
```

The source comparison is intentionally exact. A different symbol, any
different `short_window`, `long_window`, or `desired_quantity`, a different
production schema/family/version, or either different source digest is
incompatible and must raise. No normalization or mapping is permitted beyond
the already frozen canonical model semantics.

## Architecture-141 separation

Architecture 143 must not consume or reinterpret:

```text
ResearchCandidateProductionCompatibilityAssessment
Architecture-139 portfolio rank
HistoricalExperimentVariant metadata as strategy semantics
variant_name as strategy semantics
the old SHADOW candidate as a semantic bridge
```

Architecture 141 remains immutable:

```text
stage  SHADOW
status NOT_ESTABLISHED
```

Its blockers are historical truth for its old portfolio path. The new proof is
strategy-native and bound only to the accepted Architecture-142 definition and
verified walk-forward chain.

Architecture 143 must not change any Architecture-139, Architecture-141, or
Architecture-142 artifact schema, namespace, identity, serialized bytes, or
accepted behavior.

## Prohibited capabilities

The future module must not instantiate, parse for authority, serialize as
output, or create:

```text
ProductionStrategyContract
PAPER_CANDIDATE
AWAITING_HUMAN_PROMOTION
production strategy decision
promotion eligibility
production replacement/selection state
review-paper authority
D1/D1R9 authority
```

It must not call `build_production_strategy` or instantiate
`MovingAverageCrossoverStrategy` merely to prove compatibility. It must not
acquire data or access filesystem, network/socket, provider APIs, credentials,
Robinhood, broker/execution adapters, production SQLite/stores, scheduler,
ACL/native-host mutation, GUI composition, subprocesses, the current clock, or
UUID4/randomness. The accepted 142 verifier may perform deterministic in-memory
research replay; that is verification computation, not operational authority.

## Zero-effect contract

The exact Architecture-143 accounting contract is:

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
STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0
PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0
D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

The proof is a pure in-memory research-evidence artifact. It does not create
or mutate a store, scheduler, release, account, credential, paper state,
production state, or operator-control state.

## Lifecycle boundary

Architecture 143 proves semantic compatibility only. It does not create
`PAPER_CANDIDATE`, move any lifecycle stage, create `ProductionStrategyContract`,
approve promotion, select a production session, authorize paper or live
trading, authorize D1/D1R9/D2, or authorize provider access.

A later separately reviewed architecture may consume a verified Architecture-
143 proof to define paper-candidate materialization or eligibility. Human
promotion remains later, separate, and explicit. Real-money trading remains
NO-GO.

## Planned implementation surface

The next isolated source checkpoint is limited approximately to:

```text
src/trading_bot/experiments/research_strategy_production_compatibility.py
tests/experiments/test_research_strategy_production_compatibility.py
src/trading_bot/experiments/__init__.py
```

Only the exact source/test files in the frozen surface, plus the narrowly
permitted mechanically required current-inventory/authority successor overlay
described above, may be added after actual inventory recomputation. No
Architecture-139, 141, or 142 artifact schema, namespace, identity, or
accepted source behavior may change. Workflow YAML, D1R9, and operational
authority remain prohibited.

## Required future test contract

The future implementation must add focused coverage for at least:

- exact target field set, deterministic target UUID5 identity, and canonical
  JSON roundtrip;
- deterministic proof identity, exact proof field set, and canonical JSON
  roundtrip;
- a legitimate exact match whose complete 142-B chain is replay-verified;
- independent verification of a legitimate exact proof;
- symbol, `short_window`, `long_window`, and `desired_quantity` mismatches;
- production source HEAD and TREE mismatches;
- production schema, strategy family, and strategy version drift;
- wrong completed walk-forward, qualification, qualification policy, or passed
  artifact;
- wrong qualification source HEAD/TREE;
- tampered underlying fold/backtest evidence rejected before compatibility;
- parsed self-consistent target alone grants no authority;
- parsed self-consistent proof alone cannot satisfy external verification;
- target/proof parsing performs no research execution;
- Architecture-141 artifacts and bytes remain unchanged;
- Architecture-142 schemas, namespaces, identities, and accepted behavior
  remain unchanged;
- AST/capability restrictions and exact zero-effect accounting; and
- successor-overlay and inventory fail-closed behavior.

## Publication and next checkpoint

At design freeze, this was one docs-only logical checkpoint whose
source/test/workflow surface was intentionally unchanged. Its recorded next
checkpoint was the isolated Architecture-143 source implementation with
focused tests and static capability checks. That checkpoint is now accepted as
described above. The frozen contract still preserves the exact 142 source
boundary and stops before any production, paper, broker, scheduler, D1R9, D2,
provider, credential, or live effect.

D1R9 remains separate and untouched.
