# Architecture 104 — Personal-Desktop Supervised Paper Execution Boundary

Status: accepted design for PD2C source implementation.

## Purpose

PD2B proves that the system can prepare one exact Architecture-67 paper operation from genuine authority, a genuine selected C3 snapshot, and freshly reread post-lock Paper-v2 account state without exposing caller-selected filesystem authority.

PD2C defines the next boundary: consume that already-prepared operation while the same account mutex is still held and route it to the existing Architecture-67 execute-once machinery without giving callers a raw production operation root or raw execution-input capability.

PD2C begins source-only. This architecture does not authorize a real mutation of `F:\AITradingBot\Paper-v2\runtime`.

## Fixed production facts

```text
Paper-v2 root:       F:\AITradingBot\Paper-v2
A67 operation root:  F:\AITradingBot\Paper-v2\runtime
receipt parent:      F:\AITradingBot\Paper-v2\runtime\paper-operations
```

The production effect gates remain source-owned:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED   = False
```

PD2C source certification must leave both false.

## Authority composition

The production-facing execution boundary must have this shape:

```text
genuine ValidatedProductionAuthority
+ genuine SelectedC3SnapshotReadResult
+ pure planning inputs
-> enter PD2B3 supervised preparation
   -> genuine P2 provenance revalidated
   -> PD2B1 enters PD2A account mutex
   -> post-lock Paper-v2 reread
   -> P1 build + exact replay verification
   -> private active A67 binding
-> PD2C validates active preparation provenance
-> PD2C consumes the private binding while the same mutex is still held
-> source-owned fixed production root only
-> production-effect admission gate
-> Architecture-67 execute-once
-> durable terminal result
-> private binding expires
-> account mutex releases
```

A caller may never mint PD2C authority from an arbitrary UUID, path, operation root, `VerifiedPaperOperationExecutionInputs`, `PaperOperationIntent`, prebuilt preparation binding, native handle, timeout, or copied audit evidence.

## Same-scope requirement

The Architecture-67 call, when eventually enabled, must happen before PD2B3 exits. The private prepared binding is process-local and valid only during the exact active PD2B3 scope.

PD2C must not detach or serialize that binding for later use. It must not return a reusable object that contains both the production operation root and raw A67 inputs.

## Production root authority

The generic Architecture-67 coordinator intentionally accepts an explicit operation root for manual/disposable use. PD2C must not expose that flexibility to production.

For production composition, the root must reconcile exactly to:

```text
F:\AITradingBot\Paper-v2\runtime
```

It must come from the genuine post-lock Paper-v2 authority already retained inside PD2B3, not from a caller argument or environment variable.

A mismatching root fails closed before Architecture-67 execution.

## Effect gate

PD2C must introduce or reuse a narrow source-owned production execution gate such that:

- when the gate is `False`, the production-facing execution entry point fails closed before calling Architecture 67;
- tests can exercise the composition through an explicitly disposable/injected executor seam without changing the production gate;
- caller input cannot override, shadow, monkey-select, or configure the production gate;
- enabling the production gate is a later explicitly reviewed source checkpoint and is not part of PD2C source implementation.

PD2C must not flip either existing Paper-v2 production/recovery gate to `True`.

## Architecture-67 semantics retained

PD2C must preserve the existing Architecture-67 execute-once contract rather than reimplementing it:

- inspect/classify exact operation state before runtime;
- deterministic idempotency and conflicting-state blocking;
- no blind runtime retry;
- prospective successor edge/full-lineage verification;
- staged transition reread/verification;
- finalized transition reread/verification;
- finalized transition is the authoritative account-state commit point;
- receipt commitment follows transition commitment;
- deterministic failed receipts for eligible runtime failures;
- existing zero-runtime receipt recovery only where Architecture 67 proves the exact already-applied transition;
- invalid, ambiguous, staging, or mismatched state fails closed.

PD2C must call the existing `execute_paper_operation_once` boundary rather than duplicate its transition/receipt algorithms.

## Abandoned ownership

Ordinary PD2C execution is not permitted after `ABANDONED_OWNER`.

PD2B3 already fails before preparation in that state. PD2C must preserve that boundary and must not add a bypass or implicit recovery mode.

Crash/restart reconciliation of abandoned ownership and durable receipt gaps belongs to PD3 unless a separately reviewed recovery checkpoint is authorized earlier.

## Result surface

PD2C may expose a small immutable supervised execution result containing safe audit/result facts already returned by Architecture 67, for example:

- operation ID;
- application ID;
- classification;
- diagnostic code;
- cycle result ID when present;
- successor checkpoint ID when present;
- transition/receipt completion classification;
- whether any production executor call was performed.

The result must not itself grant authority for a second execution.

## Failure and cleanup

Any failure before Architecture-67 invocation must perform zero paper mutation and unwind the PD2B3/PD2A scope normally.

If the executor raises or returns a fail-closed Architecture-67 result, PD2C must still unwind through the existing context stack. It must not retry the runtime in the same call.

If mutex release later fails, the existing PD2A process-lifetime poison behavior remains authoritative.

## No new external effects

PD2C does not authorize or introduce:

```text
provider call #7
broker submission
live trading
unattended scheduling
credential mutation
account/group/password mutation
LSA policy/right mutation
KSP/signing/private-export mutation
```

## Source-only certification rule

PD2C implementation tests use fake/disposable roots and injected Architecture-67 executors. They must not open the real production account mutex, read/write the production Paper-v2 tree, perform a provider call, contact a broker, or schedule unattended work.

Only after PD2C source review and broad certification may a later checkpoint design production-effect qualification. The first real Paper-v2 mutation still requires explicit user authorization.
