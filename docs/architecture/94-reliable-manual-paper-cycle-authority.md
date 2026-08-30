# Reliable manual paper-cycle authority and composition

## Status and purpose

Architecture 94 freezes the first reliable manually invoked paper cycle after
accepted C3 market-data capture and GUI-A7 integration.

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
external order submit/cancel/replace, live trading, unattended scheduling,
automatic retry, or any new market-data provider effect.

**Production/live trading remains NO-GO.**

## Non-negotiable authority rules

Architecture 94 inherits the C1/C2/C3 rules:

- durable state outranks process-local assumptions;
- ambiguous effects fail closed;
- child success cannot create authority;
- paths, filenames, PIDs, environment values, digests, UUIDs, reconstructed
  objects, or caller assertions cannot create alternate authority;
- every order that can reach execution passes deterministic risk;
- strategy, GUI, AI, schedulers, providers, and future brokerage adapters cannot
  bypass deterministic risk or reviewed authority;
- reading an already-selected C3 artifact cannot mint C3 capture authority;
- Architecture 94 never constructs `WindowsEffectfulDailySnapshotCapture`,
  accesses Windows Credential Manager, or calls Alpaca.

All six accepted real-provider C3 effects remain consumed. There is no provider
call #7. Call #5 remains `FAILED / CONFIRMED`; call #6 remains
`SUCCEEDED / CONFIRMED` and `SUCCESS_SELECTED`. Neither lineage is retried.
`/v2` Alpaca credential references remain immutable historical state.

## Existing boundaries reused unchanged

Architecture 94 should reuse, not reimplement, the following accepted
boundaries.

### Daily snapshot

Architecture 56 remains the canonical daily-snapshot parser, verifier, and replay
boundary. Selected C3 bytes are usable only after strict offline verification
and reconciliation with durable C3 selection evidence.

### Strategy

`MovingAverageCrossoverStrategy` remains the initial deterministic strategy. Its
crossover calculation, long-only position filtering, quantity selection, and
proposal identity are unchanged. The strategy remains a pure proposal producer
and receives no execution authority.

### Planner, proposals, and risk

The existing rebalance planner/proposal adapter and Architecture-18 portfolio
risk orchestrator remain unchanged. `RiskManager` remains the sole owner of risk
rules, reason codes, and approve/resize/reject decisions.

A strategy proposal, target, plan, GUI state, C3 selection, or paper-operation
intent is never order authorization.

### Local simulated execution

Architecture 19 and the accepted paper submission/fill/application boundaries
remain unchanged. `PaperPortfolioRuntime` remains the accepted target-based
simulated paper execution composition.

### Checkpoint and lineage

Architectures 62, 63, and 66 remain unchanged. Existing checkpointed-cycle,
successor-checkpoint, prospective edge, and full-lineage verification remain the
source of truth for paper-account transition validity.

### Durable paper operation

Architecture 67 remains the only paper transition commit/recovery algorithm.
Its no-clobber finalized transition remains the paper-account commit point; its
receipt remains a separate audit commitment.

The following Architecture-67 rules are preserved exactly:

- one admitted `PENDING` operation calls the paper runtime at most once;
- prospective edge and full lineage are verified before publication;
- staged bytes are flushed, reread, and reverified before no-clobber finalize;
- ambiguous/staging state is never automatically deleted, repaired, or retried;
- finalized verified transition without receipt may use only the existing
  zero-runtime-call receipt-recovery path;
- verified completed or deterministic failed receipt prevents runtime
  re-execution.

## The three missing boundaries

The repository already contains almost all deterministic paper mechanics. The
missing work is narrower than a new paper engine.

1. **Selected C3 read authority.** C3 has durable `SUCCESS_SELECTED` state but
   no reviewed later-stage read capability proving that one exact published
   artifact is the selected production snapshot.
2. **Operational paper-account authority.** Architecture 67 correctly accepts
   explicit roots/manifests for offline use, but an arbitrary caller path or an
   alternate internally valid genesis must not define another operational
   account.
