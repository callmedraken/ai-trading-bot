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

## Milestone-3 one-shot transition execution

Milestone 3 adds an explicit `--execute-once` mode. Execution is admitted only
after the milestone-2 inspection result is exactly `PENDING`, the operation-root
identity remains stable, and the exact transition final and staging names remain
unoccupied. Every other inspection classification returns without invoking the
runtime.

An admitted invocation calls
`execute_checkpointed_verified_snapshot_paper_cycle` exactly once. It never
retries a domain rejection, exception, verification failure, or filesystem
failure. The normalized caller-authored request, verified terminal authority,
and completed snapshot verification are passed directly to that existing
runtime.

The pre-commit order is fixed:

1. execute exactly one private paper cycle;
2. canonicalize its checkpointed-cycle report;
3. create and canonicalize its successor checkpoint;
4. verify the prospective successor edge using the fully verified prior;
5. append exactly the new report, successor checkpoint, and current snapshot to
   the caller-provided prior artifacts;
6. verify the complete prospective lineage with the successor as terminal;
7. exclusively create the sibling transition staging directory;
8. write and flush the exact two files;
9. safely reread the staged bytes and repeat edge and full-lineage verification;
10. no-clobber rename the staging directory within the same parent;
11. safely reread the finalized bytes and repeat edge and full-lineage
    verification;
12. return `TRANSITION_COMMITTED`.

The finalized transition directory is the authoritative paper-account commit
point. It cannot become visible before prospective and staged verification both
pass. `APPLIED` and `NO_ACTION` are successful outcomes; both commit a successor
checkpoint because the compact ledger `as_of` advances.

The milestone-3 commit path deliberately preserves invocation-created staging
after any interrupted or failed staging phase. It never deletes, repairs,
overwrites, merges, or automatically retries crash-left work. A verification
failure after rename reports blocked state while preserving the already
authoritative finalized transition.

Milestone 3 creates no operation directory and no receipt. Consequently, at
that milestone boundary a later invocation that found the exact verified
finalized transition but no receipt remained `BLOCKED` with
`FINALIZED_TRANSITION_WITHOUT_RECEIPT`.

## Milestone-4 receipt commitment and recovery

Milestone 4 preserves the finalized transition directory as the authoritative
paper-account state commit point. It adds a second, operation-level audit
commitment: the immutable schema-1 `COMPLETED` receipt. The receipt is stored
separately from the transition because the transition is identified by the
existing application UUID and remains reusable account-lineage evidence,
whereas the receipt is identified by the operation UUID and retains caller
idempotency and complete operation intent.

Normal completion has this fixed order:

1. complete every milestone-3 prospective, staged, and finalized transition
   verification;
2. construct the canonical receipt from the exact intent, verified prior and
   successor lineage, report, successor checkpoint, application, result, and
   outcome;
3. run the milestone-1 offline verifier against the in-memory receipt bytes and
   all exact dependencies;
4. exclusively create receipt staging and write its one canonical file;
5. bounded-reread and fully offline-verify the staged receipt;
6. no-clobber rename staging to the final operation directory in the same
   `paper-operations` parent;
7. bounded-reread and fully offline-verify the finalized receipt;
8. return `COMPLETED`.

`APPLIED` and `NO_ACTION` receipts use the unchanged milestone-1 schema. The
receipt UUID equals the operation UUID, status is `COMPLETED`, outcome exactly
matches the verified cycle result, and diagnostic code is `NONE`. No clock,
path, mutable status, or diagnostic prose enters canonical evidence.

The fixed layout is:

```text
<operation-root>/
  paper-account-transition-<application-id>/
  paper-operations/
    paper-operation-<operation-id>/
      paper-operation-receipt-<operation-id>.json
```

Receipt staging is the sibling
`.paper-operation-<operation-id>.staging`. The `paper-operations` parent is
created only by the receipt output helper after verifying the retained
operation-root identity and rejecting bounded case-fold collisions. Staging is
exclusive and contains exactly one file. The helper flushes canonical bytes,
uses bounded safe rereads, retains parent and directory identities, rejects
links and reparse points, and finalizes by same-parent no-clobber rename. It
never deletes, repairs, replaces, merges, or resumes staging.

A process may stop after transition finalization but before receipt
finalization. A later exact invocation may recover only when read-only
inspection establishes one verified finalized requested transition, no
finalized receipt, no receipt staging, and no ambiguous or conflicting state.
Recovery safely rereads the fixed transition, proves the predecessor, snapshot,
request, application, result, report, successor edge, and complete successor
lineage, reconstructs the same canonical receipt, and performs the same
in-memory, staged, and finalized milestone-1 verification. It invokes the
paper-cycle runtime zero times and returns `RECEIPT_RECOVERED`.

An exact verified finalized receipt returns `ALREADY_APPLIED` with zero runtime
calls and zero writes. A receipt staging directory blocks both execution and
recovery and is preserved for manual review. A receipt without its matching
verified transition, a noncanonical or altered receipt, an invalid transition,
or a dependency mismatch remains blocked and is never overwritten. Milestone 4
does not produce `FAILED` receipts and does not retry failed runtime execution.

## Deferred coordinator work

Schedulers, services, loops, polling, databases, distributed locks, multi-host
coordination, provider capture, external paper accounts, and real-money
execution remain outside this design. Before unattended scheduling, the system
still needs an explicit scheduling policy, single-writer ownership and stale
invocation rules, bounded dependency retention, alerting and manual-review
procedures, credential/provider boundaries, and a decision on stronger global
caller-key authority. Schema-1 receipt-only directories still cannot establish
complete global caller-key reuse when foreign dependencies are unavailable.
