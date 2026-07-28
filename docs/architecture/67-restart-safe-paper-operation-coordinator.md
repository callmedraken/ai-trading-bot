# Restart-safe paper-operation coordinator

## Milestone-1 boundary

Milestone 1 defines only immutable paper-operation intent and terminal receipt
evidence. It adds deterministic operation identity, strict canonical receipt
serialization and parsing, and a pure offline receipt verifier.

It does not add a command, operation-root inspection, filesystem enumeration,
staging, directory finalization, transition execution orchestration, receipt
recovery, scheduling, provider access, broker access, network access, or a
background process.

## Immutable operation intent

`PaperOperationIntent` retains schema version 1, the caller's canonical
idempotency UUID, complete verified prior-lineage evidence, the exact terminal
checkpoint artifact evidence, completed daily-snapshot artifact evidence, exact
cycle-configuration SHA-256 and byte length, and the normalized existing
`CheckpointedVerifiedSnapshotPaperCycleRequest`.

Filesystem paths are transport metadata outside the model. They are not
retained in identity material and cannot change the operation ID.

The operation UUID5 uses namespace
`f4cb58e5-bb4a-5dad-8a12-951679933b77` and byte-length-framed material version
`paper-operation-identity-v1`. Its ordered material is:

1. material version;
2. caller idempotency UUID;
3. prior-lineage evidence UUID;
4. terminal checkpoint artifact kind, domain UUID, SHA-256, and byte length;
5. completed snapshot artifact kind, domain UUID, SHA-256, and byte length;
6. the complete canonical normalized checkpointed-cycle request;
7. exact cycle-configuration SHA-256 and byte length.

The request is canonicalized with the same request tree and scalar conventions
used by checkpointed-cycle reports. Identity uses no clock, path, serialized
receipt bytes, environment value, Python hash, object identity, provider state,
or mutable service.

Caller idempotency-key reuse is not registered in mutable state. A later
coordinator milestone will detect reuse by bounded safe inspection of immutable
finalized receipts.

## Terminal receipt semantics

`PaperOperationReceipt` is frozen, slotted, schema version 1, and has a receipt
ID exactly equal to its operation ID.

A `COMPLETED` receipt has exactly one outcome:

- `APPLIED`, when the verified checkpointed cycle applied at least one fill;
- `NO_ACTION`, when the verified cycle produced the established successful
  no-action result and successor checkpoint.

Both completed outcomes retain the exact prior and successor lineage evidence,
transition report and successor checkpoint artifact evidence, application UUID,
and cycle-result UUID. `NO_ACTION` remains a committed successor edge because
the final compact-state `as_of` advances under the existing cycle contract.

A `FAILED` receipt retains the prior lineage, derived application UUID, and one
stable diagnostic code. It retains no outcome, successor lineage, report,
successor checkpoint, or cycle-result UUID. It is valid only when pure replay
of the exact operation reproduces the same recognized deterministic
domain/execution failure.

A failed receipt must never classify permission denial, dependency reads,
filesystem or disk failures, unsafe paths, staging conflicts, interrupted
writes, process interruption, provider behavior, broker behavior, or scheduling
state. Those conditions remain incomplete or blocked coordinator state and are
not terminal domain receipts.

Diagnostic prose is excluded from canonical receipt evidence.

## Canonical encoding

Receipts use one strict UTF-8 JSON representation:

- sorted keys and compact separators;
- `ensure_ascii=True`;
- exactly one final newline;
- canonical lowercase UUID and SHA-256 text;
- canonical UTC timestamp and context-independent Decimal text;
- explicit bounds on total bytes, arrays, strings, integers, and Decimals;
- no floats or non-finite JSON constants;
- rejection of BOMs, duplicate keys, missing or unknown fields, trailing data,
  and noncanonical reserialization.

The receipt embeds normalized operation intent, including the complete request
and prior-lineage evidence. It can therefore recompute identity without the
original transport paths. The exact caller-authored cycle-configuration bytes
remain an explicit verifier dependency and must match retained SHA-256 and byte
length.

