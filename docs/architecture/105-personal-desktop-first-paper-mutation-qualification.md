# Architecture 105 — Personal-Desktop First Paper Mutation Qualification

Status: accepted design for PD2D1 source implementation.

## Purpose

PD2C proves that one genuine supervised Paper-v2 operation can be routed to the
existing Architecture-67 execute-once boundary while preserving the same
account-mutex lifetime, fixed production root, result reconciliation, and
fail-closed gate semantics.

PD2D1 is the final **non-mutating** checkpoint before any source gate enablement
or first durable Paper-v2 write. It answers:

> Given the exact current genuine authority, selected C3 snapshot, post-lock
> Paper-v2 state, and deterministic planning inputs, does the existing read-only
> Architecture-67 inspector classify the exact would-be operation as clean
> `PENDING`?

PD2D1 does not execute a paper cycle. It does not create, rename, write, delete,
or repair a Paper-v2 object. It does not change the PD2C execution gate.

## Fixed production facts

```text
Paper-v2 root:       F:\AITradingBot\Paper-v2
A67 operation root:  F:\AITradingBot\Paper-v2\runtime
receipt parent:      F:\AITradingBot\Paper-v2\runtime\paper-operations
```

All effect gates remain false throughout PD2D1 source implementation and
qualification:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

PD2D1 must itself fail closed if the supervised-execution gate is already true;
qualification is a pre-enable activity, not an alternate execution path.

## Authority composition

The production-facing qualification boundary has this shape:

```text
genuine ValidatedProductionAuthority
+ genuine SelectedC3SnapshotReadResult
+ pure deterministic planning inputs
-> require PD2C supervised-execution gate is still False
-> enter PD2B3 supervised preparation
   -> genuine P2 provenance reconciled to exact C1
   -> PD2B1 enters PD2A account mutex
   -> genuine post-lock Paper-v2 reread/revalidation
   -> P1 build + exact replay verification
   -> private active A67 binding
-> consume private binding while same mutex is still held
-> require exact source-owned F:\AITradingBot\Paper-v2\runtime root
-> call existing inspect_paper_operation_root only
-> reconcile inspection identities to active prepared operation
-> map exact PENDING/PENDING to READY; all other valid classifications NOT_READY
-> private binding expires
-> mutex releases
```

The caller may never mint qualification authority from an arbitrary path, raw
A67 inputs, prebuilt preparation, paper-account ID, lineage/prior, operation ID,
application ID, terminal checkpoint ID, mutex name, Trading SID, native handle,
timeout, inspector override, or readiness override.

## Read-only inspection contract

PD2D1 must use the existing:

```text
inspect_paper_operation_root(operation_root, inputs)
```

It must not duplicate Architecture-67 inspection logic.

The production-facing path must not import or call:

```text
execute_paper_operation_once
commit_transition_directory
commit_paper_operation_receipt
preflight/commit writer helpers used to mutate the operation root
```

The private focused-test seam may inject a fake inspector, but it must not be a
caller-selectable production argument and must require an explicit private/test
issuer barrier.

## Qualification result

Use a small immutable non-authorizing result. Safe fields may include:

- paper account ID;
- selected snapshot ID;
- plan ID;
- operation ID;
- application ID;
- terminal checkpoint ID;
- inspection classification;
- inspection diagnostic code;
- qualification status `READY` or `NOT_READY`;
- `inspector_called=True`.

The result must not expose:

- operation root or any `Path`;
- raw `VerifiedPaperOperationExecutionInputs`;
- PD2B3 preparation or private binding;
- receipt/transition path;
- a callable execution method;
- any token that can later bypass the PD2C gate.

The result is evidence only. It is never durable execution authority and is not
consumed by PD2C to skip revalidation.

## Identity reconciliation

Before returning qualification evidence, require the exact
`PaperOperationInspectionResult` type and reconcile:

```text
inspection.operation_id == active.operation_id
inspection.application_id == active.application_id
inspection.terminal_checkpoint_id ==
    active prepared execution inputs' verified prior checkpoint ID
```

Any wrong type or identity mismatch fails closed while still unwinding the
PD2B3/PD2A scope.

## READY rule

Only this exact inspection is READY:

```text
classification = PaperOperationClassification.PENDING
diagnostics     = (PaperOperationInspectionCode.PENDING,)
```

Every other valid A67 inspection result is `NOT_READY` and is preserved as
non-authorizing diagnostic evidence. This includes:

```text
ALREADY_APPLIED
CONFLICTING
BLOCKED
VALID_FAILED_RECEIPT
STALE_TERMINAL_CHECKPOINT
FINALIZED_TRANSITION_WITHOUT_RECEIPT
OPERATION_STAGING_EXISTS
TRANSITION_STAGING_EXISTS
INVALID/UNSAFE/AMBIGUOUS states
```

Qualification must not repair, delete, rename, retry, recover, or reinterpret
these states into permission to execute.

## Same-scope requirement

The inspector must run while the exact PD2B3 preparation is active and while the
same PD2A account mutex remains held. The private binding must not be detached,
serialized, cached for later, or returned.

Normal return, `NOT_READY`, inspector exception, wrong return type, or identity
mismatch all unwind through the existing PD2B3 context. PD2A release-failure
process poisoning remains authoritative.

`ABANDONED_OWNER` remains blocked by PD2B3 before the inspector is called.
PD2D1 does not add abandoned-owner or receipt-gap recovery.

## Real-host qualification phase

After source review and broad certification, PD2D1 may be exercised once on the
intended Windows host under the dedicated non-elevated `Trading` account.

That real-host run may perform only the already-reviewed **read-only** effects
required by C1/P2/PD2B3 and A67 inspection:

- acquire/release the account mutex;
- read/pin/revalidate fixed Paper-v2 objects;
- read selected C3 evidence through the existing P2 authority;
- inspect the exact fixed A67 operation root.

It must not:

- enable the PD2C execution gate;
- call the A67 executor;
- create staging/final transition or receipt objects;
- mutate Paper-v2;
- perform provider call #7;
- contact a broker;
- schedule unattended work;
- modify credentials, accounts, groups, ACLs, LSA policy, KSP state, or signing material.

Real-host qualification evidence is point-in-time, non-authorizing evidence.
PD2D2 must revalidate genuine state from scratch before any future execution.

## Relationship to the first real mutation

PD2D1 completion does not authorize PD2D2.

The first real mutation requires a separate explicit checkpoint that at minimum
reviews:

1. the exact source change that enables the dedicated PD2C supervised-execution
   gate;
2. the exact intended idempotency UUID and pure planning inputs;
3. current real-host PD2D1 READY evidence;
4. one-shot invocation commands under the dedicated `Trading` account;
5. expected durable transition/receipt identities and post-run readback;
6. crash/interruption instructions that forbid blind rerun;
7. fresh explicit user authorization immediately before enabling or executing.

No automatic workflow may cross that boundary.
