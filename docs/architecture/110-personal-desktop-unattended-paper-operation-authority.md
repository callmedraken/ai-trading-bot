# Architecture 110 — Personal-Desktop Unattended Paper Operation Authority

## 1. Scope and decision

PD4 moves the accepted Paper-v2 pipeline from manually initiated supervised
operation to **unattended simulated paper operation under the dedicated non-admin
`Trading` account**.

Architecture 110 is the first PD4 contract. It does not authorize an unattended
run, install a Windows scheduled task, enable provider call #7, perform receipt
recovery, or add broker/live authority. It freezes the authority model that
later PD4 source checkpoints must implement.

The central decision is:

> A scheduler is only an untrusted wake-up source. Durable invocation identity,
> account state, duplicate suppression, recovery identity, and execution
> authority come from reviewed application state and existing C1/P2/PD2/PD3
> contracts, never from Task Scheduler state or process lifetime.

## 2. Controlling predecessor contracts

PD4 must compose, not weaken:

- C1 `ValidatedProductionAuthority` for machine/Trading-token authority;
- C2/C3 transactional market-data authority and its conservative provider-call
  semantics;
- Architecture 94 P1/P2 deterministic strategy-plan and selected-C3 authority;
- PD2A account-scoped Windows mutex;
- PD2B/C supervised preparation/execution ordering and hardened Paper-v2 output;
- Architecture 67 restart-safe operation inspection/execution;
- Architecture 109 / PD3 terminal missing-receipt qualification and recovery.

No scheduler, unattended launcher, environment variable, cwd, PID, wall-clock
value, or task-run history becomes a substitute for any predecessor authority.

## 3. Threat model

PD4 protects the closed single-owner desktop against practical unattended
failure modes:

- duplicate scheduler wakeups;
- process restart after durable intent but before execution;
- process crash between transition and receipt commitment;
- overlapping approved Trading processes;
- stale or wrong selected market-data snapshots;
- replay of an invocation for the wrong account/session/strategy profile;
- partial invocation-record publication;
- caller-selected paths, SIDs, task names, or operation identities;
- ambient `PYTHONPATH`, cwd, or alternate-package selection;
- accidental effect execution while a gate is closed;
- ambiguous prior state being treated as permission to retry.

PD4 does not defend against malicious Administrator/SYSTEM/physical control,
consistent with Architecture 102.

## 4. Scheduler is wake-up only

The eventual Windows scheduler integration may launch a reviewed source-owned
script under the dedicated `Trading` principal, but the scheduled task may
provide **no semantic trading arguments**.

The task must not choose or override:

- paper-account ID;
- Trading SID;
- authority/database/Paper-v2 roots;
- target transition or operation ID;
- caller idempotency UUID;
- strategy configuration;
- risk policy;
- selected snapshot;
- provider identity;
- broker identity;
- recovery target;
- effect-gate state.

Task Scheduler history, trigger count, last-run result, and next-run time are
operator diagnostics only. They are never durable trading authority.

Task creation/modification is a Windows configuration effect and remains outside
source-only PD4 checkpoints until separately reviewed and explicitly approved.

## 5. Durable unattended invocation bundle

Unattended operation requires a durable record of the exact semantic facts
needed to reproduce the operation after process restart and to satisfy PD3-C if
receipt recovery becomes necessary.

Architecture 110 introduces a versioned immutable **unattended invocation
bundle** concept under a fixed source-owned Paper-v2 runtime namespace.

Proposed fixed root:

```text
F:\AITradingBot\Paper-v2\runtime\unattended-invocations
```

Canonical identity is a deterministic UUID5 derived from versioned semantic
material. The exact UUID material must be frozen before implementation, but it
must bind at least:

```text
paper_account_id
intended trading session
selected C3 selection/snapshot identity
strategy profile/configuration identity
unattended schedule-policy version
```

The durable bundle must carry or bind the exact original semantic facts required
by PD3 reconstruction, including:

