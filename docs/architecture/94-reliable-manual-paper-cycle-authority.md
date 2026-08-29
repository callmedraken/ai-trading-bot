# Reliable manual paper-cycle authority and composition

## Status and purpose

This document freezes Architecture 94 for the first reliable manually invoked
paper cycle after accepted C3 market-data capture and GUI-A7 integration.

The milestone composes already-reviewed deterministic strategy, proposal, risk,
paper-execution, checkpoint, lineage-verification, and restart-safe paper
operation boundaries without turning C3 market-data authority into trading
authority.

The product-level flow is:

```text
selected parent-verified C3 snapshot
+ explicit offline strategy-history seed
+ verified authoritative paper-account tip
        |
        v
pure deterministic strategy plan
        |
        v
existing target/planner/proposal path
        |
        v
existing deterministic portfolio risk
        |
        v
existing simulated paper execution
        |
        v
existing successor checkpoint + full-lineage verification
        |
        v
existing Architecture-67 durable transition + receipt evidence
```

This is simulated paper-account mutation only. It does not authorize a broker,
order submission to an external account, cancel/replace, live trading,
unattended scheduling, automatic retry, or any new market-data provider effect.
Production/live trading remains NO-GO.

## Non-negotiable authority rules

Architecture 94 inherits the production rules established by C1/C2/C3:

- durable state outranks process-local assumptions;
- ambiguous effects fail closed;
- child success cannot create authority;
- paths, filenames, PIDs, environment values, digests, UUIDs, reconstructed
  objects, or caller assertions cannot create alternate authority;
- every order that can reach execution must pass deterministic risk;
- strategy, GUI, AI, schedulers, providers, and future brokerage adapters cannot
  bypass deterministic risk or reviewed authority;
- a read of an already-selected C3 artifact cannot mint C3 capture authority;
- no operation in this milestone may construct
  `WindowsEffectfulDailySnapshotCapture`, access Windows Credential Manager, or
  call an Alpaca provider.

All six accepted real-provider C3 effects remain consumed. Architecture 94
performs no provider call #7. The accepted call-#5 and call-#6 lineages remain
historical and are never retried. `/v2` Alpaca credential references remain
immutable historical state.

## Existing boundaries reused unchanged

The following accepted boundaries remain authoritative and should not be
reimplemented inside Architecture 94.

### Daily-snapshot parsing and offline verification

Architecture 56 remains the sole canonical daily-snapshot parser/verifier and
replay boundary. A selected production artifact is useful to paper planning only
after its exact bytes pass the existing strict offline verifier and reconcile
with durable C3 selection evidence.

### Baseline strategy logic

`MovingAverageCrossoverStrategy` remains the initial deterministic strategy.
Its crossover calculation, long-only position filtering, quantity selection,
and strategy proposal identity remain unchanged.

Architecture 94 does not give that strategy execution authority. It remains a
pure proposal producer.

### Planner, proposals, and risk

The existing rebalance planner/proposal adapter and Architecture-18 portfolio
risk orchestrator remain unchanged. `RiskManager` remains the sole owner of
risk rules, reason codes, and quantity approval/resizing/rejection.

Architecture 94 must not duplicate a risk formula or treat a strategy proposal,
target, plan, paper-operation intent, GUI state, or C3 selection as order
authorization.

### Local order and simulated-paper execution

Architecture 19 and the accepted paper submission/fill/application boundaries
remain unchanged. `PaperPortfolioRuntime` remains the accepted local simulated
paper execution composition where its existing target-based contract is used.

### Checkpoint, successor edge, and full lineage

Architectures 62, 63, and 66 remain unchanged. The accepted checkpointed cycle,
successor-checkpoint construction, prospective successor-edge verification, and
full-lineage verification remain the source of truth for paper-account state
transitions.

### Restart-safe durable operation commitment

Architecture 67 remains the only write/commit algorithm for one paper-account
transition. Its no-clobber finalized transition is still the paper-account
commit point. Its operation receipt remains a separate audit commitment.

Architecture 94 must preserve its existing rules:

