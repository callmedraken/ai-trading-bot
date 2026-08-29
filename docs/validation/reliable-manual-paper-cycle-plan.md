# Reliable manual paper-cycle validation plan

This plan validates Architecture 94. It is intentionally staged so pure/offline
logic is proven before any paper-account mutation boundary is admitted, and so
no test or acceptance step can authorize another Alpaca/provider effect.

## Global gate rules

- Production/live trading remains NO-GO.
- No provider call #7 is authorized by this plan.
- No test may construct the production C3 effect adapter unless it is an
  existing inert/unit seam that cannot launch a provider child; the preferred
  Architecture-94 tests use no C3 effect adapter at all.
- No test may access Windows Credential Manager or perform an ad-hoc remote
  authentication probe.
- Broker submission/cancel/replace remains absent.
- The accepted call-#5 and call-#6 C3 lineages are read-only historical state.
- `/v2` credential references are not modified, deleted, or restaged.
- Focused tests run during implementation. The expensive complete repository
  suite is reserved for final certification of the unchanged source tree.
- Disposable authority/account roots used in tests must be explicit test seams;
  the production-style manual command must remain bound to the code-owned root.

## A94 architecture post-write review

Before source implementation:

1. prove the branch parent is the accepted integrated `develop` head
   `bd88ee966bff455f9fc897d6cfdfafdd807f27e2`;
2. prove the architecture commits are docs-only;
3. review Architecture 94 against Architectures 18, 19, 23, 56, 62, 63, 66,
   67, 77, 81, 82, and 83;
4. confirm no accepted deterministic identity, schema, serializer, production
   SQL, GUI contract, C3 effect/retry rule, or paper-operation commit rule was
   silently superseded;
5. confirm the selected C3 daily snapshot is treated as one target-session bar
   per symbol and that the moving-average history gap is explicit rather than
   inferred;
6. confirm all source implementation remains blocked until this review passes.

Expected result: `ARCHITECTURE_94_FREEZE=ACCEPTED`.

## A94-A — pure strategy-history and strategy-plan contracts

### Contract tests

Cover the canonical offline history seed:

- exact schema/version and UUID5 identity;
- strict JSON/canonical serialization and byte-for-byte replay;
- SHA-256/byte-length evidence separate from semantic identity;
- one-symbol v1 universe only;
- valid daily bars and exact XNYS descriptor;
- unique strictly increasing sessions;
- required consecutive suffix for the configured long window;
- seed terminal session is exactly the modeled session immediately before the
  selected C3 target session;
- future/equal/current-session history is rejected;
- malformed, missing, duplicate, extra, noncanonical, over-bound, and wrong
  symbol/calendar material is rejected;
- no provider, filesystem mutation, clock, broker, GUI, or C3 authority
  dependency exists in pure parsing/verification.

Cover deterministic strategy planning:

- a complete seed plus selected C3 bar creates the exact existing
  `MovingAverageCrossoverStrategy` context;
- equal semantic inputs create equal strategy plan/proposal/target/request IDs;
- changed history, selected snapshot, account tip, strategy config, policies,
  open-reference assertions, or idempotency key changes the appropriate plan
  identity;
- paths, wall clock, Python hash/object identity, environment values, and
  serialized artifact location do not affect semantic identities;
- bullish crossover while flat produces the expected strategy BUY proposal;
- bearish crossover while invested produces the expected full-position SELL
  proposal;
- no crossover produces explicit `NO_SIGNAL`;
- non-actionable genuine crossovers preserve existing baseline strategy
  semantics rather than deferring a signal;
- strategy proposal is converted to an exact representable target or planning
  blocks; no silent rounding/capping/resizing occurs in the bridge;
- planner/proposal output must exactly reconcile symbol/side/desired quantity
  with a nonempty strategy signal before risk can run;
- `NO_SIGNAL` must produce no executable planner proposal;
- strategy-plan metadata binds plan ID plus plan artifact SHA-256/byte length to
  the exact existing checkpointed-cycle request;
- pure plan replay reconstructs the same request without executing a paper
  cycle.

### Focused gate

Run only new strategy-history/plan tests plus directly affected existing
verified-snapshot preparation, planner/proposal, strategy, and risk tests.

Do not run the full repository suite here.

## A94-B — read-only selected-C3-snapshot authority

### Production construction boundary

Test that genuine production-style construction requires a
`ValidatedProductionAuthority` and the exact fixed production SQLite/capture
layout. Disposable tests may use explicitly named authority fixtures.

Prove the selected-snapshot reader:

- opens SQLite read-only through the approved VFS;
- validates installed database/schema/identity prerequisites;
- exposes no mutating transactional methods;
- never constructs `WindowsEffectfulDailySnapshotCapture`;
- never constructs a provider, reads credentials, launches a child, resumes a
  process, allocates an attempt, records a terminal, or inserts a selection;