```text
caller idempotency UUID
strategy-history seed bytes/evidence
strategy configuration
selected P2 snapshot reference and digest/length
open reference
paper-cycle policies
planning/submitted/filled timestamps
metadata
paper account / predecessor identity at qualification time
versioned unattended policy identity
```

The record may reference already-durable C3/Paper-v2 artifacts only when their
exact bytes remain independently recoverable and are reverified by established
contracts. A digest without an authoritative byte source is insufficient.

The durable bundle is immutable once finalized. Restart logic must verify exact
canonical bytes; it may not rewrite an old invocation to match new in-memory
intent.

## 6. Publication ordering for unattended intent

The invocation bundle must be durable **before** the first Paper-v2 execution
effect for that unattended invocation.

Required high-level ordering:

```text
genuine C1
+ exact selected P2 snapshot
-> strict pre-lock Paper-v2 read for immutable account identity
-> acquire existing PD2A account mutex
-> strict post-lock Paper-v2 reread
-> derive exact unattended invocation identity/bundle
-> inspect fixed invocation namespace
-> publish or reverify identical finalized invocation bundle
-> reconstruct exact operation inputs from the durable bundle
-> inspect/reconcile A67
-> only then consider unattended execution effect
```

If bundle staging exists, canonical bytes conflict, the account predecessor has
changed incompatibly, or more than one authority candidate exists, the launch
blocks. No cleanup or repair is implied.

## 7. Invocation-bundle output authority

The invocation bundle requires its own narrow output capability over only the
fixed `unattended-invocations` namespace. It must not be able to create A67
transition/receipt output, C3 snapshots, credentials, broker artifacts, or
arbitrary files.

Publication must reuse the existing hardened Windows patterns where applicable:

- fixed parent validation;
- no-follow/pinned object identity checks;
- exact Trading ownership and ACL expectations;
- write-through creation/finalization;
- no-clobber same-parent final rename;
- read-after-write and read-after-finalize verification;
- one-shot process-local capability;
- fail closed on parent/security drift.

The capability may be opened only by a source-owned unattended boundary after
its dedicated gate and all incompatible gates are in the expected state.

## 8. Dedicated unattended execution gate

PD4 introduces a distinct gate, initially and normally closed:

```text
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = False
```

This gate is separate from:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED
```

A later unattended Paper-v2 effect may be admitted only under an exact reviewed
gate combination. Source-only implementation keeps every gate false.

The unattended gate does not authorize provider access, receipt recovery,
broker submission, live trading, or scheduler installation.

## 9. Duplicate and overlap authority

PD4 does not add scheduler-level duplicate locking. The **same PD2A
paper-account mutex** remains the in-process/cross-process account critical
section.

Duplicate wakeups for the same unattended invocation must converge on the same
durable invocation identity and the same Architecture-67 operation identity.

Expected outcomes:

```text
identical finalized invocation bundle + A67 PENDING
-> same operation may proceed once when effect authority is open

identical bundle + completed receipt
-> ALREADY_APPLIED / no write

identical bundle + exact terminal missing receipt
-> RECOVERY_REQUIRED classification; no blind fresh execution

conflicting bundle / changed semantic facts / ambiguous A67 state
-> BLOCKED
```

A scheduler's claim that an earlier process failed is not authority to retry.

## 10. Startup reconciliation

Every unattended wakeup must reconcile durable state before fresh execution.
At minimum it must distinguish:

```text
HEALTHY_NO_PENDING_INVOCATION
READY_SAME_INVOCATION
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

If PD3 reports `RECEIPT_RECOVERY_REQUIRED`, PD4 must not execute a fresh cycle.
Until a separately reviewed recovery-effect policy exists, the unattended launch
must stop and surface sanitized operator evidence.

Architecture 110 therefore does **not** silently convert the PD3 receipt-recovery
gate into permanently armed unattended recovery authority.

## 11. Selected market-data authority

Architecture 110 does not make C3 provider capture unattended. Initial PD4
source work consumes an already-authoritative selected P2 snapshot and proves
unattended Paper-v2 invocation semantics independently of provider scheduling.

