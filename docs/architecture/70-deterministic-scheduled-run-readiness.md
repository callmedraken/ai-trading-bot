# Deterministic scheduled-run readiness

## Milestone-B boundary

Milestone B defines path-independent scheduled identities, immutable capture and
selection evidence, an explicit XNYS hours boundary, and a pure read-only
readiness decision. It does not schedule, wait, retry, capture, access
credentials, execute a paper operation, publish files, advance the lineage
head, recover receipts, generate targets, notify an operator, or acquire a
lock.

Every time, dependency, policy, verification result, and health result is an
input. The evaluator never reads a clock, environment variable, directory,
provider, broker, network connection, or mutable pointer.

## Identity domains

Five fixed UUID5 namespaces use UTF-8 byte-length-framed, versioned material:

| Identity | Namespace | Material version |
| --- | --- | --- |
| scheduled paper session | `1a3373dc-b18e-583b-b983-b60336bfa7ea` | `scheduled-paper-session-v1` |
| scheduled launch | `4f62bcb9-1e06-55fa-82b8-d1293447390b` | `scheduled-launch-v1` |
| scheduled capture attempt | `b9ebad76-c89b-5df0-9256-203f0cee267a` | `scheduled-capture-attempt-v1` |
| scheduled snapshot selection | `261aef12-6159-5def-9508-56b406b649d8` | `scheduled-snapshot-selection-v1` |
| scheduler caller-idempotency key | `fac48241-5672-5ce3-9014-9ed29b47d07a` | `scheduler-caller-idempotency-key-v1` |

The session identity binds the authority epoch, exact calendar descriptor,
target session D, execution session E, ordered universe, and universe/readiness
policy versions. A launch additionally binds its phase, explicit nominal UTC
slot, retry ordinal, and runner policy. Hostname, PID, boot identity, filesystem
path, actual start time, and Task Scheduler instance identity are excluded.

A capture-attempt identity binds one ordinal, ordered symbols, timeframe,
adjustment, complete provider descriptor, feed, currency, policy version, and
exact configuration evidence. Allocation and provider invocation are outside
this milestone. One ordinal is reserved for at most one provider call.

The selection identity binds the exact head record, terminal checkpoint and
`as_of`, ordered immutable attempt-record evidence, selected attempt identity,
selected snapshot evidence, selection policy, and chronology result. It is
terminal-specific: changing the authoritative head or terminal changes the
selection identity.

The caller-idempotency key binds the session, exact head, verified lineage,
terminal, selection record and snapshot, cycle request/configuration, target
authority, approved release, and optional approval artifact. This UUID is the
value intended for the existing paper-operation
`caller_idempotency_key`. Re-reading the same approval cannot randomize it;
changed target, configuration, release, terminal, or snapshot evidence creates
a different key.

## Explicit market-hours authority

`MarketSessionHoursSchedule` is a strict, versioned XNYS input contract. It
contains a coverage interval, ordered open-session entries, explicit
exceptional closures, and exact authority-artifact evidence. Each open entry
contains UTC open/close instants and an explicit `REGULAR` or `EARLY_CLOSE`
kind.

Validation requires the exact supported XNYS descriptor, chronological unique
entries, complete coverage of every session date modeled by the existing
calendar, and an exact partition between open entries and exceptional closures.
Regular entries must map to 09:30–16:00 America/New_York; early-close entries
must map to 09:30–13:00. Missing, duplicate, out-of-order, non-session, and
ambiguous closure inputs fail.

The existing calendar supplies deterministic session dates only. It is not the
official market-hours authority and does not decide early closes or
extraordinary closures. Producing, approving, updating, and distributing an
official schedule artifact remains a separate operational authority decision.
This milestone neither fetches nor generates one.

## Capture policy and terminal attempt records

The capture policy explicitly fixes:

- publication delay after target close;
- cutoff guard before execution open;
- maximum attempts and every fixed retry backoff;
- maximum clock skew and acceptable capture lateness;
- exact ordered universe, provider, feed, timeframe, adjustment, and currency;
- policy version and exact configuration evidence.