3. **Strategy history.** A C3 daily snapshot contains one completed daily bar per
   symbol, while `MovingAverageCrossoverStrategy` needs `long_window + 1` bars.
   Missing history cannot be fetched, inferred, or manufactured during this
   milestone.

Architecture 94 closes only these gaps and composes them with existing paper
execution.

## Selected C3 snapshot read authority

### Construction

A sealed read-only selected-snapshot service is issued only from a genuine
`ValidatedProductionAuthority`.

It opens the fixed production authority SQLite database read-only through the
already-approved VFS and reuses existing installed SQLite/schema/identity
validation. Queries for one selection run inside one read transaction so the
joined evidence is a consistent database snapshot.

It does not construct a production `WindowsTransactionalAuthority` with a C3
external adapter and exposes no methods for session creation, attempt
allocation, claim, reservation, process creation, resume, terminal mutation,
selection mutation, recovery, credential access, or provider construction.

### Exact selection assertion

The manual-cycle plan supplies one exact `selection_id` only as an assertion and
query key. The ID does not create authority.

The read service accepts it only when durable state proves one complete success
lineage including, at minimum:

```text
session.state == SUCCESS_SELECTED
attempt.state == SUCCESS_SELECTED
terminal.terminal_state == SUCCEEDED
terminal.provider_call_disposition == CONFIRMED
exactly one session_selections row binds selection/session/terminal
selection snapshot digest == terminal snapshot digest
stored semantic evidence/digests are canonical and mutually consistent
```

Absent, duplicate, inconsistent, unsupported, malformed, or ambiguous durable
state blocks. The service never chooses a row by newest timestamp, filename,
directory order, UUID order, or SQLite row order.

### Artifact commitment and identity evidence

`session_selections` has no independent artifact byte-length claim. Its artifact
commitment is the exact selection row, its exact terminal binding, and its copied
`snapshot_digest`. P2 therefore does not compare the selection or terminal with
a separately stored selection/terminal byte length. The terminal's durable C3
evidence likewise does not require a separate artifact byte-length column.

For a successful C3 terminal, the canonical terminal evidence retains the
snapshot ID, `artifact_sha256`, and `artifact_identity_sha256`. C3 v1 fixes the
published final filename to
`daily-market-data-snapshot-<snapshot-id>.json` below the fixed C1
capture-output root. The existing `C3ArtifactIdentityEvidence` commits the
snapshot ID, final canonical filename, artifact SHA-256, artifact byte length,
and native file identity. Its canonical evidence object is not stored in
SQLite; the durable terminal `artifact_identity_sha256` commits all of those
fields, including the byte length.

P2 safely opens the exact candidate final object beneath the fixed root,
performs a bounded reread, obtains its native file identity, computes its exact
SHA-256 and byte length, and reconstructs the existing C3 artifact-identity
evidence. The reconstructed identity digest must exactly equal the durable
terminal `artifact_identity_sha256`; P2 compares the digest and never attempts
to invert it. The reread SHA-256 must also equal the terminal and selection
`snapshot_digest`, and strict daily-snapshot verification must pass with a
matching snapshot ID. The reread length and current file identity are inputs to
that verification, not an alternate source of authority.

No C3 schema or evidence migration is required, and no accepted C1/C2/C3
behavior changes. The Architecture-94 artifact path remains transport only:
it cannot create authority, select another artifact, or supply a fallback.

### Published artifact reconciliation

The plan may contain one explicit artifact path as a transport hint. The path
cannot create authority.

The file must be an exact safe regular file beneath the fixed C3 capture-output
root already validated by C1. The read is bounded by the existing daily-snapshot
artifact limit and follows existing production protections against
reparse/symlink/device/identity substitution.

The reread bytes must satisfy all of:

- SHA-256 equals the durable selected terminal snapshot digest;
- strict `verify_daily_snapshot(...)` returns complete PASS;
- parsed snapshot ID equals the terminal evidence snapshot ID;
- the reread byte length and native file identity reconstruct the existing
  canonical C3 artifact-identity evidence and its digest matches terminal
  evidence.

There is no directory scan or fallback path in v1.

### Output

Success issues a process-local, non-serializable, non-copyable selected-snapshot
permit plus immutable nonsecret audit evidence.

Knowing the selection ID/path/digest or reproducing the snapshot bytes cannot
mint the permit. The permit is accepted only by the Architecture-94 composition
root and cannot be converted into provider, credential, C2 mutation, or C3
capture authority.

## Authoritative manual paper account

### Separate authority and fixed root

Paper-account mutation receives a separate reviewed authority. It is not C3
capture authority and cannot expand C3 external-effect permissions.

The production-style manual paper deployment uses the code-owned root:

```text
F:\AITradingBot\Paper
```

The execution CLI cannot choose a different operational account root. Tests may
use explicitly named disposable seams only.

The root is separately provisioned and validated for the approved Trading SID,
owner/DACL/inheritance policy, safe object types, and reparse/device rejection.
It contains no credentials.

### Immutable account anchor

The root contains one immutable account anchor binding:

- paper-account schema/policy version;
- canonical `paper_account_id`;
- approved machine authority identity and Trading SID;
- exact genesis checkpoint ID, SHA-256, and byte length.

The anchor is provisioned once and not overwritten by ordinary operation. A
caller path, alternate manifest, or reconstructed/different genesis cannot
create a second account under this authority.

### Current tip comes from verified graph state

The current operational tip is not selected by filename, timestamp, mtime,
lexical order, or caller-provided manifest.

Under an account-scoped lifecycle mutex, the authority performs a bounded strict
inventory of the fixed operation layout and verifies recognized finalized
transitions using Architecture-63 edge verification and Architecture-66 full
lineage verification.

Authority exists only when durable state forms exactly one linear verified chain
from the anchored genesis to one unique terminal checkpoint.

Forks, cycles, competing successors, disconnected/alternate genesis, unsafe
objects, staging remnants, malformed recognized state, case-fold collisions,
enumeration overflow, or unverifiable transitions block admission.

The unique verified terminal is current because durable graph state proves it,
not because an artifact calls itself `latest` or `current`.

### Serialization and concurrency

One Windows lifecycle mutex keyed by authoritative `paper_account_id` is held
across the final pre-mutation account revalidation and the complete
Architecture-67 execute/recover call.

The mutex does not replace durable evidence. After acquisition the complete
anchor/graph/tip is revalidated. A second process cannot concurrently admit a
competing successor from the same tip.

## Pure strategy-history seed

### Why it exists

Architecture 56 supplies one selected target-session bar per symbol. The
moving-average strategy needs prior bars for previous/current averages.
Architecture 94 therefore records the prior history as an explicit offline-only
input rather than pretending C3 supplied it.

### V1 scope

The first reliable manual cycle is deliberately narrow:

- exactly one symbol;
- `MovingAverageCrossoverStrategy` only;
- one frozen strategy config;
- one selected C3 target-session bar as the current bar;
- one canonical offline history-seed artifact for preceding sessions;
- long-only behavior unchanged.

No AI strategy, model download, optimizer, research-winner selection, network
lookup, provider fetch, or automatic strategy choice is in v1.

### Seed contract

A new `strategy-history-seed/v1` artifact is canonical and bounded. It binds the
symbol, XNYS calendar descriptor, ordered daily bars, explicit offline source
descriptor, UUID5 semantic identity, and separate SHA-256/byte-length evidence.

The artifact is explicitly classified as **offline seed data**, not C3 selection
authority.

For a moving-average plan:

- seed bars are valid completed XNYS daily bars;
- sessions are unique and strictly increasing;
- the suffix required by the configured long window is consecutive modeled XNYS
  sessions;
- final seed session is the modeled XNYS session immediately preceding the
  selected C3 target session;