A complete daily unattended product will later need a separately reviewed PD4
checkpoint that bridges an unattended wakeup to C3 market-data capture while
preserving Architecture-77/82 one-shot provider-call authority, credential
containment, recovery classification, and selection verification.

Until that checkpoint is reviewed and explicitly authorized:

```text
provider call #7 = NOT AUTHORIZED
```

No unattended paper gate may imply a provider call.

## 12. Session and freshness policy

The scheduler clock is a fact to reconcile, not authority to nominate arbitrary
market data.

Before unattended execution, a source-owned policy must verify that:

- the selected snapshot is a valid P2 result under the current C1;
- its market session is exactly the session required by the unattended
  invocation policy;
- the modeled next-session open reference follows the established calendar;
- no stale snapshot may be used merely because a scheduled wakeup occurred;
- replaying an old wakeup does not create a new semantic invocation.

The exact timing window and session-eligibility rule must be frozen in a later
PD4 checkpoint before any real unattended run.

## 13. Post-run verification

Before mutex release, an unattended execution path must require:

```text
strict ordinary Paper-v2 reread
complete lineage/receipt verification
exact operation/application reconciliation
expected terminal checkpoint
A67 ALREADY_APPLIED for completed operation
C1/P2 provenance still valid
all source-owned gate expectations still valid
```

The public result is sanitized audit evidence only and carries no reusable
execution authority.

## 14. Failure and recovery rules

PD4 inherits the conservative rules:

- no automatic cleanup of staging or conflicting state;
- no automatic new caller idempotency key after ambiguous failure;
- no new operation to "make progress" after a crash;
- no retry because Task Scheduler reports failure;
- no provider retry outside C2/C3 authority;
- no receipt reconstruction through fresh paper-cycle execution;
- no broker/live fallback;
- no account mutation outside reviewed capabilities.

Uncertain state stops the unattended launch and leaves durable evidence for
operator review.

## 15. Source-checkout and production interpreter

The eventual unattended launcher must use the established reviewed `scripts/`
source-checkout pattern and the fixed production interpreter:

```text
F:\AITradingBot\runtime\python.exe
```

It must not depend on ambient `PYTHONPATH`, current working directory, developer
virtualenv, or an alternate installed `trading_bot` package.

## 16. Initial PD4 checkpoint decomposition

Recommended source sequence:

```text
PD4-A  canonical unattended invocation model + pure verification
PD4-B  fixed invocation-bundle read authority and safe publication capability
PD4-C  read-only startup qualification/reconciliation under PD2A mutex
PD4-D  unattended Paper-v2 execution composition with gate False
PD4-E  no-argument source-checkout launcher + scheduler contract
PD4-F  final source certification + Trading-principal read-only qualification
```

A later separately reviewed checkpoint is required for unattended C3 provider
capture. Actual task installation and the first unattended effect remain
explicit operator/effect boundaries.

## 17. Non-goals

Architecture 110 does not authorize or implement:

- provider call #7;
- unattended C3 provider access;
- Windows scheduled-task installation or modification;
- real receipt recovery;
- broker-paper or live order submission;
- margin, leverage, shorts, options, or crypto;
- a daemon or high-frequency polling loop;
- remote multi-host coordination;
- v1 cleanup or migration;
- account/group/password/LSA/KSP changes.

## 18. Acceptance criteria

Architecture 110 is accepted when implementation and validation prove:

```text
scheduler is wake-up only
unattended semantic identity is source-owned and deterministic
exact restart-recovery facts are durable before execution
same PD2A mutex protects the account critical section
A67 remains durable duplicate/idempotency authority
missing-receipt state cannot enter fresh execution
unattended gate is distinct and defaults False
invocation output capability cannot write A67/provider/broker state
strict post-run reread/reconciliation is mandatory
ambient package/cwd/task state grants no trading authority
provider/broker/live authority remains unchanged
```
