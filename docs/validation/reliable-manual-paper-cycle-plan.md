# Reliable manual paper-cycle validation plan

This plan validates Architecture 94. The implementation stages are named
`P1` through `P6` exactly as in the architecture document.

The gates are ordered so pure/offline behavior is proven before paper-account
mutation can be admitted. Nothing in this plan authorizes another
Alpaca/provider effect.

## Global gate rules

- Production/live trading remains NO-GO.
- No provider call #7 is authorized.
- Call #5 and call #6 C3 lineages are read-only historical state and are never
  retried.
- `/v2` Alpaca credentials are not modified, deleted, or restaged.
- No test may access Windows Credential Manager or perform an ad-hoc remote
  authentication probe.
- No broker submit/cancel/replace path is added.
- Architecture-94 tests should not construct the production C3 effect adapter;
  selected-snapshot tests use a read-only authority boundary.
- Focused tests/checks run during implementation. The complete repository suite
  is reserved for final certification of the unchanged source tree.
- Disposable roots/databases are explicit test seams only. Production-style
  manual paper operation remains bound to code-owned roots and validated
  authority.

## Architecture-94 post-write gate

Before source implementation:

1. prove the feature branch descends directly from accepted integrated
   `develop` head `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`;
2. prove the architecture checkpoint changes documentation only;
3. review Architecture 94 against Architectures 18, 19, 23, 56, 62, 63, 66,
   67, 77, 81, 82, and 83;
4. confirm no accepted deterministic identity, schema, serializer, production
   SQL, GUI contract, C3 effect/retry rule, or Architecture-67 commit rule was
   silently superseded;
5. confirm the selected C3 snapshot is treated as one target-session bar per
   symbol and the moving-average history gap is explicit;
6. confirm all implementation remains blocked until this gate passes.

Expected result:

```text
ARCHITECTURE_94_FREEZE=ACCEPTED
```

## P1 — Pure strategy history and strategy plan

P1 performs no production-authority operation and no durable mutation.

### History-seed contract

Cover:

- strict `strategy-history-seed/v1` schema and canonical serialization;
- deterministic UUID5 semantic identity;
- artifact SHA-256/byte length retained separately from semantic identity;
- exactly one symbol in v1;
- exact XNYS calendar descriptor;
- valid daily bars with unique strictly increasing sessions;
- configured-long-window suffix is consecutive modeled XNYS sessions;
- final seed session is exactly the modeled session immediately before the
  selected C3 target session;
- equal/future target-session data is rejected;
- malformed, missing, duplicate, extra, noncanonical, over-bound, wrong-symbol,
  and wrong-calendar material is rejected;
- pure parser/verifier depends on no provider, broker, GUI, clock, production
  authority, or filesystem mutation.

### Strategy-plan contract

Cover:

- seed bars plus selected C3 bar reconstruct the exact existing
  `MovingAverageCrossoverStrategy` context;
- account positions come only from verified prior paper-account state;
- equal semantic inputs produce equal plan/proposal/target/request identities;
- changed history, selected snapshot, prior account, strategy config, policy,
  open-reference assertion, or idempotency key changes the appropriate identity;
- paths, wall clock, environment values, Python hash/object identity, and
  artifact location do not affect semantic IDs;
- bullish crossover while flat produces expected BUY proposal;
- bearish crossover while invested produces expected full-position SELL;
- no crossover produces explicit `NO_SIGNAL`;
- existing non-actionable crossover behavior remains unchanged;
- strategy proposal converts to an exact representable target or planning
  blocks; there is no silent rounding/capping/resizing;
- planner proposal exactly reconciles symbol/side/desired quantity with a
  nonempty strategy signal before risk is permitted;
- `NO_SIGNAL` produces no planner proposal;
- identical canonical request cores produce deterministic detached plan-artifact
  binding evidence and the same reconstructed request;
- the canonical plan binds the complete semantic checkpointed-cycle request core
  without serializing its own artifact SHA-256 or byte length;
- canonical plan serialization is followed by detached artifact SHA-256/byte
  length computation and exact three-entry `architecture94.` metadata injection
  in frozen order;
- caller/base `architecture94.` metadata is rejected, while caller metadata
  order and existing checkpointed-cycle reserved prefixes remain unchanged;
- changing plan artifact bytes changes detached artifact evidence and the
  reconstructed request, while semantic-equivalent canonical inputs remain
  deterministic;
- pure replay recomputes the plan ID, SHA-256, and byte length and reconstructs
  the exact final existing checkpointed-cycle request without running a paper
  cycle;
- tampered plan bytes, plan ID, SHA-256, byte length, or injected metadata fail
  closed;