- no seed session/timestamp equals or follows the selected target session;
- the selected C3 bar is appended as the current/final strategy bar;
- the resulting context contains at least `long_window + 1` bars.

Missing or mismatched history blocks. Architecture 94 never calls a provider to
fill it.

## Pure manual strategy plan

A deterministic `ManualPaperStrategyPlan` is built before paper-account
mutation. It binds, at minimum:

- plan schema/version;
- paper-account ID and exact verified prior terminal checkpoint evidence;
- selected C3 selection/session/terminal/snapshot evidence;
- selected artifact SHA-256/byte length;
- strategy-history seed ID/SHA-256/byte length;
- exact moving-average strategy config;
- deterministic strategy context/run identity;
- exact strategy proposal or explicit `NO_SIGNAL`;
- derived explicit target portfolio;
- complete semantic existing checkpointed-cycle request core;
- caller idempotency key;
- explicit next-session open-reference assertions and existing paper policies.

The plan has no provider, credential, broker, scheduler, filesystem-mutation, or
wall-clock authority. Its UUID5 semantic identity binds complete canonical
semantic material; paths, serialized plan bytes, artifact SHA-256, and artifact
byte length do not define semantic identity. The plan's strategy-history,
selected-snapshot, account, strategy, proposal/target, policy, operation, and
request-core evidence remains pure and deterministic.

### Strategy context

The strategy context is reconstructed only from:

- verified offline seed bars;
- selected C3 target-session bar;
- verified paper-account state from the authoritative tip;
- deterministic plan-owned IDs/ordinals.

No ambient portfolio alias, current time, GUI selection, cache, or mutable
research result is consulted.

### Proposal-to-target bridge

The existing checkpointed paper runtime is target-based while the accepted
baseline strategy returns `TradeProposal | None`. Architecture 94 does not add a
second execution pipeline.

For this one-symbol v1 only, a pure bridge maps the exact strategy result into an
`ExplicitQuantityTargetPortfolio`:

- `NO_SIGNAL`: retain exact current quantity and current marked cash;
- BUY signal: target quantity equals strategy `desired_quantity`;
- SELL signal: target quantity is zero;
- every other shape is unsupported and blocks.

Target cash is derived from verified marked equity and selected C3 close so the
quantity and cash targets reconcile exactly with the existing target/planner
model. A negative, nonrepresentable, long-only-invalid, or otherwise
unexpressible target blocks; nothing is silently rounded, capped, or altered.

The existing planner/proposal adapter then produces the proposal that is
actually passed to deterministic risk. For this narrow bridge, a nonempty
planner proposal must exactly reconcile with the strategy signal's symbol,
side, and desired quantity. `NO_SIGNAL` must produce no planner proposal. Any
mismatch fails closed.

This is not a general multi-symbol or AI strategy-to-target policy.

### Risk remains mandatory

After strategy/planner reconciliation, existing deterministic risk alone decides
approve/resize/reject. The bridge cannot approve orders, overwrite a resize, or
bypass a rejection.

## Binding strategy evidence to the existing operation

Architecture 94 preserves existing checkpointed-cycle and Architecture-67
transition/receipt schemas unchanged.

The canonical `ManualPaperStrategyPlan` artifact binds the complete semantic
checkpointed-cycle request core: every request field that does not depend on the
plan artifact's own serialized SHA-256 or byte length, including the existing
request ID, snapshot reference, target, ordered open references, policies,
cycle timestamps, and caller/base metadata in its supplied order. The plan
artifact MUST NOT serialize its own artifact SHA-256 or byte length, directly or
indirectly. In particular, it MUST NOT serialize a final
`CheckpointedVerifiedSnapshotPaperCycleRequest` that contains those
self-referential values.

Plan semantic identity remains UUID5 over complete canonical semantic material.
Serialized bytes, path, artifact SHA-256, and artifact byte length do not define
the semantic UUID. After canonical plan serialization, the exact plan artifact
SHA-256 and byte length are computed. Only then is the final existing
`CheckpointedVerifiedSnapshotPaperCycleRequest` deterministically derived from
the request core.

