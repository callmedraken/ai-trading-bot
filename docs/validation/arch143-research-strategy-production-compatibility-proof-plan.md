# Architecture 143 / RCL-6 — Research Strategy Production Compatibility Proof Plan

Status: **ARCHITECTURE 143 / RCL-6 DESIGN FROZEN; SOURCE NOT IMPLEMENTED**.

This validation record freezes the future implementation and acceptance
boundary. It does not add executable source, tests, checkpoint-runner logic,
workflow changes, or operational authority in the current checkpoint.

## Validation objective

Prove that one accepted Architecture-142 strategy-native definition and its
fully replay-verified 142-B PASS chain have exact semantic compatibility with
one explicit inert `ProductionStrategySemanticTarget`.

The proof is positive-only. A mismatch must raise and must not emit an artifact.
Canonical parsing proves only self-consistency and never substitutes for
external research replay, chain reconciliation, or semantic comparison.

Architecture 141 remains immutable `SHADOW` / `NOT_ESTABLISHED` evidence for
its old portfolio candidate. The validation plan does not consume it as a
bridge and does not rewrite its bytes or blockers.

## Frozen admission and source boundary

The design was admitted from this exact clean checkout:

```text
worktree F:\AI\worktrees\ai-trading-bot-architecture-143-design-freeze
branch   develop
upstream origin/develop
base HEAD  a0defb4a5c568e6afc78a76a325509396a9d327e
base TREE  50f6e193e917132dd596155115bbc1fc73691f4f
```

The accepted 142-B interface boundary is the exact final feature commit
`e88f38f8deeb834ac3f162b6a82e328dc4708ad0`. The future implementation consumes
its public definition, walk-forward, qualification, and passed-artifact
interfaces through the external verifier; it does not copy or merge feature
source into `develop` as part of this design freeze.

The future source checkpoint has two separate authorities:

```text
executable predecessor  e88f38f8deeb834ac3f162b6a82e328dc4708ad0
design authority        3d66d1a3a7629eb07fcdef9fd1d6ed9f68d1bd87
```

Create the future feature branch/worktree from the exact accepted 142 commit,
not from `develop`:

```text
branch   feature/research-strategy-production-compatibility-current
worktree F:\AI\worktrees\ai-trading-bot-research-strategy-production-compatibility-current
```

The future implementation must preserve `e88f38f` as the direct executable
predecessor and read the frozen Architecture-143 documents from exact design
commit `3d66d1a3a7629eb07fcdef9fd1d6ed9f68d1bd87` using read-only `git show` or
an equivalent. It must not merge, cherry-pick, rebase, or copy 142 source into
`develop`, and must not merge/cherry-pick the 143 docs commit into the feature
source merely to obtain documentation. Every implementation report must state
both authorities separately.

Future source scope is approximately:

```text
src/trading_bot/experiments/research_strategy_production_compatibility.py
tests/experiments/test_research_strategy_production_compatibility.py
src/trading_bot/experiments/__init__.py
```

Only mechanically required current inventory/authority successor overlays and
their exact tests may be added after actual inventory recomputation. Workflow
YAML, D1R9, and operational authority remain prohibited. The source
implementation must not change Architecture-139, 141, or 142 schemas,
namespaces, identities, serialized bytes, or accepted behavior.

`scripts/checkpoint_runner.py` remains unchanged unless actual local inventory
recomputation and affected current-authority tests prove that a new supported
Architecture-143 test surface mechanically requires a successor overlay. If
required, the only permitted change is an additive, fail-closed Architecture-
143 overlay that composes after the frozen Architecture-142-B overlay. The
accepted 142-A and 142-B dictionaries/digests remain frozen and byte unchanged.
The overlay may cover only exact current inventory/authority test blobs that
actually changed because of Architecture-143 inventory admission. No
historical pin may be rewritten in place and no unrelated source pin may be
changed. Actual inventory must be recomputed, never guessed. Current inventory
tests may change only for mechanically measured membership/count effects of the
new supported test surface. If no successor overlay is mechanically required,
`checkpoint_runner.py` must remain unchanged. This is narrow source-authority
bookkeeping, not operational authority.

## Frozen artifacts

### Production semantic target

```text
type                   ProductionStrategySemanticTarget
schema                 production-strategy-semantic-target/v1
identity version       production-strategy-semantic-target-identity/v1
UUID5 namespace        16be4a92-15d8-5db1-9f92-17a3dbd195f3
```