- execute the paper runtime at most once for one admitted `PENDING` operation;
- verify the prospective edge and full lineage before publication;
- stage, flush, reread, and reverify before no-clobber finalization;
- never overwrite, repair, delete, or automatically retry ambiguous state;
- after a finalized transition, receipt recovery may perform zero-runtime-call
  recovery only when the exact transition verifies;
- a verified completed or deterministic failed receipt prevents runtime
  re-execution.

## Why a new boundary is required

The accepted repository contains nearly all deterministic paper-cycle mechanics,
but it does not yet contain an operational authority that can truthfully join
those mechanics to accepted C3 state.

Three gaps must be closed.

1. C3 has durable `SUCCESS_SELECTED` state, but there is no reviewed read-only
   public capability that later paper operation can consume as proof that one
   exact published snapshot is the selected production snapshot.
2. Architecture 67 accepts an explicit operation root and explicit prior
   lineage. That is correct for an offline tool, but an operator-selected path
   or internally valid alternate genesis must not define a second operational
   paper account.
3. The accepted C3 daily snapshot contains exactly one completed daily bar per
   requested symbol, while `MovingAverageCrossoverStrategy` requires
   `long_window + 1` historical bars. Missing strategy history therefore cannot
   be fetched, inferred, or silently manufactured during this milestone.

Architecture 94 adds only the authority/composition needed to close those gaps.

## A94-A: read-only selected-C3-snapshot authority

### Construction

A new sealed read-only service is issued only from a genuine
`ValidatedProductionAuthority`. It opens the fixed C2 authority SQLite database
read-only through the already-approved VFS and reuses the existing installed
SQLite/schema/identity validation boundaries.

It must never construct a production `WindowsTransactionalAuthority` with a C3
external adapter. It has no methods for session creation, attempt allocation,
claiming, launch reservation, process creation, resume, terminal recording,
selection, recovery, or provider construction.

### Exact selection assertion

The operator/manual-cycle plan supplies one exact `selection_id` as an
assertion/query key. The ID does not create authority.

The read-only service accepts it only when durable state proves one complete C3
success lineage including, at minimum:

```text
session.state == SUCCESS_SELECTED
attempt.state == SUCCESS_SELECTED
terminal.terminal_state == SUCCEEDED
terminal.provider_call_disposition == CONFIRMED
one session_selections row binds the exact selection/session/terminal
selection snapshot digest == terminal snapshot digest
all relevant stored evidence/digests are canonical and valid
```

The service rejects absent, duplicate, inconsistent, stale-schema, unsupported,
or ambiguous durable state.

It never chooses the newest row by time, filename, directory order, UUID order,
or database row order.

### Published artifact reconciliation

The plan may carry one explicit artifact path as a transport hint only. The
path cannot create selection authority.

The artifact must be an exact safe regular file beneath the fixed C3 capture
output root already validated by C1. The read must be bounded by the existing
daily-snapshot artifact limit and must reject reparse/symlink/device/identity
substitution according to the existing production file-safety policy.

The reread bytes must reconcile with durable selection/terminal evidence:

- SHA-256 equals the selected terminal snapshot digest;
- strict `verify_daily_snapshot(...)` returns complete PASS;
- the parsed snapshot ID equals the C3 terminal evidence snapshot ID;
- the resulting byte length and digest are retained in immutable evidence.

No directory scan or fallback path is permitted in v1.

### Output

Successful reconciliation issues one process-local, non-serializable,
non-copyable selected-snapshot permit plus immutable audit evidence containing
only nonsecret semantic identities/evidence.

Constructing a lookalike dataclass, knowing the selection ID, knowing the
artifact path, or reproducing the snapshot bytes cannot mint this permit.

The permit is accepted only by the Architecture-94 composition root and cannot
be converted into provider, credential, C2 mutation, or C3 capture authority.

## A94-B: authoritative manual paper-account root

### Separate authority

Paper-account mutation receives its own reviewed authority. It is not C3
capture authority and must not expand C3's external-effect permissions.

The initial deployment uses a code-owned Windows root:

```text
F:\AITradingBot\Paper
```

The execution CLI does not accept an arbitrary operational account root. Test
and offline tooling may retain explicit disposable roots behind named test
seams, but production-style manual paper execution is bound to the fixed root.

