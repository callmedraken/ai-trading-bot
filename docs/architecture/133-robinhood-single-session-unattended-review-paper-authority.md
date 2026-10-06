# Architecture 133 — Single-Session Robinhood Unattended Review-Paper Authority

Status: **frozen design checkpoint**. This document authorizes source/design work
only. It does not authorize scheduler mutation, unattended provider access,
Robinhood review requests, synthetic paper mutation, broker placement, or live
trading.

## Decision

The next current-supported product step after Architecture 131 is one bounded
**single-session unattended simulated-paper wake** using the already-accepted
Robinhood review/read boundary.

Architecture 133 does not revive the historical D10 unattended deployment. D10
remains historical infrastructure with its scheduler disabled. Architecture 133
is a new current-product authority built from the accepted Architecture 131
review-paper primitives and the Architecture 132 certification model.

The first unattended scope is deliberately smaller than a multi-day soak:

- exactly one pre-authorized NYSE session;
- exactly one pre-authorized `TradeProposal`;
- at most one fresh quote acquisition;
- at most one risk decision;
- at most one Robinhood `review_equity_order` request;
- at most one synthetic local paper fill;
- zero automatic retry;
- zero historical catch-up;
- zero real-order placement/cancel/options/crypto authority.

A successful single-session qualification is evidence for a later separately
designed multi-session soak. It does not automatically authorize recurrence.

## Controlling Architecture 131 contracts

Architecture 133 composes, rather than replaces, the accepted current-supported
Robinhood review-paper line:

```text
131-S published NYSE regular-session authority
131-P bounded quote acquisition
131-N canonical risk-price snapshot
131-O durable forward-paper risk preview
131-Q PREPARE / EXECUTE invariants
131-K durable virtual-paper risk context
131-J deterministic paper pipeline
131-I review-paper intent bridge
131-H review-only Robinhood paper operator
131-A2 durable review-paper store / deterministic synthetic fill
131-LQ / 131-V independent evidence lessons
```

Architecture 133 must not call the interactive 131-V human challenge wrapper.
131-V remains the supervised human-started qualification surface.

The unattended authority must preserve the safety properties that 131-V proved
while substituting a separate bounded source-owned activation/wake authority for
the per-execution human challenge. It may reuse accepted 131-Q primitives only
through an explicitly reviewed Architecture-133 composition that proves the new
authority before any provider/effect boundary.

## Activation authority

The first Architecture-133 activation is immutable and binds exactly:

- schema/version;
- one deterministic activation ID;
- exact certified source/deployment identity;
- exact target NYSE session date;
- exact `TradeProposal`, including proposal ID, symbol, side, desired quantity,
  reason/confidence, and proposal creation time;
- exact `RiskLimits`;
- exact `new_trading_enabled` value;
- exact review-paper store identity/path and starting cash;
- exact opening/closing buffers;
- exact quote max age;
- exact slippage basis points and commission;
- exact local order UUID;
- exact zero-semantic-argument wake contract identity;
- activation creation time and terminal expiry rule.

The activation is single-use. It is not renewable in place and must not contain
a reusable provider credential, raw OAuth material, native handle, or broker
mutation capability.

The target session is explicit. The first unattended milestone does **not**
derive a missed historical session and does not search backward or forward for a
session to trade.

## Wake identity and durable state machine

One deterministic wake identity is derived from the activation ID, target
session date, proposal ID, and local order ID.

Before provider access the wake must durably classify the activation/wake state.
The exact state model must distinguish at least:

```text
READY
PREPARE_STARTED
PREPARED
REVIEW_STARTED
COMPLETED
STOPPED
INDETERMINATE
```

Names may be refined during source design, but these semantic distinctions are
frozen:

- no provider call occurs before durable wake admission;
- a previously COMPLETED wake is read-only/idempotent;
- a previously STOPPED wake is not retried automatically;
- a wake that may have crossed the review boundary is INDETERMINATE until an
  independent reconciliation proves the durable outcome;
- neither process restart nor scheduler replay manufactures fresh retry
  authority;
- the same activation can never produce two local order IDs or two paper fills.

A durable state write is local paper-control metadata only. It is not a
Robinhood order and carries no broker placement authority.

## One unattended wake

A valid wake performs at most this ordered sequence:

1. prove exact runtime/source identity and exact single-session activation;
2. read one current UTC instant and resolve the activation's exact target
   session through accepted 131-S;
3. require the wake is inside the exact admissible regular-session window;
4. prove the deterministic wake has no consumed/ambiguous prior effect;
5. reconstruct the exact durable review-paper account and proposal state;
6. acquire one accepted 131-P quote snapshot;
7. construct and independently validate the same risk-preview material required
   by the accepted supervised path;