Exact fields:

```text
schema, target_id, production_source_head, production_source_tree,
production_strategy_schema, strategy_id, strategy_version, symbol,
strategy_config
```

The production schema/family/version are fixed from
`PRODUCTION_STRATEGY_SCHEMA`, `MOVING_AVERAGE_STRATEGY_ID`, and
`MOVING_AVERAGE_STRATEGY_VERSION`. Symbol and config are exact inert
`Symbol`/`MovingAverageCrossoverConfig` values. There is no
`target_session_date`.

Target UUID5 material is length-framed UTF-8, in exactly this order:

```text
production-strategy-semantic-target-identity/v1
schema
production_source_head
production_source_tree
production_strategy_schema
strategy_id
strategy_version
str(symbol)
str(config.short_window)
str(config.long_window)
canonical_decimal(config.desired_quantity)
```

Source HEAD/TREE are provenance material only; they do not prove GitHub/source
acceptance or deployment authority.

### Compatibility proof

```text
type                   ResearchStrategyProductionCompatibilityProof
schema                 research-strategy-production-compatibility-proof/v1
identity version       research-strategy-production-compatibility-proof-identity/v1
UUID5 namespace        f9f82ac4-219d-512d-bfe9-a1c07c9427a1
```

Exact final fields, in the frozen semantic/identity order, are:

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

