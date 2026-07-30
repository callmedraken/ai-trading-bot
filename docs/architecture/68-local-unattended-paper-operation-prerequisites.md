# Local unattended paper-operation prerequisites

## Boundary

This document records the approved prerequisites that must exist before the
manual restart-safe paper-operation coordinator can be invoked on an unattended
schedule. It is architecture and risk policy, not scheduler approval.

The supported setting is one Windows machine and one local filesystem. Paper
trading remains simulated. There is no external paper account, brokerage,
real-money execution, cloud registry, distributed coordination, database,
scheduler service, daemon, or background loop.

## Required milestones

The incremental order is:

1. authoritative local lineage-head artifacts and verification;
2. deterministic scheduled-session, launch, capture-attempt, and operation
   identities plus a read-only readiness evaluator;
3. a Windows local single-writer guard;
4. a guarded capture-readiness dry-run with immutable decision evidence;
5. capture-only unattended operation;
6. an optional separately approved, human-authored target execution boundary;
7. a narrow Windows scheduling adapter;
8. repeated unattended simulated-paper validation.

Every milestone has an independent stop/go decision. Capture-only operation is
the recommended first stopping point.

## Authority prerequisite

Scheduling must never choose account state by checkpoint filename, directory
order, modification time, UUID order, or highest sequence. It requires:

- append-only explicit lineage manifests;
- immutable, deterministic head records;
- one narrowly mutable current-head reference;
- complete verification from that reference to genesis;
- strict one-edge advancement from explicit evidence;
- fail-closed rollback, fork, stale reference, unsafe path, and ambiguity
  handling.

The finalized transition directory remains authoritative account-state evidence
after commit. Until that transition is explicitly nominated, verified, and
published into a new head, the scheduler-selection pointer remains at the prior
head and no later operation may run.

Milestone 69 implements only this authority prerequisite. Milestone 70 consumes
its verified immutable evidence without reopening, scanning, or mutating the
authority root.

## Deterministic identities and readiness

Milestone 70 scheduled identities use dedicated UUID5 namespaces and versioned,
byte-length-framed material. They must bind the intended XNYS session, ordered
SPY/QQQ universe, provider/config versions, selected authoritative terminal,
selected snapshot evidence, and exact target/config evidence. Repeated launches
must not generate random caller keys.

Human approval attests to an already fixed operation and must not change its
identity. A material target, configuration, snapshot, or terminal change creates
a different reviewed operation.

Milestone 70 remains read-only. It does not approve scheduling or capture and
does not weaken any later single-writer, credential, retry, alert, backup, or
human-approval prerequisite.

## Readiness policy

The current market calendar identifies session dates but not official hours or
early closes. Milestone 70 therefore accepts a separately versioned, explicit
XNYS readiness schedule plus publication delay, retry window, lateness, and
clock-skew policies. It does not fetch or generate official hours.

Snapshot eligibility must include:

- exact intended target session;
- exact ordered SPY/QQQ universe;
- complete offline verification;
- provider completeness;
- `snapshot captured_at >= terminal as_of`;
- no future, stale, mixed-session, or partial data;
- deterministic immutable selection among capture attempts.

Operation readiness must additionally prove the complete authoritative head,
explicit target/config authority, deterministic scheduler IDs, valid execution
session and chronology, coordinator `PENDING` state, absence of receipts,
transitions, staging, conflicts, and credentials, and any required human
approval.

Coordinator `PENDING` alone is not scheduled `READY`. The deterministic
classification precedence is `CONFLICTING`, `MANUAL_REVIEW_REQUIRED`, `BLOCKED`,
`ALREADY_COMPLETED`, `NOT_READY`, then `READY`.

## Later single-writer prerequisite

The approved version-one direction is one authority-wide Windows named mutex
with immutable lease evidence. The kernel primitive, not a timestamped file or
directory, is lock authority. An abandoned operation owner requires manual
review. No lock may be deleted merely because it is old.

Milestone 71 implements that local exclusion boundary with the exact global
mutex name, bounded acquisition outcomes, immutable start/release evidence, and
fail-closed abandoned-owner handling. It does not approve scheduling, capture,
readiness orchestration, paper-operation execution, or head advancement.
Verified mutex ACL hardening remains explicitly unimplemented; callers that
require it receive `UNSUPPORTED`.

Milestone 72 composes milestones 69 through 71 into a one-shot guarded
capture-readiness dry run. It publishes immutable decision evidence but cannot
invoke a provider or create a snapshot. Capture-only unattended operation
remains a later separate approval.

Milestone 69 assumes one caller already holds exclusive publication authority.
It contains no lock, lease, PID, timeout, scheduler, or stale-owner logic.

## Credentials and process separation

Future unattended Alpaca data credentials must reside in Windows Credential
Manager or an equivalent OS-protected store. They may enter only an allowlisted
capture child environment. They must not appear in repository files, `.env`
files, task arguments, logs, artifacts, crash output, or the paper-operation
process.

Provider-data credentials and any future broker credentials are separate
security boundaries. Broker credentials and broker execution remain excluded.

## Retry and human review

Bounded provider capture retry may allocate a new deterministic attempt ID.
Paper-operation execution may never be retried automatically after ambiguous
state. Failed receipts, crash-left staging, abandoned operation ownership,
committed transitions without completed audit/head publication, missed
execution windows, and unexpected runtime failures require review.

No scheduling implementation is permitted until retry, alert, notification,
retention, backup, disable-switch, dry-run, and operational-test policies are
approved.

## Retention and recovery

Every artifact in the transitive dependency closure of a retained head,
manifest, transition, or receipt is non-prunable. Version one performs no
automatic repair or pruning. Archive and pruning require separate verified,
explicit operator workflows.

Unattended account-state execution is not acceptable with only one unbacked
local filesystem. Capture-only experimentation may separately accept that loss
risk.

## Non-goals

- no scheduler or Task Scheduler adapter;
- no provider capture in the authority subsystem;
- no target, signal, strategy, or optimization authority;
- no operation execution or receipt recovery;
- no broker-backed reconciliation or orders;
- no real-money path;
- no multi-host coordination;
- no cloud registry or database;
- no automatic repair, cleanup, discovery, or ambiguous-operation retry.
