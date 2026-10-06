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

### 133-C — effect-free one-wake composition — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133c
PARENT 4b86018fffce8e46ec348cc5aeddf0a8657d824b
HEAD   3f5a5b673bc9d66409e415152d6252cd80a46e3a
TREE   7b048cedea8a97501198311229b25ab32f112735
CI     #231 / 37410294723 SUCCESS
```

Accepted behavior:

- one source-owned coordinator/result boundary for exactly one activation/wake;
- exact accepted 133-A activation, exact 133-B persisted wake/revision, explicit
  caller-supplied instants, and no system-clock read;
- exact target-session resolution through accepted 131-S and admission through
  accepted 131-M with the activation's frozen buffers;
- durable READY -> PREPARE_STARTED before the quote seam;
- one quote/preparation seam invocation maximum;
- exact accepted 131-N snapshot plus 131-O/K preview/risk material;
- earliest exact source-mark freshness deadline, with no extension or
  reacquisition;
- durable PREPARE_STARTED -> PREPARED before final predecessor/risk/freshness
  revalidation;
- durable PREPARED -> REVIEW_STARTED before the fake effect receives control;
- one fake review/paper-effect invocation maximum;
- successful exact acknowledgement -> COMPLETED once;
- post-effect exception/ambiguity -> INDETERMINATE with no retry;
- pre-effect rejection, stale/expired session, material drift, or exception ->
  STOPPED with zero effect attempts;
- terminal replay is read-only with zero quote/effect calls;
- PREPARE_STARTED/PREPARED/REVIEW_STARTED reopen is reconciliation-only and
  performs zero new provider/effect calls;
- bounded immutable sanitized result facts only;
- no production Robinhood transport/OAuth/operator/pipeline/scheduler/mutation,
  subprocess/config discovery, polling/sleep/retry/catch-up/fallback authority.

The source-only checkpoint
`arch133-robinhood-unattended-one-wake-composition` is registered exactly once
after 133-B with
`remote_branch=feature/robinhood-unattended-review-paper-133c`,
`preflight=None`, `execute=None`, and no trusted remote-head handoff.
Source-gate #231 passed 35 optimized checkpoints, 60 test paths, 96 Ruff paths,
Ruff check/format, git diff check, source identity stability, and the
133-A/133-B/133-C authority pins.

Focused implementation verification reported 2,084 distinct cases: 87
composition, 340 overlapping 133-A/133-B, 1,545 runner/inventory, and 112
accepted 131-Q cases. Current certification inventory is FULL 119, ROBINHOOD
46, LEGACY 204, EXHAUSTIVE 323. No ROBINHOOD/FULL certification is required at
this fake-only composition boundary.

### 133-D — bounded unattended review-paper execution — ACCEPTED

Accepted source identity:

```text
BRANCH feature/robinhood-unattended-review-paper-133d

IMPLEMENTATION
HEAD 14bc4902a231fc87f8449c5971f2f8a9b382cc6e
TREE 084c8b794e3aa6f2795ef70deb70f92b92842bcd

CI-RECOVERY SAME-TREE HEAD
HEAD 6677676170fa9ffb70ca62809c03b2df40ca1253
TREE 084c8b794e3aa6f2795ef70deb70f92b92842bcd