Proof UUID5 material is length-framed UTF-8 in this exact order, excluding the
derived `proof_id`:

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
str(config.short_window)
str(config.long_window)
canonical_decimal(config.desired_quantity)
proof_source_head
proof_source_tree
```

The future JSON parsers must reject floats, nonfinite Decimal values,
bool-as-int, unknown/missing/duplicate fields, noncanonical UUIDs or source
digests, noncanonical Decimal text, random UUIDs, clocks, `repr()`, Python
hash/object identity, filesystem paths, and serialized Python object bytes.
Canonical Decimal rendering must match the accepted production and 142
contracts without ambient Decimal-context dependence.

## Required external verification sequence

The public builder and verifier must accept independently supplied 142-B chain
inputs and explicit qualification provenance. The minimum required call is:

```python
verify_walk_forward_passed_research_strategy(
    passed,
    qualification,
    completed,
    qualification_policy,
    qualification_source_head=qualification_source_head,
    qualification_source_tree=qualification_source_tree,
)
```

The builder must perform this sequence:

1. validate exact artifact types and canonical inputs;
2. replay every 142-B fold/backtest through the accepted external verifier;
3. reconcile completed definition, evidence, qualification, policy, and passed
   lineage exactly;
4. validate the explicit target independently;
5. compare all seven exact semantic/source equalities;
6. reject every mismatch before proof construction; and
7. construct the deterministic proof from the exact frozen field set.

The verifier must repeat steps 1–6 from independently supplied inputs, rebuild
the expected proof including `proof_source_head/tree`, and require exact object
equality. A parsed proof or target alone is insufficient.

The parsers must not execute research, call the external verifier, acquire
data, inspect the filesystem/network, or establish any authority. There is no
persisted verified flag.

## Exact comparison matrix

The future implementation must enforce:

| Completed 142 definition | Semantic target |
| --- | --- |
| `production_strategy_schema` | `production_strategy_schema` |
| `strategy_id` | `strategy_id` |
| `strategy_version` | `strategy_version` |
| `symbol` | `symbol` |
| `strategy_config` | `strategy_config` |
| `strategy_source_head` | `production_source_head` |
| `strategy_source_tree` | `production_source_tree` |

Comparison is exact value equality. No mapping from names, metadata, rank,
optimizer settings, historical universe, branch, filename, proposal behavior,
numeric coincidence, or ambient state is allowed.

## Required focused test matrix for the future source checkpoint

The future test module must cover at least the following groups.

### Target and proof transport

- exact target field set and exact proof field set;
- deterministic target UUID5 and proof UUID5 identities;
- canonical JSON roundtrip for target and proof;
- rejection of unknown, missing, duplicate, noncanonical, float, nonfinite,
  bool-as-int, random, clock-derived, and serialized-object inputs;
- source digest and canonical UUID validation;
- proof construction with no caller-settable compatibility/status flag.

### Positive full-chain proof

- a legitimate exact match creates a proof only after complete external replay;
- an exact legitimate proof independently verifies;
- every underlying fold/backtest is replayed before compatibility succeeds;
- completed definition, qualification, policy, passed artifact, and all source
  provenance reconcile exactly;
- proof identity changes when any bound semantic or provenance field changes.

### Negative semantic/provenance cases

- symbol mismatch;
- `short_window` mismatch;
- `long_window` mismatch;
- `desired_quantity` mismatch;
- production source HEAD mismatch;
- production source TREE mismatch;
- production schema/family/version drift;
- wrong completed walk-forward;
- wrong qualification;
- wrong qualification policy;
- wrong passed artifact;
- wrong qualification source HEAD/TREE; and
- tampered underlying fold/backtest evidence.

Every mismatch must raise before a proof artifact is created.

### Authority and immutability

- a self-consistent parsed target grants no authority;
- a self-consistent parsed proof cannot satisfy external verification;
- target/proof parsing performs no research execution;
- no `ProductionStrategyContract`, `PAPER_CANDIDATE`, promotion, production
  selection, review-paper authority, D1/D1R9/D2 authority, or provider access;
- no `build_production_strategy` call and no strategy instantiation merely for
  comparison;
- Architecture-141 artifact/bytes remain unchanged;
- Architecture-142 schemas/namespaces/identities/behavior remain unchanged;
- AST/capability restrictions remain closed; and
- the exact zero-effect accounting remains all zero.

### Inventory and successor behavior

- current inventory/successor overlays fail closed when the future module or
  test ownership is missing or misclassified;
- only mechanically required overlays are admitted; and
- no historical 139/141/142 test is weakened or repurposed as current proof
  coverage.

## Zero-effect assertions

The future tests must assert exactly:

```text
PRODUCTION_SQLITE_READS=0        PRODUCTION_SQLITE_WRITES=0
CREDENTIAL_READS=0               PROVIDER_CALLS=0
ROBINHOOD_READS=0                BROKER_CALLS=0
SCHEDULER_CALLS=0                ACL_MUTATIONS=0
PAPER_MUTATIONS=0                STRATEGY_PROMOTIONS=0
PRODUCTION_CONTRACTS_CREATED=0   PAPER_CANDIDATES_CREATED=0
D1_OPERATIONS=0                  D1R9_OPERATIONS=0
D2_SUPERVISOR_EXECUTIONS=0
```

Deterministic in-memory replay by the accepted 142 verifier is verification
computation only and is not an external operational effect.

## Capability restrictions

The future implementation must be statically and dynamically checked to
exclude filesystem, network/socket, provider, credentials, Robinhood,
broker/execution, production SQLite/store, scheduler, ACL/native-host, GUI,
subprocess, current-clock, and randomness capabilities. It must not import or
construct `ProductionStrategyContract`, call `build_production_strategy`, or
consume Architecture-141 portfolio artifacts.

## Lifecycle and protected boundary

The proof establishes semantic compatibility only. It does not create
`PAPER_CANDIDATE`, change lifecycle stage, create a production contract,
approve promotion, select a production session, authorize paper/live trading,
or authorize D1/D1R9/D2/provider access. A later separately reviewed
architecture must define any paper-candidate materialization or eligibility.

Real-money trading remains NO-GO. D1R9 remains separate and untouched.

## Docs-only freeze verification and publication

For this design-only checkpoint:

1. verify the exact clean admission identity and preserve the old dirty
   repository outside this worktree;
2. create only the two new design/validation docs and bounded status/handoff
   updates;
3. confirm no source, test, `checkpoint_runner.py`, workflow, 139, 141, 142,
   D1R9, or operational files changed;
4. run `git diff --check`;
5. stage only the exact four documentation paths;
6. inspect the staged filename set and staged diff; and
7. create one atomic docs commit and one ordinary push/ref advance followed by
   terminal GitHub source-gate admission.

No full, Robinhood, legacy, or exhaustive test profile is required for this
docs-only checkpoint because executable/test source is unchanged. Existing
142 acceptance evidence remains authoritative and must not be rerun merely for
this documentation closeout.

If a planned docs-only source-gate run is red, preserve its evidence and stop;
only a clearly classified bounded mechanical documentation correction may be
handled as a separately declared corrective checkpoint.

## Next checkpoint

The next milestone is the isolated Architecture-143 source implementation and
its focused validation matrix above. It must use the frozen proof contract and
stop at the pure semantic proof boundary. No merge or cherry-pick of the
accepted 142 feature source is part of that implementation checkpoint.
