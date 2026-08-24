# Project Status and Roadmap

This document is the canonical high-level status/roadmap for AI Trading Bot.
Detailed architecture documents remain authoritative for their individual
subsystems, security contracts, and historical decisions.

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
reviewed foundations. C3 has now advanced beyond the previously inert effect
boundary: the branch contains the native Windows process/containment path, C1/C2/C3
production composition, the manual one-shot production capture command, and a
real Alpaca provider effect path.

C3 is **not yet certified complete**. The first real-provider E3 lineage reached
one real provider effect but ended `FAILED / CONFIRMED` with child classification
`TRANSPORT_FAILED`; no production snapshot was selected. A repeated identical CLI
request was safely blocked before a new attempt or provider effect. E3.2 now
retains only sanitized transport-stage diagnostics so future real acceptance
failures can be classified without exposing raw transport details.

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
provider request, or durable mutation. Actual provider-call count therefore
remains 1.

That behavior is required: a prior executed `FAILED / CONFIRMED` lineage is not
retry-safe. The same-session retry exception remains limited to the narrowly
proven `FAILED / NOT_STARTED` process-creation-failure case with no execution.

### Next legitimate acceptance attempt

Do not manufacture a different digest for the consumed August 21 intent by
changing an irrelevant request field. The next real provider attempt must use a
genuinely new completed XNYS session.

For the August 24, 2026 session, first run only the no-effect planning preflight
after regular close plus the planned buffer. It must prove the authorized session
is `2026-08-24`, emit `PROVIDER_CALL_PERFORMED=False`, and produce a request digest
distinct from the consumed August 21 digest:

`823e9bee88de07bbd6d3384559dd6207ad216e69d46443594f8664fff49854a7`

Only after that preflight is reviewed should exactly one new-session provider
call be authorized. A failure must be handled from its sanitized E3.2 stage and
durable disposition; the same consumed lineage must not be automatically retried.

## Immediate deep-review priorities

The latest real Windows runs identified two architecture-level reviews worth doing
before or alongside the next E3 acceptance attempt:

1. **C3 recovery and diagnostic authority.** Build an exception/crash matrix for
   `_capture_prepared_once()` covering durable predecessor/successor, whether an
   external effect may have occurred, operator visibility, permitted recovery,
   and retry permission. The current CLI is intentionally fail-closed but too
   opaque for efficient diagnosis; any future diagnostic interface must be
   read-only, durable-state-derived, sanitized, and incapable of granting retry
   authority.
2. **Crash-window / ambiguity analysis.** Prove every death window across process
   intent, process creation, receipt persistence, request delivery, resume intent,
   `ResumeThread`, result observation, cleanup, terminal write, and selection lands
   in a conservative `NOT_STARTED`, `CONFIRMED`, or `MAY_HAVE_OCCURRED` outcome
   without creating an unsafe automatic retry.

These are **Sol High, review-only first** tasks. If a real gap is found, freeze a
small architecture checkpoint before implementation.

Secondary reviews before unattended operation include Alpaca HTTP
interoperability/security policy, production `close()` and concurrent admission,
secret/transport-object lifetime, artifact publication TOCTOU, SQL invariant
mutation testing, clock/calendar authority, and the selected-snapshot to
paper-operation bridge.

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

At each checkpoint closeout:

1. Update this document's current/completed checkpoint or milestone status and
   roadmap where the checkpoint materially changes them.
2. Update the project's handoff document with the completed checkpoint, material
   architecture/workflow changes, verification or certification evidence, active
   branch/HEAD when known, and the next recommended checkpoint.
3. Review both documents even for small checkpoints. If one requires no wording
   change, explicitly record in the checkpoint report that it was reviewed and
   remains current.
4. Treat these documentation updates/reviews as a checkpoint completion gate: the
   checkpoint is not fully closed until both documents have been brought current
   or explicitly confirmed current.
5. Keep detailed architecture documents as historical/subsystem records rather
   than rewriting prior decisions to look current.
6. Update the README only when the public project description or broad product
   status changes.
7. Keep `AGENTS.md` focused on stable development, safety, architecture, testing,
   and AI-workflow rules.
8. Start implementation tasks by reading `AGENTS.md`, this status document, the
   handoff document, and the architecture documents directly relevant to the
   milestone.

The standing checkpoint workflow authorizes narrowly scoped documentation
edits/commits needed to keep this file and the handoff current at checkpoint
closeout. It does not authorize merging, rebasing, force-pushing, amending
unrelated commits, resolving review threads, changing PR metadata, or modifying
unrelated files.