8. require quote freshness and admitted session immediately before review;
9. durably mark the review boundary as started before invoking it;
10. invoke the accepted review-only 131-H/131-L composition at most once;
11. persist/reconcile the deterministic synthetic paper result;
12. independently reopen durable evidence and verify the exact completed state;
13. emit bounded sanitized wake evidence and close.

The source implementation may split these responsibilities into smaller
checkpoints. The ordering, one-attempt budget, and effect fences above are
contractual.

## Proposal authority

Architecture 133 v1 does **not** add autonomous proposal generation.

The exact proposal is frozen into the activation before unattended execution.
AI/research/strategy generation of future unattended proposals is a separate
future product authority. This keeps the first unattended qualification focused
on scheduling/effect safety rather than simultaneously introducing autonomous
strategy authority.

## Provider/effect budget

Per activation/wake:

```text
get_equity_quotes         <= 1 accepted PREPARE acquisition
review_equity_order       <= 1
get_accounts              only through the already-accepted 131-H operator
get_equity_orders         only through the already-accepted 131-H safety observer
place_equity_order         0
cancel_equity_order        0
place/cancel option        0
exercise option            0
place/cancel crypto        0
interactive OAuth reauth   0
retry                      0
historical catch-up        0
```

If persisted OAuth cannot be reused without interactive authorization, the wake
stops before review. Unattended mode must never open a browser or wait for a
human OAuth flow.

## Ambiguity and crash policy

A crash or exception before any provider effect may yield STOPPED only when
durable evidence proves the effect boundary was not crossed.

Once the review boundary is marked started, any exception, process death,
transport ambiguity, or missing terminal evidence is fail-closed
INDETERMINATE. The same activation may not retry the review request.

Independent reconciliation may prove that the deterministic local paper result
was completed. Reconciliation may not manufacture a second provider call or
synthetic fill.

## Session, stale, and missed-wake policy

The activation targets exactly one published NYSE session.

- before the admissible window: no effect;
- inside the admissible window: one bounded wake may proceed;
- after the quote/session deadline: STOPPED with no retry;
- wake first observed after the session's admissible window: MISSED_SESSION /
  equivalent terminal no-effect classification;
- different session date: fail closed;
- no previous-session or next-session catch-up;
- no automatic activation extension.

A missed first qualification requires a newly reviewed activation, not reuse of
the expired one.

## Scheduler boundary

Architecture 133 source work may define a zero-semantic-argument scheduler
contract, but may not mutate Task Scheduler.

The first protected deployment must create or update a distinct
Architecture-133 task. It must not repurpose or re-enable historical D10 tasks.

Scheduler state is wake-up plumbing and defense in depth, never the sole source
of activation/session/effect authority. The source-owned activation and durable
wake state remain authoritative.

Any scheduler mutation is a separately approved protected checkpoint after
source certification and host preflight.

## Evidence

Sanitized evidence must be sufficient to prove:

- accepted source/runtime identity;
- activation/wake/proposal/order identities;
- target session and exact admission times;
- quote observation/deadline and accepted risk material;
- durable BEFORE/AFTER paper fingerprints;
- review/operator evidence digest and exact call counters;
- wake state transitions;
- zero retry;
- zero real-order mutation counters;
- final independent reconciliation result.

Evidence must not contain OAuth tokens, credential-manager secrets, raw request
headers, account identifiers beyond already-sanitized accepted operator
material, or arbitrary exception text.

## Source checkpoint plan

### 133-A — activation + wake identity/state core — ACCEPTED

