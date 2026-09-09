# Architecture 107 — First Paper Mutation Hardening

Status: frozen PD2D2-R2 design checkpoint; documentation only; no production
effect or mutation authorization.

## Purpose

Architecture 107 hardens the already-frozen Architecture-106 first Paper-v2
mutation before another real-host attempt. It closes four review findings found
after the first PD2D2 launcher repair:

1. runtime-created Architecture-67 transition/receipt objects were not guaranteed
   to receive the exact Architecture-103 protected Windows DACLs;
2. the frozen first-operation identity was reconciled too late, after the generic
   Architecture-67 executor could already have mutated Paper-v2;
3. the generic Architecture-67 recovery behavior could commit a receipt from a
   pre-existing `FINALIZED_TRANSITION_WITHOUT_RECEIPT` state even though the
   Architecture-106 first-run contract requires non-`PENDING` state to stop
   without mutation; and
4. generic Windows directory finalization used ordinary `os.rename()` with no
   explicit write-through rename primitive.

This checkpoint does not change any production gate and does not authorize a
second real-host execution attempt.

## Existing frozen operation remains unchanged

Architecture 107 does not replan, regenerate, or replace any Architecture-106
identity or semantic input. The only first operation in scope remains:

```text
paper_account_id:        9415cd7b-bf36-5fba-bd58-a0f99119dc21
prior checkpoint ID:    1832a2b5-8b63-501a-8f7d-f1722c32307b
selection_id:            36d6fbb3-bdec-57e0-a9cf-78dc2b8f7280
selected_snapshot_id:    eba46838-44ae-5bec-97bf-98c6639ae6a7
seed_id:                 5dc95e10-ba22-5b91-94b2-0d851aa8e2d7
caller idempotency UUID: c762ad22-8d10-43d7-a38b-7d95e730c5ea
request_id:              bc0c3aa7-09a0-5534-83bf-0acdf649a2a0
plan_id:                 78292abe-6d6c-5ddf-8ffb-46eb8a914fdb
plan SHA-256:            7f62c90df051f5c4998cc3303b7a97dfb80294dfd743662c2f9930422cb83666
plan byte length:        6199
operation_id:            307f769a-f09a-539d-b12d-3fb51b973809
application_id:          78a1bae8-51ac-5bf0-b159-500768c758fc
```

Any mismatch remains STOP evidence. No replacement idempotency key or alternate
operation may be generated automatically.

## R2-A — Frozen pre-effect admission

The production supervised execution path must reconcile the complete frozen
first-operation profile while the PD2A account mutex is still held and before
calling any Architecture-67 effectful executor.

The check is source-owned and accepts no caller override. At minimum it must
reconcile:

```text
paper_account_id
post-lock terminal checkpoint ID
selected_snapshot_id
caller idempotency UUID
request_id
plan_id
plan artifact SHA-256
plan artifact byte length
operation_id
application_id
fixed operation root
```

The values must come from the active PD2B3 preparation/private binding that was
rebuilt after the mutex-protected Paper-v2 reread. A stale PD2D1 result, CLI
argument, environment variable, configuration file, or copied audit record may
not satisfy this admission check.

The check must run before the Architecture-67 runtime can execute and therefore
before any transition staging, transition finalization, failed receipt, or
completed receipt can be created.

## R2-B — Strict first-run `PENDING` admission

The generic Architecture-67 coordinator retains its normal recovery semantics
for later explicitly authorized recovery work. Architecture 107 does not weaken
or remove those semantics.

The first-mutation production composition, however, must perform one additional
read-only Architecture-67 inspection while the same PD2A mutex is held and must
require exactly:

```text
classification = PENDING
diagnostic     = PENDING
```

Any other classification or diagnostic is a no-effect STOP before the generic
Architecture-67 executor is invoked.

This prevents the first-run authorization from being consumed by receipt
recovery of a pre-existing finalized transition. Once the strict preflight has
observed exact `PENDING/PENDING`, the same account mutex remains held through the
single Architecture-67 call, so no second authorized Paper-v2 writer may change
that operation state between the strict preflight and the generic executor's
own inspection.

If the one permitted runtime attempt itself produces an eligible deterministic
failure, the existing Architecture-67 failed-receipt contract remains
unchanged. That is a result of the authorized runtime attempt, not recovery of a
pre-existing durable state.

## R2-C — Architecture-103 runtime output security

A production-specific Windows runtime-output policy must be inserted into the
Architecture-67 transition and receipt commit path without changing disposable
or generic non-production behavior.

The policy is valid only for the fixed production namespace:

```text
F:\AITradingBot\Paper-v2\runtime
F:\AITradingBot\Paper-v2\runtime\paper-operations
```

It must accept no caller-selected root.

### Existing parents

Before the first production mutation, the policy must reopen and verify the
existing `runtime` and `paper-operations` containers through no-follow Windows
handles and require the exact Architecture-103 owner/protected-DACL/ACE policy.

`paper-operations` is part of the published PD1 layout. The production first-run
path must require it to already exist and must not silently create or repair it.

### New transition/receipt objects

Every new transition staging/final directory, transition report file,
successor-checkpoint file, receipt staging/final directory, and receipt file
must finish with the exact Architecture-103 `OUTPUT_DIRECTORY` or `OUTPUT_FILE`
policy:

```text
owner: exact Trading SID
protected DACL
Administrators: reviewed full-control ACE
SYSTEM:         reviewed full-control ACE
Trading:        exact reviewed output-directory/output-file data rights
no unknown ACEs
no inherited ACE authority
no WRITE_DAC/WRITE_OWNER grant to Trading
```

The production commit path must apply and verify the policy before a staged
directory becomes the authoritative final name, then reopen and verify the
finalized name after the rename. A security-policy failure blocks finalization
or reports an ambiguous/blocked post-commit condition; it is never repaired by
blind retry.

Generic/disposable Architecture-67 tests may continue to use the existing
portable file helpers without Windows ACL effects. Production security behavior
must therefore be injected through a source-owned private policy/capability, not
through a caller CLI switch or environment variable.

## R2-D — Write-through Windows finalization

For the production Paper-v2 policy, staging-to-final directory publication must
use a no-clobber same-parent native Windows rename with write-through semantics,
for example `MoveFileExW(..., MOVEFILE_WRITE_THROUGH)` or a reviewed equivalent.

The policy must not enable replacement, cross-volume copy, delayed reboot move,
or alternate final names. Existing case-fold collision checks, identity checks,
staged rereads, finalized rereads, edge verification, lineage verification, and
receipt verification remain in force.

Portable/disposable Architecture-67 behavior may keep its existing `os.rename`
path; the stricter native finalizer is required only when the production
Paper-v2 output capability is present.

## Production composition after R2

The enabled first-run path becomes:

```text
genuine C1
+ genuine selected call-#6 P2 result
+ frozen pure Architecture-106 inputs
-> PD2B3 preparation
   -> PD2A mutex
   -> post-lock Paper-v2 reread
   -> P1 rebuild + exact replay
   -> private A67 binding
-> Architecture-107 frozen profile reconciliation
-> verify fixed runtime + paper-operations Windows ACLs
-> strict A67 read-only inspection == PENDING/PENDING
-> generic A67 one-shot runtime execution exactly once
   using the production Windows output capability
   -> exact staged ACLs
   -> staged semantic reread verification
   -> write-through no-clobber transition rename
   -> exact finalized ACL + semantic verification
   -> exact staged receipt ACL
   -> staged receipt verification
   -> write-through no-clobber receipt rename
   -> exact finalized ACL + receipt verification
-> return sanitized supervised result
-> release mutex only after terminal outcome / failure unwind
```

No provider, broker, scheduler, live-order, credential, account, group, LSA,
password, KSP, signing, or publication/recovery effect is added.

## Gate policy

All source implementation and source-only testing for Architecture 107 must leave
exactly:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
```

The existing publication freeze remains byte-for-byte unchanged.

No test may make a real Paper-v2 mutation. Native Windows tests, when useful,
must use disposable temporary objects outside the production namespace or a
fully fake native boundary.

## Failure semantics

Before the generic Architecture-67 call, any frozen-profile, root, ACL,
inspection, or native-policy failure performs zero Paper-v2 mutation.

After the Architecture-67 call begins, existing one-shot and crash semantics
remain authoritative. No exception or blocked result is retried in the same
invocation. If any production attempt later becomes interrupted or ambiguous,
Architecture 106 still requires:

```text
DO NOT rerun.
DO NOT delete staging or final objects.
DO NOT repair or rename manually.
DO NOT invoke recovery without a new reviewed authorization.
```

## Certification barrier

Architecture-107 acceptance authorizes only source implementation and testing.

After implementation, ChatGPT/Sol must review the exact diff and focused test
evidence. A fresh broad source certification is required because this repair
changes native output security, authority ordering, and crash-sensitive commit
behavior immediately before a production-effect boundary.

Even a fully certified R2 source does not authorize gate enablement or the second
real-host mutation attempt. That still requires a separate minimal gate change,
exact review, and fresh explicit user authorization immediately before the one
Trading-account invocation.