## Pure offline verification

`verify_paper_operation_receipt` receives receipt bytes, cycle-configuration
bytes, explicit prior-lineage artifacts, completed snapshot bytes, an identified
calendar, and, for completed receipts, exact report and successor checkpoint
bytes.

Verification:

1. checks optional outer receipt evidence;
2. strictly parses and canonically reserializes the receipt;
3. reconstructs intent and recomputes its operation UUID;
4. checks exact cycle-configuration artifact evidence;
5. runs existing full prior-lineage verification and requires exact retained
   evidence;
6. requires the terminal checkpoint artifact to be the verified terminal;
7. runs existing completed-snapshot verification and requires exact evidence;
8. recomputes the application UUID;
9. for `FAILED`, replays once and requires the exact recognized deterministic
   failure code;
10. for `COMPLETED`, runs the existing successor-edge verifier, reconciles
    application, result, request, report, checkpoint, and outcome evidence;
11. appends the explicit new artifacts to the supplied prior artifacts, runs
    existing full-lineage verification to the successor, and requires exact
    retained successor-lineage evidence.

PASS exposes the immutable receipt. FAIL exposes no receipt authority and only
one stable verification code. The verifier performs no discovery, filesystem
output, network, provider, broker, scheduler, clock, or environment access.

## Pre-commit successor-lineage invariant

Future execution integration must construct the prospective report and
successor checkpoint entirely before account-state commit. It must verify the
prospective successor edge and the complete resulting successor lineage before
transition-directory finalization.

Transition-directory finalization is the account-state commit point. A receipt
may be finalized only after that committed transition is reread and continues
to verify. This ordering prevents a transition directory from committing an
edge that was never proven to extend the verified prior lineage.

## Milestone-2 read-only inspection

Milestone 2 adds strict schema-1 operation configuration loading and a manually
invoked, read-only inspection command. The configuration names the caller
idempotency UUID and explicit prior-lineage manifest, terminal checkpoint,
completed snapshot, and cycle-configuration artifacts. Each artifact reference
contains its domain UUID, lowercase SHA-256, byte length, and a transport-only
path. The operation root remains a separate CLI input.

Inspection verifies the complete prior lineage, requires the configured
checkpoint to be its terminal artifact, verifies the completed snapshot, parses
the existing checkpoint-transition request, requires its snapshot reference to
match, and derives the established operation and application identities without
executing the cycle.

The operation root is inspected with bounded enumeration and fixed layouts.
Recognized transition directories are parsed and, when relevant to the requested
predecessor, verified through the existing successor-edge API. Receipt authority
always requires the milestone-1 offline receipt verifier. Unsafe links, reparse
points, changed parent identities, case-fold collisions, unexpected recognized
layout contents, staging, and ambiguous state fail closed.

Schema-1 receipt-only operation directories do not contain enough dependencies
to perform complete global caller-key reuse verification. Canonical parsing of a
foreign receipt is not authority. A foreign same-key receipt may establish a
conflict only when all exact milestone-1 verifier dependencies are available and
the full offline verification passes. If its lineage, snapshot, cycle
configuration, report, successor checkpoint, or another required dependency is
unavailable, inspection returns `BLOCKED` with
`FOREIGN_RECEIPT_DEPENDENCIES_UNAVAILABLE`; it does not return `CONFLICTING`,
skip the receipt, or infer authority from names or retained hash claims.

A future receipt schema, immutable dependency bundle, or authoritative operation
registry could provide complete conflict discovery. Milestone 2 intentionally
introduces none of those mechanisms and does not alter the milestone-1 receipt
schema.

## Deferred coordinator work

Later milestones may add the manually invoked one-shot execution coordinator,
no-clobber transition and receipt staging/finalization, restart inspection, and
receipt recovery after an already committed verified transition.

Schedulers, services, loops, polling, databases, distributed locks, multi-host
coordination, provider capture, external paper accounts, and real-money
execution remain outside this design.