Network-free/source-only.

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133a
PARENT 10e72fc5c609802e2704bb6a8b40bd99e8782d6a
HEAD   b0751e1ff2109b7f99725910ee901685e293e175
TREE   2230e11bcb3a2b27171aaa506f12110c31ae77a0
CI     #227 / 37388706716 SUCCESS
```

Accepted behavior:

- immutable/slotted `ReviewPaperActivation` and `ReviewPaperWake`;
- closed canonical JSON round-trip with unknown/missing/noncanonical material
  rejected;
- UUID5 activation identity over versioned canonical semantic facts;
- repository-wide identity policy preserved: filesystem `store_path` is
  retained exactly in activation storage material but excluded from UUID5
  domain identity, while `store_identity` remains identity-bearing;
- exact proposal, risk-limit, source/deployment, target-session, paper-account,
  buffer, quote-age, slippage/commission, order, creation-time, wake-contract,
  and expiry facts retained in the activation;
- deterministic wake identity bound to activation ID + target session date +
  proposal ID + local order ID;
- exact states `READY`, `PREPARE_STARTED`, `PREPARED`,
  `REVIEW_STARTED`, `COMPLETED`, `STOPPED`, `INDETERMINATE`;
- no outgoing transitions from terminal states;
- failure before the review-start fence terminates as `STOPPED`;
- failure after `REVIEW_STARTED` can terminate only as `INDETERMINATE`;
- caller-supplied timezone-aware timestamps only, UTC canonicalization, and no
  system-clock read;
- Decimal canonicalization independent of ambient Decimal context;
- no UUID4/randomness, filesystem access, SQLite, environment/config, network,
  subprocess, MCP/OAuth/provider adapter, risk evaluation, paper mutation,
  scheduler, retry, polling, or sleep authority.

The source-only checkpoint
`arch133-robinhood-unattended-activation-core` is registered once immediately
after the accepted Architecture-131 checkpoint sequence. Source-gate #227
reported Ruff check/format PASS, git diff check PASS, stable source identity,
and `AUTHORITY[arch133-robinhood-unattended-activation-core]=PASS`.

Focused implementation verification reported 233 core cases, 1,018 runner
cases, and the two profile-inventory cases across the focused/corrected-failure
runs, with Ruff and staged/diff checks passing. No FULL/ROBINHOOD certification
is required at this pure-model checkpoint; Architecture 132 reserves those for
the later coherent Robinhood/current-product boundaries.

### 133-B — durable wake store + provider-free reconciliation — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133b
PARENT 0609c08d2a3dd89b773c3416b629f377d04264ad
HEAD   e27ce1c2cebf38654404a96c06275e892909b2f5
TREE   37781465d0385aaa1251349ebb21fa5af59357c0
CI     #229 / 37392099387 SUCCESS
```

Accepted behavior:

- dedicated closed Architecture-133 SQLite state schema separate from the
  Architecture-131 review-paper ledger;
- exact canonical 133-A activation/wake JSON persisted with deterministic
  activation/wake identity binding;
- state-database path remains transport metadata and never enters deterministic
  identity material;
- exact-identical activation reopen is read-only/idempotent;
- same activation ID with different canonical activation bytes is a hard
  conflict, including a changed serialized paper-store path;
- first activation + READY wake admission is atomic;
- monotonic integer revision and exact one-shot optimistic compare-and-swap;
- transition legality is delegated to accepted 133-A rather than reimplemented;
- stale/conflicting writers fail closed with zero internal retry;
- terminal and INDETERMINATE state survives close/reopen with no restored
  transition authority;
- complete metadata/activation/wake snapshot is explicitly sorted and
  deterministically fingerprinted;
- independent verifier opens SQLite through URI `mode=ro`, never constructs
  the writer, and returns frozen/slotted sanitized verification facts;
- malformed schema/metadata, partial rows, noncanonical JSON, duplicate/binding
  conflicts, invalid revisions, and expected-state disagreement fail closed;
- embedded Architecture-131 paper-store material remains inert during normal
  admission/transition/verification paths;
- no provider/OAuth/risk-manager/review/paper-fill/scheduler/subprocess/
  environment/config/clock/retry/polling authority is introduced.

The source-only checkpoint
`arch133-robinhood-unattended-state-store` is registered exactly once after
133-A with `preflight=None`, `execute=None`, and no trusted remote-head
handoff. Source-gate #229 passed the 34-participant optimized batch, Ruff
check/format, git diff check, source identity stability, and both 133-A/133-B
authority pins.

Focused implementation verification reported 107 store/verifier cases, 233
activation-core cases, 1,067 runner cases, and 450 certification-inventory cases
across focused and corrected-failure runs. No ROBINHOOD/FULL certification is
required at this local-durability-only checkpoint.

### 133-C — effect-free one-wake composition — FROZEN NEXT

133-C proves the unattended ordering and one-attempt semantics without granting
a real provider or paper-effect surface. It may use the accepted 133-B state
store in tests and exact Architecture-131 domain/composition types, but any
provider/review/paper-effect edge must remain a bounded injected test seam.
Production binding of those seams is deferred to 133-D.

Freeze this source contract:

1. Add one source-owned 133-C coordinator/result model for exactly one activation
   and one wake. No scheduler, CLI, environment/config, OAuth storage, network
   transport, or broker/live mutation surface is added.
2. The coordinator receives the exact accepted 133-A activation, exact current
   133-B persisted wake/revision, the dedicated 133-B state store, and explicit
   caller-supplied instants needed for deterministic tests. It must never derive
   a historical/next session or manufacture a second activation/order identity.
3. Resolve the activation's exact target date through accepted 131-S and require
   the schedule/session date equals the activation target. Admission uses
   accepted 131-M semantics and the activation's exact opening/closing buffers.
4. Start only from durable `READY`. Atomically transition
   `READY -> PREPARE_STARTED` before the quote/preparation edge. A terminal or
   already-consumed/ambiguous wake returns/raises a bounded no-effect outcome and
   never restarts.
5. Provider acquisition is represented by one narrow typed quote/preparation
   seam whose test implementation returns the exact accepted 131-N snapshot
   material. The coordinator invokes that seam at most once. No generic
   arbitrary-command callback and no retry loop are permitted.