- cannot be subclassed or reconstructed into a valid production permit through
  public constructors, copying, pickling, dataclass lookalikes, UUIDs, digests,
  paths, or snapshot bytes.

### Durable selected-lineage tests

Use disposable validated authority databases to cover:

- exact `SUCCESS_SELECTED` session + attempt;
- exact `SUCCEEDED / CONFIRMED` terminal;
- exactly one matching `session_selections` row;
- exact selection/session/terminal linkage;
- exact terminal/selection snapshot digest agreement;
- absent selection;
- wrong session/attempt state;
- failed/ambiguous terminal;
- non-CONFIRMED disposition;
- duplicate/inconsistent linkage where schema/test seams permit it;
- unsupported/malformed evidence;
- wrong selection assertion;
- database/schema/authority identity mismatch;
- no newest/latest/time/row-order fallback.

### Artifact reconciliation tests

Cover:

- explicit transport path under the fixed capture output root only;
- safe regular-file/reparse/device protections;
- bounded read;
- artifact SHA mismatch;
- strict daily-snapshot verification failure;
- snapshot-ID mismatch with durable terminal evidence;
- byte-length retention;
- path substitution/race detection required by the existing production
  file-safety policy;
- no directory scan, fallback filename, provider recovery, or network access.

### Accepted-C3 read-only acceptance

After all unit/integration gates pass, one supervised read-only local acceptance
may inspect the already-consumed accepted call-#6 selection:

```text
selection: 36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
snapshot: eba46838-44ae-5bec-97bf-98c6639ae6a7
artifact SHA-256: 31d82a31a3fbd909f8771820bf47e796a1503264fe0ac6ce0eff7ba163f0767d
artifact byte length: 1291
terminal: SUCCEEDED / CONFIRMED
session/attempt: SUCCESS_SELECTED
```

The acceptance command must prove `PROVIDER_CALL_PERFORMED=False` or an
otherwise equivalent zero-provider invariant from the Architecture-94 service
surface. It must not invoke the production capture CLI.

Do not run the full repository suite here.

## A94-C — authoritative manual paper account

### Fixed-root/anchor tests

Cover:

- code-owned `F:\AITradingBot\Paper` production-style root;
- rejection of caller-selected production roots;
- disposable roots available only through explicit tests;
- exact owner/SID/DACL/inheritance/object-type/reparse policy;
- immutable account anchor strict schema/canonical material;
- anchor binds account ID, approved machine/principal facts, and exact genesis
  checkpoint ID/SHA-256/byte length;
- alternate/mutated/missing genesis is rejected;
- no credentials or provider/broker configuration exists in paper authority.

### Graph-derived current-tip tests

Construct bounded disposable layouts covering:

- genesis-only account -> genesis is unique tip;
- one and multiple valid successor transitions -> final unique verified tip;
- stale explicit lineage when a later verified successor exists;
- fork from one predecessor;
- disconnected alternate genesis;
- cycle/reuse conflicts;
- malformed recognized operation/transition state;
- staging remnants;
- invalid transition bytes;
- invalid successor edge;
- invalid full lineage;
- unsafe objects and reparse substitutions;
- case-fold collisions;
- enumeration bound exceeded;
- unknown state that cannot be safely ignored;
- deterministic derivation independent of filenames/timestamps/listing order.

No test may define the current operational account by sorting filenames or file
modification times.

### Concurrency/lifecycle tests

Cover one account-scoped mutex:

- one holder admits, second contender blocks/fails closed according to policy;
- mutex security/owner policy is validated;
- complete account state is revalidated after lock acquisition;
- a changed tip between initial preflight and locked admission blocks stale
  execution;
- lock release occurs only after Architecture-67 execution/recovery returns to
  a durable classified state;
- crash/recovery tests prove the mutex never substitutes for durable evidence.

Use native Windows acceptance only when explicitly opted in. Ordinary focused
unit tests must remain safe and disposable.

## A94-D — authority/composition join

Test the new composition root with selected snapshot, paper-account authority,
and verified strategy plan.

Prove:

- selected-snapshot permit, paper-account permit, account/tip evidence, and plan
  all belong to the same exact operation;
- lookalike/reconstructed permits are rejected;
- prior terminal checkpoint equals the graph-derived current tip;
- plan snapshot evidence equals the durable selected C3 snapshot evidence;
- plan prior-account evidence equals the authoritative account evidence;
- strategy-plan replay regenerates the exact checkpointed-cycle request;
- the existing `VerifiedPaperOperationInputs` semantics are preserved;
- the existing read-only Architecture-67 inspection is performed before
  execution admission;
- changed selection, changed account tip, changed plan bytes, changed history,
  changed config, or changed operation state blocks instead of rebinding;