### P1/P2 artifact-evidence boundary

P1's selected artifact SHA-256 and byte length are pure, non-authorizing
assertions bound into the `ManualPaperStrategyPlan`. The plan does not bind
`artifact_identity_sha256`, `C3ArtifactIdentityEvidence`, native file identity,
filesystem facts, or any P2 permit or authority object. P2 independently proves
the authoritative selected C3 artifact from durable selection/terminal state,
safe reread, and the terminal `artifact_identity_sha256` commitment. P4 later
exact-compares the P1 selected-C3 assertion with P2's independently proven
selected-C3 audit evidence. P2 artifact-identity evidence is not part of P1
strategy economics or P1 authority. This clarification does not change accepted
P1 source or identity semantics.

The derived final request injects exactly these Architecture-94-owned metadata
entries, after the caller/base metadata and in this frozen order:

1. `architecture94.strategy_plan_id` — canonical plan semantic UUID text;
2. `architecture94.strategy_plan_sha256` — lowercase 64-character SHA-256 of
   the exact canonical plan artifact bytes;
3. `architecture94.strategy_plan_byte_length` — canonical base-10 positive byte
   length text.

Architecture 94 owns the `architecture94.` metadata namespace for this boundary.
Caller/base request metadata using that prefix is rejected before derivation; it
is never overwritten or reordered. The existing `checkpoint.`, `lineage.`, and
`application.` reserved prefixes remain unchanged. The existing checkpointed
caller metadata carrier is sufficient because its metadata is ordered and
semantic, and Architecture 94 owns its additional namespace before constructing
the existing request.

The complete request core, its caller metadata order, and this deterministic
three-entry injection rule are part of plan semantics. The artifact digest and
length are detached artifact evidence, so they do not create a hash cycle.

Pure verification/replay must parse and validate the canonical plan artifact,
recompute its semantic plan ID, recompute the exact artifact SHA-256 and byte
length, reconstruct the final checkpointed-cycle request using the frozen
metadata injection, and prove that the reconstructed request is exactly the
request handed to later Architecture-94 composition.

No placeholder digest, fixed-point/self-hash search, digest-exclusion trick over
partially serialized bytes, alternate semantic hash, or second mutable artifact
is permitted.

This creates an offline-provable chain:

```text
strategy seed + selected C3 evidence + authoritative prior account
-> verified strategy plan
-> exact checkpointed-cycle configuration
-> Architecture-67 operation intent/receipt
-> exact report + successor checkpoint
```

If existing metadata constraints cannot carry this binding without changing
canonical semantics, implementation stops for Sol High architecture review. It
must not silently weaken auditability.

## Manual invocation state machine

### Read-only preflight

Preflight performs no paper-account mutation and no provider/broker effect. It:

1. validates C1 production authority for read-only selected-snapshot access;
2. validates fixed manual-paper authority/root/anchor;
3. validates exact durable C3 selection assertion;
4. safely rereads and offline-verifies selected snapshot bytes;
5. derives/verifies the unique authoritative paper-account tip;
6. reads/verifies the explicit offline strategy-history seed;
7. reconstructs/verifies the deterministic strategy plan;
8. constructs exact existing verified paper-operation inputs;
9. inspects the operation identity using existing Architecture-67 read-only
   inspection.

The result is a bounded classification such as `PENDING`, `ALREADY_APPLIED`,
`CONFLICTING`, or `BLOCKED`.

### Execute once

`--execute-once` is the only v1 paper-account mutation command. It requires one
explicit operator invocation. There is no scheduler, loop, watch mode, polling,
automatic retry, or GUI execute control.

Before mutation it acquires the account mutex and revalidates the C3 selection,
selected artifact, anchor, complete account graph/current tip, strategy plan,
exact operation intent, and `PENDING`/recoverable durable state.