6. Build/validate the exact accepted 131-O/K risk-preview material from the
   frozen proposal, frozen risk limits, exact review-paper predecessor state,
   and the one returned snapshot. Risk rejection must durably terminate
   `STOPPED` without reaching the review-effect seam.
7. Require quote observation/source freshness and exact session admission at the
   explicit pre-effect instant. The earliest mark deadline is authoritative;
   freshness may never be extended or reacquired.
8. Once preparation is complete, durably transition
   `PREPARE_STARTED -> PREPARED`. Immediately before any simulated review
   effect, revalidate the exact preview/risk material and durable predecessor
   history required by accepted 131-Q semantics.
9. Durably transition `PREPARED -> REVIEW_STARTED` **before** invoking the
   narrow typed review/paper-effect seam. Tests must prove the seam observes the
   already-persisted REVIEW_STARTED state.
10. The review/paper-effect seam is invoked at most once and only for a
    non-rejected, still-admitted, still-fresh wake. In 133-C it is always a
    fake/double; no accepted 131-H/L production binding is reachable yet.
11. A successful fake effect returns one exact immutable synthetic result and
    permits `REVIEW_STARTED -> COMPLETED` once. Any exception/ambiguous result
    after the seam is invoked must durably terminate
    `REVIEW_STARTED -> INDETERMINATE`; no same-activation retry is possible.
12. Any failure proven before the review-start fence terminates as `STOPPED`.
    State-transition failure itself is fail-closed and cannot be compensated by
    a provider/effect call.
13. Reopen/replay of COMPLETED, STOPPED, or INDETERMINATE performs zero quote
    calls and zero effect calls. Reopen of REVIEW_STARTED performs zero effect
    calls and is classified ambiguous for independent reconciliation, never
    resumed.
14. Emit/return only bounded immutable composition facts suitable for later
    evidence: activation/wake identities, state revisions/transitions, exact
    schedule/admission classification, prepared quote deadline/risk outcome,
    effect-attempt count, and final state. Do not expose credentials, arbitrary
    exception text, account identifiers, or raw provider payloads.
15. No 133-C source path may call Robinhood MCP transport, interactive OAuth,
    `run_robinhood_forward_paper_cycle`, the deterministic paper pipeline, the
    Architecture-131 paper operator, Task Scheduler, placement/cancel/options/
    crypto mutation tools, or any sleep/poll/retry mechanism.

133-C focused tests must prove exact state/edge ordering, one quote edge maximum,
risk-rejected zero-effect behavior, stale/session-expired zero-effect behavior,
review-start persistence before the fake effect sees control, one fake review
attempt maximum, COMPLETED and INDETERMINATE terminal persistence, exception
classification on both sides of the review-start fence, zero replay/catch-up,
exact predecessor/risk drift rejection, and unreachable forbidden mutation
surfaces.

Register the next source-only checkpoint as
`arch133-robinhood-unattended-one-wake-composition` immediately after 133-B.
It must have `preflight=None` and `execute=None`. 133-C remains
source/fake-only; ROBINHOOD certification stays deferred to 133-D, where the
accepted provider/review-paper production boundaries are first bound.

### 133-D — bounded unattended review-paper execution

Add the source-owned one-wake execution boundary that may reach accepted 131-H
once only after durable review-start fencing. Provider effects remain disabled
in source tests.

### 133-E — zero-argument host/scheduler surface

Add a source-owned zero-semantic-argument launcher, persisted-OAuth-only policy,
runtime identity admission, and scheduler specification. No scheduler mutation.

### 133-F — final source certification

Run focused/source-gate verification throughout, ROBINHOOD certification at the
first complete Robinhood boundary, and FULL certification at the final coherent
current-product tree.

## Protected qualification sequence

No protected step is authorized by this document.

After 133-F source acceptance, the intended protected sequence is:

1. provider-free/read-only host preflight;
2. separately authorize publication of one exact single-session activation;
3. separately authorize one Architecture-133 scheduler installation/update;
4. separately authorize observation of the first unattended provider wake;
5. independent provider-free reconciliation;
6. disable/expire the one-session task/activation before review;
7. only after acceptance decide whether to design a multi-session soak.

Each protected step has fresh authority. A source/CI/certification PASS never
grants the next effect.

## Explicit non-goals

Architecture 133 v1 does not authorize or implement:

- real Robinhood order placement or cancellation;
- options or crypto trading;
- broker-paper/live-money execution;
- autonomous AI proposal generation;
- multi-day recurring soak authority;
- automatic catch-up/backfill;
- provider retry after ambiguity;
- browser-based unattended OAuth;
- D10 scheduler/runtime reuse;
- production deployment as part of source implementation.

Production/live real-money placement remains **NO-GO**.