- no C3 mutation/provider method and no broker method is reachable through the
  composition root.

### Risk bypass negative tests

Deliberately attempt to:

- feed a strategy proposal directly to order creation;
- fabricate an approved risk result;
- skip the existing risk orchestrator;
- replace a resized/rejected risk decision with the strategy quantity;
- invoke paper submission from the pre-risk plan.

Every route must be impossible through the public Architecture-94 composition
surface or fail closed before any paper-account transition is committed.

## A94-E — manual CLI

The production-style CLI exposes only explicit `--inspect-only` and
`--execute-once` modes.

Test:

- exactly one mode is required;
- no capture/provider/credential/broker/scheduler/retry/latest flags exist;
- production paper root is not caller-selectable;
- exact selection and plan/config inputs are assertions, not authority;
- inspect-only is read-only;
- execute-once performs the locked second preflight before delegating;
- PENDING executes the existing paper runtime at most once;
- ALREADY_APPLIED returns without runtime calls or writes;
- finalized transition without receipt uses only the existing verified
  zero-runtime-call receipt recovery;
- deterministic failed receipt prevents rerun;
- staging/ambiguous/conflicting state blocks;
- raw parser/native/filesystem/provider details are not exposed to the operator.

No GUI execution control is added in this milestone.

## A94-F — crash/recovery and durable-evidence integration

Run focused Architecture-67 regression plus new cross-boundary cases at every
new failure window introduced by Architecture 94:

1. before selected-snapshot read permit issuance;
2. after selected-snapshot permit but before paper-account lock;
3. after lock but before second account-tip revalidation;
4. after account revalidation but before strategy-plan revalidation;
5. after complete second preflight but before Architecture-67 delegation;
6. every existing Architecture-67 staging/finalization/receipt window.

For each window record:

- durable predecessor;
- whether paper runtime was called;
- whether a finalized transition can exist;
- current operator classification;
- permitted recovery;
- whether runtime retry is permitted.

The expected rule is conservative: Architecture-94 pre-delegation failures have
no committed paper transition; once Architecture 67 is entered, Architecture 67
alone determines transition/receipt/recovery truth.

## Supervised manual simulated-paper acceptance

Only after A94-A through A94-E focused gates are accepted:

1. use the already-selected call-#6 C3 artifact read-only;
2. use one provisioned fixed manual paper account anchored to a reviewed
   genesis checkpoint;
3. use one explicit offline history seed whose terminal seed session immediately
   precedes the selected snapshot session;
4. run `--inspect-only` and require exact `PENDING` with zero provider/broker
   effects;
5. review the complete strategy-plan/proposal/risk evidence;
6. invoke `--execute-once` exactly once;
7. verify the finalized transition, receipt, successor edge, and complete
   account lineage offline;
8. rerun inspect/execute classification only as needed to prove
   `ALREADY_APPLIED`/zero-runtime-call idempotency; do not perform a new strategy
   or provider effect under the same operation identity.

Acceptance succeeds only if the complete durable chain proves:

```text
selected C3 evidence
-> offline seed + current C3 bar
-> deterministic strategy proposal/no-signal
-> exact target/planner proposal reconciliation
-> deterministic risk
-> simulated paper order/fill/application
-> verified successor checkpoint
-> verified full lineage
-> finalized Architecture-67 transition
-> verified receipt
```

## Final certification

After all focused and manual acceptance gates pass and the source tree is frozen:

1. run the focused Architecture-94 cross-boundary suite;
2. run Ruff check;
3. run Ruff format check;
4. run `git diff --check`;
5. run the complete repository pytest suite exactly once for final
   certification of the unchanged source tree;
6. confirm expected Windows native opt-in/environment skips only and zero
   failures;
7. confirm the worktree is clean except for explicitly preserved unrelated
   generated/untracked artifacts;
8. exact-review the final GitHub diff before merge-readiness is declared.

A docs-only follow-up after source certification does not require another full
repository run when exact diff review proves no source/test change.

## Model routing

- Architecture/security/authority/crash-recovery changes: ChatGPT/Sol High for
  design/review; Codex Sol High only for bounded implementation after the
  relevant sub-contract is frozen.
- Pure deterministic strategy-history/strategy-plan contracts: Sol Medium.
- Canonical serializers/parsers and subtle plan verification: Sol Medium.
- Selected-C3 read authority and manual paper-account root/tip/mutex: Sol High.
- Authority/composition join: Sol High initially; only clearly mechanical
  follow-up wiring may drop to Luna Extra High.
- Frozen CLI plumbing, exports, localized fixture updates, and formatting:
  Luna Extra High.

Codex must run only focused tests/checks for its changes and report the exact
commands for the user's final local verification. No subagents are used unless
explicitly requested.