- no existing checkpointed-cycle, preparation, runtime, or Architecture-67
  schema change is required.

### P1 focused gate

Run new P1 tests plus directly affected strategy, verified-snapshot preparation,
planner/proposal, and risk tests. Run Ruff on changed Python/test paths and
`git diff --check`.

Do not run the full repository suite.

## P2 — Read-only selected-C3 snapshot authority

P2 may read production authority state only through the reviewed read-only
boundary. It may not mutate C2/C3 state or contact a provider.

### Construction and capability tests

Prove:

- genuine production construction requires `ValidatedProductionAuthority`;
- fixed production SQLite/capture layout is enforced;
- SQLite opens read-only through approved VFS;
- installed schema/identity prerequisites are validated;
- joined selection evidence is read in one consistent read transaction;
- no mutating transactional methods are exposed;
- `WindowsEffectfulDailySnapshotCapture` is never constructed;
- no provider, credential read, child launch/resume, attempt allocation,
  terminal mutation, selection mutation, or recovery method is reachable;
- selected-snapshot permit cannot be forged by public construction,
  subclassing, copying, pickling, UUID/digest/path knowledge, lookalike objects,
  or snapshot bytes.

### Durable selection tests

Using disposable validated authority databases, cover:

- exact `SUCCESS_SELECTED` session and attempt;
- exact `SUCCEEDED / CONFIRMED` terminal;
- exactly one matching `session_selections` row;
- exact selection/session/terminal linkage;
- exact terminal/selection snapshot-digest agreement;
- absent selection;
- wrong session/attempt state;
- failed/ambiguous terminal;
- non-CONFIRMED disposition;
- inconsistent linkage/evidence;
- unsupported schema/authority identity;
- wrong selection assertion;
- no newest/latest/timestamp/row-order fallback.

### Artifact reconciliation tests

Cover:

- explicit transport path must remain beneath fixed capture-output root;
- safe regular-file/reparse/device/identity protections;
- bounded read;
- SHA mismatch;
- strict daily-snapshot verification failure;
- snapshot-ID mismatch with terminal evidence;
- exact byte-length/digest retention;
- path substitution/race protections required by production file safety;
- no directory scan, fallback filename, provider recovery, or network access.

### Read-only accepted-C3 local acceptance

After P2 focused gates pass, one supervised read-only acceptance may inspect the
already-consumed accepted call-#6 selection:

```text
selection: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
terminal: SUCCEEDED / CONFIRMED
session/attempt: SUCCESS_SELECTED
```

The command must prove an equivalent of `PROVIDER_CALL_PERFORMED=False` from the
Architecture-94 surface and must not invoke the production capture CLI.

Do not run the full repository suite.

## P3 — Manual paper-account authority

### Fixed root and anchor

Cover:

- production-style root is code-owned `F:\AITradingBot\Paper`;
- caller-selected production roots are rejected;
- disposable roots require explicit test seams;
- owner/SID/DACL/inheritance/object-type/reparse policy is enforced;
- account anchor has strict canonical schema/material;
- anchor binds account ID, approved machine/principal facts, and exact genesis
  checkpoint ID/SHA-256/byte length;
- missing/alternate/mutated genesis is rejected;
- authority contains no credentials or broker/provider settings.

### Graph-derived current tip

Disposable layouts cover:

- genesis-only account -> genesis is unique tip;
- one/multiple valid successor transitions -> final unique verified tip;
- stale explicit lineage when a later verified successor exists;
- fork from one predecessor;
- disconnected alternate genesis;
- cycle/reuse conflicts;
- malformed recognized state;
- staging remnants;
- invalid transition bytes/edge/full lineage;
- unsafe/reparse objects;
- case-fold collisions;
- enumeration bound exceeded;
- unknown state that cannot safely be ignored;
- derivation independent of filename, timestamps, mtimes, and listing order.

No code may define the operational account by sorting filenames or choosing a
caller manifest as `latest`.

### Concurrency/lifecycle

Cover:

- one account mutex holder admits; competing holder fails/blocks by policy;
- mutex security is validated;
- complete account state is revalidated after acquisition;
- tip change between first preflight and locked admission blocks stale execution;
- mutex remains held through Architecture-67 execute/recover return to durable
  classification;
- mutex never substitutes for durable transition/receipt evidence.

Native Windows gates remain explicit opt-in; ordinary focused tests are safe and
disposable.

## P4 — Authority/composition join

P4 is the first layer that can delegate to existing paper-account mutation, but
only after complete locked revalidation.

Prove:

- selected-snapshot permit, paper-account authority, current-tip evidence, and
  strategy plan belong to the same exact operation;