The root is separately provisioned and validated for the approved Trading SID,
owner/DACL/inheritance policy, safe object types, and reparse/device rejection.
It contains no credentials.

### Account anchor

The fixed root contains one immutable account anchor that binds:

- paper-account schema/policy version;
- one canonical `paper_account_id`;
- machine authority identity and approved Trading SID;
- the exact genesis checkpoint ID, SHA-256, and byte length.

The anchor is provisioned once and is not overwritten by ordinary operation.
A different genesis, path, manifest, or reconstructed checkpoint cannot create a
second account under the same authority.

### Current-tip derivation

The current operational paper-account tip is not selected by filename,
timestamp, modification time, lexical order, or caller-provided manifest.

Under a single account-scoped lifecycle mutex, the service performs a bounded,
strict inventory of the fixed operation layout, then verifies every recognized
finalized transition needed to build the graph rooted at the anchored genesis.
It reuses Architecture-63 edge verification and Architecture-66 full-lineage
verification.

Authority exists only when the durable graph is exactly one linear verified
chain from the anchored genesis to one unique terminal checkpoint. Forks,
cycles, competing successors, unsafe objects, staging remnants, malformed
recognized state, case-fold collisions, enumeration overflow, or unverifiable
transitions block admission.

The derived unique terminal checkpoint is the current tip because verified
durable transition state proves it, not because any artifact calls itself
"current" or "latest".

### Serialization and concurrency

One Windows lifecycle mutex keyed by the authoritative `paper_account_id` is
held across the final pre-effect account revalidation and the complete
Architecture-67 execute/recover call.

A second process cannot concurrently admit another successor from the same
account tip. The mutex does not replace durable verification; after acquisition
the complete anchor/graph/tip state is revalidated before mutation.

## A94-C: pure strategy-history seed

### Reason for the seed

Architecture 56 deliberately captures one target-session daily bar per symbol.
The accepted moving-average strategy needs enough earlier bars to calculate both
previous and current long/short averages. Architecture 94 therefore makes prior
history an explicit, offline-only input instead of pretending C3 supplied it.

### V1 strategy scope

The first reliable manual cycle is deliberately narrow:

- exactly one symbol;
- `MovingAverageCrossoverStrategy` only;
- long-only behavior inherited unchanged;
- one explicit frozen strategy config;
- one selected C3 target-session bar as the current bar;
- an explicit canonical offline history-seed artifact supplying the preceding
  completed sessions.

No AI strategy, model download, optimizer, research winner selection, network
lookup, provider fetch, or automatic strategy choice is part of v1.

### Seed contract

The new pure `strategy-history-seed/v1` artifact is canonical, bounded, and
strictly parsed. It binds its exact symbol, calendar descriptor, ordered daily
bars, source descriptor, UUID5 identity, SHA-256, and byte length.

The seed is explicitly classified as offline seed data, not C3 production
selection authority.

For the moving-average plan:

- all seed bars must be valid completed XNYS daily bars;
- sessions are unique and strictly increasing;
- the retained suffix required by the configured long window must be consecutive
  modeled XNYS sessions;
- the final seed session is the modeled XNYS session immediately preceding the
  selected C3 snapshot target session;
- no seed timestamp/session may equal or follow the selected target session;
- the selected C3 bar is appended as the current and final strategy bar;
- there must then be at least `long_window + 1` total strategy bars.

Missing or mismatched history blocks the plan. Architecture 94 never performs a
provider call to fill the gap.

## A94-D: pure manual strategy plan

A new pure, deterministic `ManualPaperStrategyPlan` is built before any
paper-account mutation.

It binds, at minimum:

- strategy-plan schema/version;
- paper-account ID and exact verified prior terminal checkpoint evidence;
- selected C3 selection/session/terminal/snapshot evidence;
- selected snapshot artifact SHA-256 and byte length;
- strategy-history-seed artifact ID/SHA-256/byte length;
- exact moving-average strategy config;
- deterministic strategy context/run identity;
- exact strategy proposal or explicit `NO_SIGNAL` result;
- the derived explicit target portfolio;
- exact existing checkpointed-cycle request;
- caller idempotency key;
- all explicit next-session open-reference assertions and existing paper-cycle
  policies.

