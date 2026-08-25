# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
The canonical cross-chat/development handoff is `docs/AI_TRADING_BOT_HANDOFF.md`.
Detailed architecture documents remain authoritative for their individual
subsystems, security contracts, and historical decisions.

A copy of the handoff may also be uploaded to the ChatGPT Trading Bot Project for
convenient context sharing, but that Project file is a mirror rather than an
independent source of truth. When copies differ, use the Git-tracked handoff.

## Long-term objective

Build a conservative automated trading platform that can progress safely from
deterministic historical research to simulated paper trading, unattended paper
operation, broker-paper operation, restricted live trading, and finally a
polished end-user application.

The platform is not permanently paper-only. Live trading is a long-term product
goal, but it remains unavailable until all separately reviewed safety,
credential, brokerage, reconciliation, operator-control, and acceptance gates
are complete.

## Current production status

**Production/live trading: NO-GO.**

C1 `ValidatedProductionAuthority` and C2 `WindowsTransactionalAuthority` are
reviewed foundations. C3 has advanced through the native Windows
process/containment path, C1/C2/C3 production composition, the manual one-shot
production capture command, and two controlled real Alpaca provider effects.

C3 is **not yet certified complete** because no real provider lineage has produced
a parent-verified selected production snapshot. The August 21 lineage ended
`FAILED / CONFIRMED` with the original broad child classification
`TRANSPORT_FAILED`. E3.2 then added closed stage diagnostics and E3.3 corrected
truthfulness so programming defects are not mislabeled as transport failures.
The E3.3 fixed runtime was subsequently built, inspected, deployed through the
sealed-runtime procedure, Trading read/execute access was republished, and the
non-admin Trading zero-provider preflight passed.

A fresh August 24 planning preflight then passed with authorized snapshot date
`2026-08-24` and a digest distinct from the consumed August 21 request. Exactly one
new provider effect was authorized. That August 24 lineage also ended
`FAILED / CONFIRMED`, but E3.3 correctly narrowed the child classification to
`TRANSPORT_RESPONSE_METADATA_FAILED`. Durable read-only inspection verified
entered provider fence, complete result transport, clean child exit, complete
parent/staging cleanup, valid evidence hashes, and no snapshot/artifact authority.

C3-E3.4 is now source-certified. It preserves every existing metadata validation
rule while replacing the broad response-metadata classification with a closed,
sanitized sub-classification set. The E3.4 source has **not yet been deployed** to
the fixed production runtime, so no further real provider effect is authorized.

There is still no unattended production scheduler, brokerage live-order
transport, or authorization to place real-money orders.

## Implemented foundations

The repository includes:

- deterministic trade proposal, risk, execution, portfolio, and ledger models;
- historical market-data providers and deterministic NYSE/XNYS calendar support;
- single- and multi-symbol backtesting with complete-frame and next-open semantics;
- baseline strategies, walk-forward/research infrastructure, optimization,
  analytics, and human-readable reporting;
- simulated paper-account and paper-operation/recovery infrastructure;
- durable evidence, deterministic UUID5/canonical serialization contracts, and
  historical-evaluation integrity rules;
- Windows authority provisioning, schema, validation, capability, and
  transactional-authority milestones through C2;
- the C3 capture planner, canonical child protocol, Credential Manager boundary,
  isolated provider core, native Windows containment/lifecycle integration,
  parent-side production composition, and manual production capture boundary;
- a canonical production transactional SQLite artifact and reviewed
  lifecycle/recovery/concurrency boundaries.

## Completed Windows authority foundation

Architecture 77 defines the transactional capture-authority state machine,
durable evidence, capabilities, recovery rules, and lifecycle ordering.
Architectures 78-81 define provisioning, schema, capability, and the C2 service
boundary.

C2 final certification previously completed with:

- combined service + Architecture-77 suite: 775 passed;
- complete repository suite: 2,725 passed, 13 skipped, 0 failed;
- production SQL unchanged at 118,896 bytes with SHA-256
  `aa61df2f5db0090f8373222d1f5e492a58f4c10273afacfab45e382bacd4bb58`.

## Current milestone: C3 effectful market-data capture

C3 is the only reviewed bridge from C1/C2 authority into real market-data
credentials, native process execution, Alpaca transport, staged capture,
independent parent verification, publication, and snapshot selection.

Completed/implemented C3 areas include:

1. Immutable capture planning and deterministic request/session identity.
2. Canonical bounded parent/child protocol.
3. C1/C2/C3 composition and the rule that child success is evidence, not authority.
4. Exact Windows Credential Manager targets with Trading-SID verification and no
   fallback credential source.