- reconstructed/lookalike permits are rejected;
- plan prior checkpoint equals graph-derived current tip;
- plan snapshot evidence equals durable selected C3 evidence;
- plan account evidence equals authoritative paper-account evidence;
- plan replay regenerates exact checkpointed-cycle request;
- existing `VerifiedPaperOperationInputs` semantics are preserved;
- Architecture-67 read-only inspection occurs before mutation admission;
- changed selection/tip/plan/history/config/operation state blocks instead of
  rebinding;
- no C3 mutation/provider or broker method is reachable through composition.

### Risk-bypass negative tests

Attempt to:

- send a strategy proposal directly to order creation;
- fabricate an approved risk result;
- skip the existing risk orchestrator;
- replace a resize/rejection with strategy quantity;
- invoke paper submission from the pre-risk plan.

Every route must be unavailable publicly or fail before paper transition commit.

### Crash-window matrix

Add focused cases for new pre-delegation windows:

1. before selected-snapshot permit issuance;
2. after permit but before account mutex;
3. after mutex but before second account-tip verification;
4. after account verification but before strategy-plan verification;
5. after second preflight but before Architecture-67 delegation;
6. every existing Architecture-67 staging/finalization/receipt window.

For each record durable predecessor, runtime-call possibility, transition
possibility, operator classification, permitted recovery, and runtime-retry
permission.

Expected rule: pre-delegation failures commit no paper transition; after
Architecture 67 is entered, Architecture 67 alone determines transition and
receipt truth.

## P5 — Manual CLI

The production-style CLI exposes only explicit `--inspect-only` and
`--execute-once` modes.

Test:

- exactly one mode required;
- no capture/provider/credential/broker/scheduler/retry/latest flags;
- production paper root is not caller-selectable;
- selection/config paths remain assertions/transport, not authority;
- inspect-only is read-only;
- execute-once performs locked second preflight before delegation;
- `PENDING` calls existing runtime at most once;
- `ALREADY_APPLIED` returns with zero runtime calls/writes;
- finalized transition without receipt uses only existing verified
  zero-runtime-call receipt recovery;
- deterministic failed receipt prevents rerun;
- staging/ambiguous/conflicting state blocks;
- operator output excludes raw parser/native/filesystem/provider detail.

No GUI execute control is added.

## P6 — Supervised simulated-paper acceptance and final certification

Only after P1-P5 focused gates are accepted:

1. use the already-selected call-#6 C3 artifact read-only;
2. use one provisioned fixed paper account anchored to a reviewed genesis;
3. use one explicit offline history seed ending immediately before selected C3
   target session;
4. run `--inspect-only` and require exact `PENDING` with zero provider/broker
   effect;
5. review strategy plan/proposal/target/planner/risk evidence;
6. invoke `--execute-once` exactly once;
7. verify finalized transition, receipt, successor edge, and complete lineage
   offline;
8. prove repeated same-operation classification becomes
   `ALREADY_APPLIED`/zero-runtime-call as appropriate, without a new provider or
   strategy effect under the same operation identity.

Acceptance must prove the offline durable chain:

```text
selected C3 evidence
-> offline seed + selected C3 current bar
-> deterministic strategy proposal/no-signal
-> exact target/planner proposal reconciliation
-> deterministic risk
-> simulated paper order/fill/application
-> verified successor checkpoint
-> verified full lineage
-> finalized Architecture-67 transition
-> verified receipt
```

### Final source certification

On the unchanged final source tree:

1. run focused Architecture-94 cross-boundary gate;
2. run Ruff check;
3. run Ruff format check;
4. run `git diff --check`;
5. run complete repository pytest suite exactly once;
6. require zero failures and only expected opt-in/environment skips;
7. preserve unrelated generated/untracked artifacts;
8. exact-review final GitHub diff before merge-readiness.

A later docs-only correction does not require another full suite when exact diff
proves no source/test change.

## Model routing

- Architecture and authority decisions: ChatGPT/Sol High.
- P1 pure deterministic history/strategy-plan contracts and serializers:
  Codex Sol Medium after the contract is accepted.
- P2 selected-C3 read authority: Codex Sol High.
- P3 fixed paper root/anchor/tip/mutex: Codex Sol High.
- P4 authority/composition/crash-recovery join: Codex Sol High initially.
- P5 frozen CLI plumbing/exports/localized fixtures: Luna Extra High.
- Mechanical formatting or frozen-contract fixture cleanup: Luna Extra High.

Codex runs focused tests/checks only during iteration and reports exact commands
for the user's broad/final local verification. No subagents are used unless
explicitly requested.