It then delegates exactly once to the existing Architecture-67 execute/recover
boundary. The wrapper does not implement a second transition publication or
receipt recovery algorithm.

Changed durable state between preflight and locked admission blocks. It never
automatically replans against another account tip or snapshot.

## Crash and recovery

Architecture 94 adds no optimistic retry semantics.

- Crash before Architecture-67 mutation admission: no paper transition committed;
  rerun begins with complete read-only revalidation.
- Architecture-67 staging/ambiguous state: existing fail-closed inspection is
  authoritative; no automatic cleanup/runtime rerun.
- Finalized verified transition without receipt: only existing zero-runtime-call
  receipt recovery may proceed after authoritative revalidation.
- Verified completed receipt: return `ALREADY_APPLIED`; no runtime rerun.
- Verified deterministic failed receipt: do not rerun the same operation.
- Changed account tip, selected C3 evidence, plan, or dependency bytes: the old
  operation is not silently rebound; a new explicit plan is required.

## Required durable audit chain

A completed manual cycle must be explainable offline through:

- paper-account ID and anchored genesis evidence;
- prior full-lineage evidence and terminal checkpoint ID;
- C3 selection/session/terminal/snapshot IDs;
- selected snapshot digest plus independently reread artifact SHA-256,
  byte-length, and identity evidence (not a separate selection/terminal
  byte-length claim);
- strategy-history seed ID/SHA-256/byte length and `OFFLINE_SEED` classification;
- strategy config and deterministic plan ID;
- strategy proposal or `NO_SIGNAL`;
- derived target and planner-proposal reconciliation;
- deterministic risk decisions;
- existing order/submission/fill/application audit results;
- cycle result and successor checkpoint IDs;
- prospective/final edge and full-lineage verification evidence;
- Architecture-67 operation/transition/receipt IDs and classification.

Secrets, credential values, raw native errors, provider response bodies, and
unbounded filesystem diagnostics remain excluded.

## Explicitly deferred

Architecture 94 does not authorize or design:

- provider call #7 or any C3 recapture;
- `/v2` credential mutation/restaging;
- broker account reads/mutations;
- external order submit/cancel/replace;
- live credentials/live-mode authority;
- unattended scheduling/automatic retry;
- GUI execute/retry/recover controls;
- automatic strategy/research-winner selection;
- online strategy-history acquisition;
- multi-symbol strategy composition;
- AI-generated autonomous targets;
- distributed/multi-host paper mutation;
- cleanup/repair of ambiguous Architecture-67 staging state.

## Implementation stages

Implementation begins only after Architecture 94 and its validation plan pass
post-write review.

### P1 — Pure strategy history and strategy plan

Implement only canonical history-seed models/serializer/verifier, deterministic
moving-average context, proposal-to-target bridge, and exact plan-to-existing
request reconciliation. No authority or mutation code.

### P2 — Read-only selected-C3 snapshot authority

Implement C1-bound read-only SQLite selection validation plus safe artifact
reread/offline verification. No C3 effect adapter or provider path.

### P3 — Manual paper-account authority

Implement fixed root, immutable anchor, graph-derived unique tip, account mutex,
and read-only account preflight.

### P4 — Authority/composition join

Revalidate selected snapshot, account tip, and strategy plan under admission and
construct exact existing verified paper-operation inputs without changing
Architecture-67 commit semantics.

### P5 — Manual CLI

Expose only explicit `--inspect-only` and `--execute-once`; no scheduling,
provider, broker, retry, or arbitrary production-root controls.

### P6 — Acceptance and certification

Run focused pure/authority/crash/cross-boundary gates, one supervised local
simulated-paper acceptance, then one final unchanged-tree full-repository
certification.

Any implementation discovery requiring C3 capture mutation, C2 selection
mutation, arbitrary operational paper roots, a second transition commit
algorithm, risk bypass, automatic strategy-history acquisition, or optimistic
recovery invalidates this freeze and requires Sol High architecture review.