Schema-1 terminal attempt records are immutable canonical artifacts. A `PASS`
record must carry complete verified snapshot evidence. `REJECTED` and `FAILED`
records carry no snapshot and retain one terminal code. Attempt history is
caller ordered and ordinals must be contiguous from zero. Conflicting ordinal
or attempt identities are not repaired or sorted.

## Terminal-specific snapshot selection

The evaluator consumes the explicit attempt history. An eligible snapshot must:

- originate from the exact scheduled session and capture policy;
- be a complete verification pass;
- match target D and the exact ordered universe;
- match provider, feed, timeframe, adjustment, and currency;
- satisfy `terminal as_of <= captured_at`;
- not exceed the explicit observed time plus clock skew;
- not exceed target close plus maximum acceptable lateness.

The normal deterministic selection is the lowest eligible attempt ordinal and
must be represented by an exact canonical selection record. Later eligible
retry ordinals do not replace that lowest eligible record. No filename, UUID
ordering, modification time, capture timestamp alone, or directory order
participates. Duplicate records for one ordinal, conflicting attempt records,
or a mismatched selection record fail closed as conflicts.

Capture-window states distinguish too early, open, expired, no attempts,
backoff active, and attempts exhausted. Snapshot states distinguish target,
universe, provider-policy, completeness, terminal chronology, future skew,
staleness, duplicate eligibility, and selection mismatches.

## Readiness input and operation gates

`ScheduledReadinessInputs` is frozen explicit material containing:

- normalized evidence from a completely verified authoritative local head;
- target D, execution E, and explicit observation time;
- the market-hours schedule and capture policy;
- ordered terminal attempt records, optional selected snapshot and selection;
- optional exact cycle, target, release, and approval evidence;
- manual-disable and pending-head-advancement state;
- explicit disk, audit, notification, backup, and credential-isolation health;
- normalized existing paper-operation inspection evidence;
- explicit staging, failed-receipt, and transition-without-receipt state.

The narrow CLI adapters accept the existing
`VerifiedAuthoritativeLineageHead` and `PaperOperationInspectionResult` public
types and normalize their exact immutable evidence. The pure evaluator itself
does not reopen their files.

`READY` requires all scheduled identities to reconcile, head and terminal
binding, no unrepresented successor, manual enablement, explicit hours,
terminal-specific selected snapshot, exact cycle and target evidence, approved
release and required approval, absence of operation credentials, passing health
gates, chronology
`terminal as_of <= captured_at <= planning <= submitted <= filled`, a fill
inside execution-session hours, and coordinator `PENDING`.

Coordinator `PENDING` is only one gate and never establishes readiness by
itself. A verified transition without a receipt or head advancement, a valid
failed receipt, or crash-left staging requires manual review. Completed state
requires verified completed receipt and transition evidence plus an explicitly
advanced authoritative head.

## Classification precedence

The exact precedence is:

```text
CONFLICTING
→ MANUAL_REVIEW_REQUIRED
→ BLOCKED
→ ALREADY_COMPLETED
→ NOT_READY
→ READY
```

Diagnostics are unique and emitted in enum declaration order, independent of
the order in which gates are evaluated.

## Serialization

Terminal attempt and snapshot-selection records use strict schema 1, compact
sorted ASCII JSON, and exactly one final newline. Parsing rejects BOMs, invalid
UTF-8, duplicate/unknown/missing fields, floats, nonstandard constants,
noncanonical UUID/hash/date/timestamp text, unbounded collections and integers,
and bytes that differ from canonical reserialization.

No readiness decision is published in this milestone. The immutable result is
held in memory for a later dry-run runner; adding a persistent decision artifact
requires a separate publication decision.

## Deferred operational decisions

Capture-only unattended operation remains the recommended next boundary.
Target approval semantics, notification delivery authority, backup
requirements, official hours maintenance, Windows single-writer locking,
credential injection, retries, scheduler integration, and retention/recovery
remain unresolved and separately gated.