5. One-shot isolated child/provider execution with a provider-call fence.
6. Native suspended-process topology using reviewed Job Object and inherited-handle
   constraints.
7. Durable C2 execution/resume ordering around `CreateProcessW` / `ResumeThread`.
8. Native acceptance probes for environment, handle inheritance, containment, and
   hostile/reparse/device substitution rejection.
9. Manual one-shot `production_daily_snapshot_capture` operator boundary.
10. E3.2 sanitized transport-stage classifications, including request,
    response-start, response-metadata, and response-body failure classes.
11. E3.3 truthful transport-stage classification: expected transport/protocol
    failures retain the closed sanitized stage, unexpected programming defects
    remain internal failures, and sanitized non-200 HTTP status errors remain a
    distinct HTTP-response path.
12. E3.4 closed sanitized response-metadata reasons and child classifications for
    acquisition, malformed headers, duplicate relevant headers, content encoding,
    transfer encoding, transfer-length conflict, content length, request ID,
    content type, and generic fallback.

### E3.3 certification and deployment

C3-E3.3 source certification completed on commit
`bf88890d87ed1734a4634e4b8069ff5232a20994` after implementation commits
`7fdbd185b4cae1d8392bb7473f40ad69a4fb967d` and
`bf88890d87ed1734a4634e4b8069ff5232a20994`:

- complete repository suite: 3,094 passed, 16 skipped, 0 failed;
- Ruff check: passed;
- Ruff format check across Git-tracked Python sources: passed.

The accepted E3.3 production wheel was built from the certified implementation
checkpoint and inspected before deployment:

- wheel length: 672,104 bytes;
- wheel SHA-256:
  `ed87fcce586a3b2f2477f2b99e6c404d7c42f5cc2ef29e230b12cd8ca7640b3b`;
- 192 wheel entries / 191 RECORD hashes verified;
- production SQL remained 118,896 bytes with the frozen SHA-256 above;
- installed semantic checks proved the E3.3 HTTP hierarchy and narrowed stage
  behavior.

The sealed-runtime deployment passed with runtime quiescence, temporary Trading
access revocation, offline install, installed RECORD reconciliation, C1 validation,
Administrator ownership, Administrator/SYSTEM sealing, Trading RX republication,
and a non-admin Trading zero-provider preflight. No provider request occurred
through that deployment/preflight sequence.

### E3.4 source certification

C3-E3.4 is source-certified at implementation commit
`134467ecda1ffbb39f48cf68a2d3e9017d1d2f61` (`fix: classify Alpaca response
metadata failures`). The certified diff survived the E3.3 docs-only fast-forward
byte-for-byte with SHA-256
`6d9232fef1f5dfaf8b1df329e28db20646d108a81b0e1410e2d2d9cd82cdbca6`.

Final broad certification:

- complete repository suite: 3,136 passed, 16 skipped, 0 failed;
- Ruff check over Git-tracked Python: passed;
- Ruff format check over 358 Git-tracked Python files: passed;
- final `git diff --check`: passed.

E3.4 changes diagnostic precision only. It does not change C1/C2 authority,
production SQL, provider-call budget, endpoint/feed/query semantics, Credential
Manager behavior, native process ordering, or retry authority. Unexpected
programming defects still escape expected transport catches and become sanitized
`INTERNAL_FAILED` child results.

The native ordering continues to preserve the core rule:

```text
CreateProcessW suspended
-> durable C2 execution / PRE_RESUME_READY
-> write exact canonical child request
-> close request writer
-> commit ResumeIntent
-> ResumeThread exact primary thread once
-> bounded child/process observation
-> cleanup evidence
-> parent verification / terminal / selection
```

`RESUME_RECORDED` is lifecycle evidence; it is not provider-success evidence.

## Current E3 real-provider acceptance state

### Consumed August 21 lineage

The first E3 real-provider attempt produced exactly one real external provider
effect:

```text
session: 4667f0a1-8890-57b9-ae07-98ffc9633ade
attempt ordinal: 0
terminal outcome: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_FAILED
```

A second invocation using the exact same deterministic request was blocked before
attempt allocation. It created no new attempt, claim, reservation, child,
provider request, or durable mutation.

The consumed August 21 C2 request digest is:

`823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7`

### Consumed August 24 lineage

After E3.3 deployment and zero-provider verification, the pure planner authorized
snapshot `2026-08-24` with a fresh digest:

`ed4cc49dc385486ac5ca623f64e99766247e371c90f29f1ff8fd585841d6b651`

The freshness guard proved no existing durable session for that digest. Exactly
one real provider invocation then produced:

```text
session: c78b94a4-963f-5197-9a03-16017ea2203b
attempt: e1a74104-150c-5ef9-96f3-f9d6d0c8aee0
terminal: b4c34eec-81d4-5dad-b01a-34d88fca05d4
terminal outcome: FAILED
provider disposition: CONFIRMED
child classification: TRANSPORT_RESPONSE_METADATA_FAILED
selection: none
snapshot: none
```

Read-only durable inspection confirmed:

```text
child fence state: ENTERED
result transport: COMPLETE
process outcome: EXITED_ZERO
parent cleanup: COMPLETE
artifact verification: NOT_ATTEMPTED
staging cleanup: COMPLETE
terminal reason: POST_FENCE_CHILD_FAILURE
terminal evidence digest: valid
terminal diagnostics digest: valid
```

This lineage is consumed and must not be retried. Actual real-provider call count
is now exactly **2**.

### Planner clock contract

The first August 24 pure-plan attempt failed safely before any durable/provider
effect because the exchange-local calendar date was still August 24. The current
planner reconciles by calling `previous_session(requested_at_utc)`, which first
moves back from the **New York calendar date**. Therefore a request for completed
session date `D` reconciles only once the New York calendar date has advanced to
`D + 1`; it is not enough merely to wait until regular market close plus a buffer.

For the August 24 request this meant waiting until midnight EDT on August 25
(9:00 PM PDT on August 24). The subsequent pure planner passed at
`2026-08-25T04:08:44.675052+00:00`.

Treat that exchange-date rule as the current acceptance contract. Changing the
planner to a different close-time semantic would be separate clock/authority
architecture work and requires Sol High review.

### Next legitimate acceptance attempt

Do not retry either consumed lineage and do not manufacture a new digest by
changing irrelevant fields. A future provider effect must use a genuinely new
completed XNYS session.

Before provider call #3 can even be considered:

1. Build a new fixed-runtime artifact from the E3.4 implementation checkpoint
   `134467ecda1ffbb39f48cf68a2d3e9017d1d2f61`.
2. Inspect exact wheel contents, source binding, SHA-256, byte length, RECORD, SQL
   digest, and the E3.4 classification behavior.
3. Redeploy through the established sealed-runtime procedure with no provider
   effect.
4. Restore exact Trading RX and complete the non-admin zero-provider preflight.
5. Use the next genuinely completed XNYS session and wait until the New York
   calendar date advances to the following day before the pure planning preflight.
6. Review the fresh authorized session and request digest.
7. Only then make an explicit decision whether to authorize exactly one provider
   effect.

**Provider call #3 is currently unauthorized.**

## Immediate deep-review status

The first Sol High recovery/crash review is complete. It found no unsafe automatic
retry path, but identified two follow-up architecture concerns before unattended
operation: operator diagnosis/recovery routing is too opaque, and some proven
pre-effect/safe-continuation durable states are not directly resumable through the
one-shot production facade. Any future diagnostic interface must remain read-only,
durable-state-derived, sanitized, and incapable of granting retry authority.

The Alpaca HTTP interoperability/security review led to E3.3 and E3.4. E3.3 fixed
misclassification of unexpected programming defects. E3.4 now makes known
response-metadata validation failures precise without persisting raw headers,
provider/server text, response bodies, credentials, or arbitrary exception text.

Remaining secondary reviews before unattended operation include production
`close()` and concurrent admission/drain behavior, secret/transport-object
lifetime, artifact publication TOCTOU, SQL invariant mutation testing,
clock/calendar authority, and the selected-snapshot to paper-operation bridge.

## Roadmap after C3

### 1. Reliable manual paper cycle

Establish one trustworthy end-to-end manual cycle:

verified selected market snapshot -> strategy -> proposals -> deterministic risk ->
paper execution -> durable before/after evidence.

The paper engine must consume only the selected parent-verified C3 snapshot, not a
caller-selected path or merely child-produced file. Exactly-once paper-cycle
identity and restart behavior should be frozen before automation.

### 2. Unattended paper operation

Add authoritative XNYS scheduling, Task Scheduler/service integration, startup
reconciliation, crash recovery, health/alerting, durable run status, and
stale/missing-data fail-closed behavior.

### 3. Long paper soak

Operate unattended long enough to expose scheduling, data-quality, recovery,
reconciliation, reboot, provider-outage, and storage assumptions while consequences
remain simulated.