SOURCE-GATE #234 / 37413871721 SUCCESS
```

The original implementation push received no GitHub workflow run despite the
already-reviewed Robinhood branch-family trigger. No missing run was treated as
acceptance. A single no-file-change fast-forward commit preserved the exact
implementation tree and retriggered the gate. #234 passed the 36-checkpoint
optimized batch, 61 test paths, 98 Ruff paths, Ruff check/format, diff check,
stable source identity, and all 133-A/B/C/D authority pins.

Accepted behavior:

- one source-owned 133-D binding around the accepted 133-C coordinator; no
  duplicate wake state machine or transition authority;
- persisted OAuth read exactly for the bounded provider path, with no browser,
  interactive challenge, token refresh, discovery/registration, or credential
  write authority;
- exact required-symbol validation and one Robinhood quote request maximum;
- accepted 131-N snapshot construction with the activation's frozen freshness
  policy;
- independent durable REVIEW_STARTED verification before review-paper operator
  control;
- exact proposal/risk/order/store/source material preserved and revalidated;
- deterministic market-order intent uses the activation's frozen local order ID;
- accepted 131-H review-paper operator invoked at most once;
- successful acknowledgement requires exact PASS evidence, expected call
  budgets, exact synthetic paper record, deterministic idempotency, and zero
  placement/cancel/options/crypto mutation counters;
- quote/OAuth/provider failure before the 133-D effect boundary is STOPPED;
- exception, malformed acknowledgement, process/transport ambiguity, or inability
  to prove the exact result after effect entry is INDETERMINATE;
- terminal/reconciliation replay performs zero new provider/review effects;
- no quote reacquisition, fallback session, catch-up, polling, sleep, retry,
  scheduler mutation, environment/config discovery, autonomous proposal
  generation, or broker/live effect.

The source-only checkpoint
`arch133-robinhood-unattended-review-paper-execution` is registered exactly once
after 133-C with
`remote_branch=feature/robinhood-unattended-review-paper-133d`,
`preflight=None`, and `execute=None`.

Required ROBINHOOD certification passed on the exact accepted tree:

```text
profile robinhood PASS
robinhood-1: 1893 / 1893
robinhood-2: 1899 / 1899
total:       3792 / 3792
skipped: 0
failed:  0
errors:  0
evidence: F:\AI\temp\certification\arch133d-robinhood-667767
```

Current certification inventory is FULL 120, ROBINHOOD 47, LEGACY 204,
EXHAUSTIVE 324. FULL remains deferred to 133-F.

### 133-E — zero-argument host/scheduler source surface — ACCEPTED

Accepted source:

```text
BRANCH feature/robinhood-unattended-review-paper-133e
PARENT c24039f229b66f1d5510cf8e5c317cc8d0cbafc5
HEAD   ee542d5decf9b9fb1933a0a8681ee0c5cae29f27
TREE   274e2097c86a7cf41efa9e7af41f7324686d1ff7
CI     #236 / 37427681435 SUCCESS
```

Accepted behavior:

- fixed Architecture-133 launcher with zero semantic command-line arguments and
  sanitized rejection before trading-source import;
- exact source HEAD/TREE, runtime executable/version/launcher digest, Trading
  principal, and deployment identity admission before OAuth/provider access;
- one fixed host binding, activation publication, wake store, paper store, and
  evidence location; no CLI/environment path or trading-authority injection;
- exact canonical activation bytes and dedicated wake-state binding before
  execution composition;
- one current UTC read maximum for an admitted READY wake;
- at most one delegation to accepted 133-D and no retry/polling/catch-up loop;
- persisted-OAuth-only execution path and provider-free persisted-OAuth
  availability metadata for preflight;
- terminal and reconciliation-only wake states return read-only with zero
  133-D/provider delegation;
- immutable single-session scheduler spec with task identity distinct from D10,
  zero semantic arguments, IgnoreNew overlap policy, zero restart/repetition
  authority, and explicit session start/end boundaries;
- scheduler/task state never creates activation/effect authority;
- no Task Scheduler query/mutation surface in the scheduler module;
- provider-free Q133-1 preflight verifies exact source/runtime/activation/wake,
  paper predecessor, OAuth availability metadata, proposed scheduler spec, and
  zero consumed wake authority without invoking 133-D;
- bounded sanitized host/preflight evidence with no credentials, account IDs,
  raw provider payloads, arbitrary exception text, or secret-bearing CLI/env
  material.

The source-only checkpoint
`arch133-robinhood-unattended-host-scheduler-surface` is registered exactly
once after 133-D with
`remote_branch=feature/robinhood-unattended-review-paper-133e`,
`preflight=None`, and `execute=None`.

Focused verification reported 1,051 distinct cases: 80 host, 356 runner, 2
inventory, and 613 overlapping tests. Source-gate #236 passed 37 checkpoints,
62 test paths, 103 Ruff paths, Ruff check/format, git diff check, stable source
identity, and all 133-A/B/C/D/E authority pins.

Current certification inventory is FULL 121, ROBINHOOD 48, LEGACY 204,
EXHAUSTIVE 325. No separate ROBINHOOD rerun is required at 133-E because the
accepted 133-D provider/review-paper effect boundary was not changed.

Architecture-124's historical sealed pre-source D10 guard remains historical
one-week-soak precedent, not an Architecture-133-v1 requirement. 133-E's frozen
single-session contract requires exact source/runtime admission before
OAuth/provider access; native deployment/ACL qualification remains a separate
protected gate.

### 133-F — final source certification — ACCEPTED

Architecture 133 is fully source-certified at the exact closed 133-E tree:

```text
BRANCH feature/robinhood-unattended-review-paper-133e
HEAD   31ab26fa842594b9d915ff8bba65a705978b0b00
TREE   49afbefd4767a63b88c02c24f2a2bbbc0a282f21
SOURCE-GATE #236 / 37427681435 SUCCESS
DOCS-GATE   #237 / 37429153807 SUCCESS
```

Final FULL certification passed:

```text
profile full PASS

broad-1
modules 58
cases 2702
passed 2702
skipped 0
failed 0
errors 0

broad-2
modules 63
cases 2139
passed 2136
skipped 3
failed 0
errors 0

TOTAL
cases 4841
passed 4838
skipped 3
failed 0
errors 0
wall 300.214 s
evidence F:\AI\temp\certification\arch133f-full-31ab26f
```

The FULL run covered all 121 current-supported modules, including the 48-module
ROBINHOOD subset. The separately required first complete Robinhood-boundary
certification already passed at 133-D with 3,792 / 3,792 cases, so no mechanical
second ROBINHOOD run was required at 133-F.

The exact certified feature source was compared against live `develop` before
this docs-only closeout:

```text
origin/develop HEAD 10e72fc5c609802e2704bb6a8b40bd99e8782d6a
merge base          10e72fc5c609802e2704bb6a8b40bd99e8782d6a
ahead                11
behind               0
open PR              none
```

Architecture 133 is therefore source-complete and merge-ready. The final
canonical 133-F closeout changes documentation only and does not alter the
certified executable/test source.

No Architecture-133 source/certification acceptance authorizes production host
provisioning, activation publication, Task Scheduler mutation, a Robinhood
provider wake, paper-effect qualification, broker placement, or live trading.
Those remain the separately approved protected sequence below.

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