The plan contains no provider, credential, broker, scheduler, filesystem-mutation,
or wall-clock authority.

Its identity is UUID5 over complete canonical semantic material. Paths and
serialized plan bytes do not participate in the semantic ID; the artifact
SHA-256/length are retained separately as transport evidence.

### Strategy context

The strategy context is reconstructed solely from:

- the verified seed bars;
- the selected C3 target-session bar;
- the verified current paper-account state derived from the authoritative tip;
- deterministic plan-owned IDs/ordinals.

No ambient portfolio alias, current time, GUI selection, cache, or mutable
research result is consulted.

### Proposal-to-target bridge

The existing checkpointed paper runtime is target-based, while the accepted
baseline strategy returns `TradeProposal | None`. Architecture 94 does not add a
second execution pipeline.

For v1 only, a pure bridge converts the exact one-symbol strategy result into an
`ExplicitQuantityTargetPortfolio`:

- `NO_SIGNAL`: exact current quantity and current marked cash target;
- accepted BUY signal: target quantity equals the strategy proposal desired
  quantity;
- accepted SELL signal: target quantity is zero;
- every other shape is unsupported and blocks planning.

Target cash is derived from the verified account's marked equity and the
selected C3 close so that the requested quantity target and cash target exactly
reconcile with the existing planner's target model. A target that is negative,
nonrepresentable, violates the current long-only account shape, or cannot be
expressed exactly is blocked; it is never silently rounded, capped, or changed.

The existing planner/proposal adapter then produces the proposal batch that is
actually submitted to deterministic risk. For this narrow one-symbol bridge,
its nonempty proposal must reconcile exactly with the strategy signal's symbol,
side, and desired quantity before risk is allowed to run. A no-signal plan must
produce no planner proposal. Any mismatch fails closed.

This bridge is not a general strategy-to-target policy and must not be reused for
multi-symbol or AI strategies without a later architecture review.

### Risk remains mandatory

Even after exact strategy/planner reconciliation, the existing deterministic
risk orchestrator decides whether the proposal is approved, resized, or
rejected. The strategy-plan bridge cannot approve an order and cannot bypass a
risk rejection or resize.

## A94-E: plan binding to the existing durable paper operation

Architecture 94 preserves the existing checkpointed-cycle request and
Architecture-67 receipt/transition schemas where possible.

The derived checkpointed-cycle request carries reserved Architecture-94 metadata
that binds the strategy plan's semantic ID and artifact SHA-256/length. The
strategy-plan verifier must be able to reconstruct the exact request and prove
that those metadata values match the plan artifact.

The existing paper-operation intent therefore remains bound to the exact cycle
configuration that was deterministically produced from the strategy plan. A
future verifier can prove the chain:

```text
strategy seed + selected C3 evidence + prior account
-> verified strategy plan
-> exact checkpointed-cycle configuration
-> Architecture-67 operation intent/receipt
-> exact report + successor checkpoint
```

If existing metadata constraints cannot carry this binding without changing
canonical semantics, implementation must stop and return to architecture review
rather than silently weakening auditability.

## A94-F: manual invocation state machine

The production-style command is explicitly manual and has two phases.

### Read-only preflight / inspect

Preflight performs no account mutation and no provider/broker effect. It:

1. validates C1 production authority for read-only selected-snapshot access;
2. validates the fixed manual-paper authority/root/anchor;
3. validates the exact durable C3 selection assertion;
4. safely rereads and offline-verifies the selected snapshot artifact;
5. derives and verifies the unique authoritative paper-account tip;
6. reads/verifies the explicit offline strategy-history seed;
7. deterministically reconstructs and verifies the strategy plan;
8. constructs the exact existing verified paper-operation inputs;
9. inspects the exact operation identity through the existing read-only
   Architecture-67 inspection boundary.

The result is one bounded classification such as `PENDING`, `ALREADY_APPLIED`,
`CONFLICTING`, or `BLOCKED`. Preflight cannot authorize an Alpaca or brokerage
call.

### Execute once

`--execute-once` is the only v1 paper-account mutation command. It requires an
explicit operator invocation; there is no scheduler, loop, watch mode, polling,
automatic retry, or GUI execute control.

