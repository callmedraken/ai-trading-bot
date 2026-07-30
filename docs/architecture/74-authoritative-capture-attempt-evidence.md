# Authoritative capture-attempt evidence

The first provider prerequisite milestone publishes authority only. It does
not create a process, access a secret, contact Alpaca, capture a snapshot,
retry, schedule, or advance paper-operation lineage.

## Allocation and history

`CaptureAttemptAllocationRecord` schema 1 binds the exact existing guarded
readiness decision, session/launch/epoch, head and terminal evidence, policy
and configuration references, ordered universe, provider descriptor, and the
existing deterministic scheduled attempt ID. The allocation consumes the
proposed ordinal immediately and fixes `provider_call_budget=1`. Paths are
transport metadata and are excluded from identity. Allocation is accepted only
from an exact `READY`/`CAPTURE_ATTEMPT_ALLOWED` decision with provider
invocation permission.

Each session has the fixed layout:

```
<root>/<scheduled-session-id>/
  history-head-records/ allocations/ terminals/ zero-call-proofs/
  recovery-records/ current-attempt-history.json
```

Immutable schema-1 history heads form an explicit predecessor chain. The one
mutable pointer is authoritative; verification follows only that pointer and
named predecessor/evidence references. It never scans directories, picks the
highest ordinal, counts files, or repairs a pointer. Genesis is generation
zero, `EMPTY`, next ordinal zero. Allocation advances to
`ALLOCATED_NOT_LAUNCHED` and increments the ordinal before any possible
provider call. The closed state machine is `EMPTY`,
`ALLOCATED_NOT_LAUNCHED`, `LAUNCH_MAY_HAVE_OCCURRED`, `TERMINAL_SELECTED`,
`RECOVERY_REQUIRED`, `SUCCESS_SELECTED`, and `SESSION_CLOSED`.

## Terminal, proof, and recovery facts

Schema-2 terminal evidence preserves the schema-1 parser and bytes while
adding exact allocation, child/credential/process evidence, provider-call
disposition, explicit completion time, terminal classification, diagnostics,
exit/timeout evidence, optional snapshot, verification, cleanup, and policy.
`SUCCEEDED` requires a verified snapshot and confirmed response; ambiguous
timeouts cannot claim `NOT_STARTED`; failed terminals cannot claim an accepted
snapshot. A terminal is historical fact, not retry authorization.

`ZeroProviderCallProof` is a closed, evidence-backed schema-1 artifact. Each of
its five classifications requires the corresponding launch, resume, adapter,
transport, and exit evidence. Timeout, termination, missing snapshot, or a
caller boolean is never proof. `ManualCaptureAttemptRecoveryRecord` is
immutable operator authorization for only the listed recovery actions and is
published without provider access. It never silently repairs the pointer.

Retry/escalation is a pure classifier over supplied state, terminal facts,
proof, policy, deadline, attempts, and explicit approval. It reads no clock,
sleeps, loops, calls a provider, or rewrites history.

## Publication boundary

Artifacts use same-directory exclusive staging, flush/fsync, canonical reread,
and no-clobber finalization. Pointer replacement uses the approved Windows
`MoveFileExW` write-through compare-and-swap approach. A stale pointer or
replacement failure retains immutable artifacts and leaves the old pointer
authoritative. The module assumes the caller already holds the wider launch
guard; it is intentionally lock-unaware.