### 4. Broker-paper integration

Add a real brokerage adapter in paper/sandbox mode with account/position reads,
submit/cancel/replace, broker IDs, fills, rejects, partial fills, durable
reconciliation/idempotency, ambiguous-submit recovery, and startup broker
reconciliation.

### 5. Live-readiness milestone

Before any real-money order path can be enabled, implement and accept explicit
operating-mode authority, separate live credentials, exact account verification,
strict live limits, kill switch/emergency stop, outage/halt behavior, startup
broker reconciliation, operator-visible health/reconciliation state, and clear
ambiguous-outcome recovery procedures.

### 6. Tiny restricted live deployment

Only after live-readiness acceptance, permit a deliberately tiny long-only live
deployment with conservative approved symbols, exposure, frequency, and order-size
limits. Live mode must remain explicitly enabled and fail closed.

### 7. Mature operations and deepen AI

Expand strategies, optimization, and AI only after the platform demonstrates
trustworthy operations, durable evidence, reconciliation, and recovery. AI may
assist analysis and proposal generation but may never bypass deterministic risk,
authority, brokerage, or operator-control boundaries.

## 100% product-completion goal: user-friendly GUI

The final product milestone is a polished graphical application that exposes the
same reviewed service boundaries used by CLI, automation, tests, and unattended
operation.

It should provide portfolio/account dashboards; market/session/provider/scheduler/
capture/broker/system health; strategy configuration; backtest/walk-forward/
optimization workflows; charts and analytics; proposal-to-risk-to-order-to-fill
traceability; paper/broker-paper/live views; orders/fills/rejects/partials/
positions/reconciliation; recovery workflows; searchable audit/history; settings;
unmistakable operating-mode indicators; future live account identity/controls;
emergency stop; and actionable human-readable errors.

The GUI is a presentation/operator-control layer, not an alternate trading, risk,
authority, brokerage, reconciliation, credential, or identity engine.

## Stable product constraints

Unless a later explicit architecture milestone changes them:

- long-only US stocks and ETFs;
- no margin or leverage;
- no options;
- no short selling;
- no crypto;
- deterministic risk approval for every order;
- paper mode by default;
- complete auditability of decisions and transactions.

## Documentation workflow

Documentation closeout is part of **every completed and accepted development
checkpoint**, not only major milestone boundaries. It should happen automatically
before the checkpoint is treated as closed or work moves to the next checkpoint.

The authoritative checkpoint-documentation pair is:

```text
docs/PROJECT_STATUS.md
docs/AI_TRADING_BOT_HANDOFF.md
```

At each checkpoint closeout:

1. Update this document's current/completed checkpoint or milestone status and
   roadmap where the checkpoint materially changes them.
2. Update `docs/AI_TRADING_BOT_HANDOFF.md` with the completed checkpoint, material
   architecture/workflow changes, verification or certification evidence, active
   branch and latest implementation checkpoint when known, and the next
   recommended checkpoint. Avoid self-referential attempts to record the handoff
   commit as the live branch HEAD; verify live HEAD when resuming.
3. Review both Git documents even for small checkpoints. If one requires no
   wording change, explicitly record in the checkpoint report that it was reviewed
   and remains current.
4. Treat the Git-tracked pair as the source of truth. A handoff copy uploaded to
   the ChatGPT Trading Bot Project is a context mirror only.
5. After material checkpoints, refresh the ChatGPT Project mirror from the
   canonical Git handoff when tooling permits. If direct Project-file replacement
   is unavailable, provide/export the current Markdown for manual replacement and
   call out any known mirror staleness when starting a new chat.
6. Treat the two Git-document updates/reviews as a checkpoint completion gate: the
   checkpoint is not fully closed until both have been brought current or
   explicitly confirmed current.
7. Keep detailed architecture documents as historical/subsystem records rather
   than rewriting prior decisions to look current.
8. Update the README only when the public project description or broad product
   status changes.
9. Keep `AGENTS.md` focused on stable development, safety, architecture, testing,
   and AI-workflow rules.
10. Start implementation tasks by reading `AGENTS.md`, this status document, the
   canonical handoff, and the architecture documents directly relevant to the
   milestone.

The standing checkpoint workflow authorizes narrowly scoped documentation
edits/commits needed to keep this Git-tracked pair current at checkpoint closeout.
It does not authorize merging, rebasing, force-pushing, amending unrelated
commits, resolving review threads, changing PR metadata, or modifying unrelated
files.