Before mutation it acquires the account-scoped mutex and revalidates the C3
selection, selected artifact, anchor, complete account graph/current tip,
strategy plan, exact operation intent, and `PENDING`/recoverable durable state.

It then delegates exactly once to the existing Architecture-67 execute/recover
boundary. The new wrapper does not implement its own transition publication or
receipt recovery algorithm.

If durable state changed between preflight and execution admission, the command
blocks. It never automatically replans against a newer account tip or alternate
snapshot.

## Crash and recovery rules

Architecture 94 adds no optimistic retry semantics.

- Crash before Architecture-67 mutation admission: no paper transition was
  committed; rerun starts with full read-only revalidation.
- Crash while Architecture 67 has staging/ambiguous state: existing fail-closed
  inspection remains authoritative; no automatic cleanup or runtime rerun.
- Finalized verified transition without receipt: the existing zero-runtime-call
  receipt recovery path may run after full authoritative revalidation.
- Verified completed receipt: return `ALREADY_APPLIED`; never rerun the runtime.
- Verified deterministic failed receipt: do not rerun the same operation.
- Changed account tip, changed C3 selection evidence, changed strategy plan, or
  changed dependency bytes: the old operation is not silently rewritten or
  rebound; a new explicitly planned operation is required.

## Operator-visible evidence

A completed manual cycle must make the following audit chain recoverable without
network access:

- paper-account ID and anchored genesis evidence;
- prior full-lineage evidence and prior terminal checkpoint ID;
- exact C3 selection/session/terminal/snapshot IDs;
- selected snapshot SHA-256/byte length;
- strategy-history seed ID/SHA-256/byte length and explicit offline-seed label;
- strategy config and deterministic strategy-plan ID;
- strategy proposal or `NO_SIGNAL`;
- derived target and planner proposal reconciliation;
- complete deterministic risk decisions;
- existing order/submission/fill/application audit results;
- cycle result and successor checkpoint IDs;
- prospective/final edge and full-lineage verification evidence;
- Architecture-67 operation/transition/receipt IDs and terminal classification.

Secrets, credential values, raw native errors, provider response bodies, and
unbounded filesystem diagnostics remain excluded.

## Explicitly deferred

Architecture 94 does not authorize or design:

- provider call #7 or any C3 recapture;
- rotating or restaging `/v2` Alpaca credentials;
- broker account reads or mutations;
- external order submit/cancel/replace;
- live credentials or live-mode authority;
- unattended scheduling or automatic retry;
- GUI execute/retry/recover controls;
- automatic selection of a strategy or research winner;
- online strategy-history acquisition;
- multi-symbol strategy composition;
- AI-generated autonomous targets;
- distributed/multi-host paper-account mutation;
- cleanup/repair of ambiguous Architecture-67 staging state.

## Required implementation checkpoints

Implementation proceeds only after this architecture and its validation plan
are reviewed and accepted.

1. **A94-A — pure strategy-history and strategy-plan contracts.** Canonical
   seed, pure verifier, deterministic moving-average context, exact
   proposal-to-target bridge, and plan-to-existing-request reconciliation.
2. **A94-B — read-only selected-C3-snapshot authority.** C1-bound read-only
   SQLite selection validation plus safe artifact reread/offline verification;
   no C3 effect adapter.
3. **A94-C — manual paper-account authority.** Fixed root, immutable anchor,
   bounded graph-derived unique tip, account mutex, and read-only preflight.
4. **A94-D — authority/composition join.** Revalidate all three inputs under
   account admission and construct the exact existing verified paper-operation
   inputs without changing Architecture-67 commit semantics.
5. **A94-E — manual CLI.** `--inspect-only` and explicit `--execute-once` only;
   no scheduling/retry/provider/broker controls.
6. **A94-F — acceptance/certification.** Focused pure, authority, crash/recovery,
   and cross-boundary tests; one supervised local simulated-paper acceptance;
   then one final unchanged-tree full repository certification.

Any implementation discovery that requires C3 capture mutation, C2 selection
mutation, an arbitrary operational paper root, a second paper transition commit
algorithm, a risk bypass, automatic strategy-history acquisition, or optimistic
recovery invalidates this freeze and requires Sol High architecture review
before code changes continue.
