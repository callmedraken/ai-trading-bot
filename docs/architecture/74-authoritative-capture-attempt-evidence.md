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

Immutable history heads form an explicit predecessor chain. Legacy heads that
do not select a success remain schema 1; schema 2 heads are used when a success
selection is published and add `latest_selection` evidence. The one mutable
pointer is authoritative; verification follows only that pointer and named
predecessor/evidence references. It never scans directories, picks the
highest ordinal, counts files, or repairs a pointer. Genesis is generation
zero, `EMPTY`, next ordinal zero. Allocation advances to
`ALLOCATED_NOT_LAUNCHED` and increments the ordinal before any possible
provider call. The closed state machine is `EMPTY`,
`ALLOCATED_NOT_LAUNCHED`, `LAUNCH_MAY_HAVE_OCCURRED`, `TERMINAL_SELECTED`,
`RECOVERY_REQUIRED`, `SUCCESS_SELECTED`, and `SESSION_CLOSED`.

The predecessor transition matrix is authoritative: `EMPTY` may allocate;
`ALLOCATED_NOT_LAUNCHED` may continue with verified zero-call proof, publish an
ambiguous or selected terminal, or close; `LAUNCH_MAY_HAVE_OCCURRED` may enter
review or close; `TERMINAL_SELECTED` may retry allocation only when its
predecessor terminal is neither successful nor ambiguous, perform an explicit
terminal-selection recovery, select success, or close; and
`RECOVERY_REQUIRED` may be reviewed again or close. It cannot recover a
committed success because its terminal is already ambiguous; committed-success
recovery is permitted only from a verified successful `TERMINAL_SELECTED`
state. `SUCCESS_SELECTED` and `SESSION_CLOSED` have no outgoing transitions.
Disk verification applies the same matrix and evidence rules as publication:
allocation records name the exact predecessor head and next ordinal;
continuation recovery names the current allocation and current parsed,
structurally verified zero-call proof; terminal-selection recovery names the
current allocation and verified successful terminal; and every manual recovery
head binds its action to the predecessor state, resulting state, and required
evidence. A structurally canonical but impossible predecessor transition is
conflicting history.

Schema-1 heads derive identity with material version
`capture-attempt-history-head-v1`; schema-2 heads derive identity with the
explicit material version `capture-attempt-history-head-v2`. The schema-1
version and field set remain byte-compatible. A legacy schema-1
`SUCCESS_SELECTED` head without selection evidence is accepted only after its
canonical bytes and UUID5 identity validate, then rejected with the dedicated
compatibility diagnostic
`LEGACY_SUCCESS_SELECTED_REQUIRES_MIGRATION`; pointer verification exposes
that diagnostic as `MANUAL_REVIEW_REQUIRED` when it is directly pointer
selected. If a newer head names that legacy success as its predecessor, the
history is `CONFLICTING` because completed history has an outgoing transition.
Malformed, noncanonical, identity-invalid, or evidence-mismatched legacy
artifacts are conflicting. Nothing is migrated, rewritten, or repaired.

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
sleeps, loops, calls a provider, or rewrites history. A restarted
`TERMINAL_SELECTED` non-success terminal must pass this classifier before
readiness can authorize another allocation; readiness backoff is not retry
authorization. Ambiguous classifications are centralized across terminal
publication, runner reporting, and retry policy.

## Publication boundary

Artifacts use same-directory exclusive staging, flush/fsync, canonical reread,
and no-clobber finalization. Pointer replacement uses the approved Windows
`MoveFileExW` write-through compare-and-swap approach. A stale pointer or
replacement failure retains immutable artifacts and leaves the old pointer
authoritative. The module assumes the caller already holds the wider launch
guard; it is intentionally lock-unaware.

After each immutable artifact required by a transition is published, the
writer validates the candidate head with the same named-artifact, state/cause,
and transition-evidence contract used by restart verification before
publishing the head or replacing the pointer. Terminal transitions reconcile
allocation identity, terminal fields, policy, ordinal, and centralized
ambiguity state. A later non-continuation recovery preserves the predecessor's
verified zero-call proof, including session closure.

Success selection has a fixed publication chain: publish and verify the
immutable terminal-selection artifact under `terminals/`, publish a schema-2
history head whose `latest_selection` contains that artifact's identity,
SHA-256, byte length, and terminal/allocation linkage, then atomically advance
the history pointer. History verification rereads only the pointer-selected
head's named selection artifact and fails closed on deletion, replacement,
modified bytes, identity mismatch, or linkage mismatch. If a crash occurs
after selection or head publication but before pointer replacement, the old
pointer remains authoritative and the immutable partial artifacts are retained
for a later explicit retry of publication; no repair or directory scan occurs.

Manual `RECOVER_COMMITTED_SNAPSHOT_AS_SUCCESS` uses the separate validated
selection policy `capture-recovery-selection-v1`. It never copies
`recovery_policy_version` into `selection_policy_version`; the selection
artifact and its canonical identity bind the recovery-selection policy
explicitly.

`select_capture_attempt_terminal` accepts only a pointer-selected
`TERMINAL_SELECTED` head. A schema-2 `SUCCESS_SELECTED` head is valid only with
`TERMINAL_SELECTION` plus matching selection-policy evidence, or
`MANUAL_RECOVERY` plus the current recovery record, committed terminal,
allocation, snapshot, and `capture-recovery-selection-v1` evidence. Neither
success nor session closure can be reopened, reselected, recovered, or
allocated.

## Milestone-75 implementation clarification

The manual isolated child consumes exactly one already-published allocation
record and its `provider_call_budget=1`. It reconciles that allocation with the
child request, credential reference, capture configuration, snapshot request,
target session/date, universe, provider policy, destination, and release
evidence before credential access.

The new child result and process creation/resume/termination records provide
the concrete evidence slots anticipated by schema-2 terminal and zero-call
proof construction. They are not automatically inserted into attempt history,
selected as a terminal, used to select a snapshot, or interpreted as retry
authority. A resumed timeout or termination remains ambiguous and is never a
zero-call proof.
