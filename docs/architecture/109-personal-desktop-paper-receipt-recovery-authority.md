# Architecture 109 — Personal-Desktop Paper Receipt-Recovery Authority

Status: **FROZEN PD3 DESIGN CHECKPOINT — DOCS ONLY — NO RECOVERY EFFECT AUTHORIZATION**

## Purpose

PD3 validates a narrowly bounded steady-state crash-recovery path for the closed,
single-owner personal Windows desktop. It does not create a second paper engine
or a second recovery algorithm. Architecture 67 already defines the only
recoverable steady-state crash state: one fully verified finalized paper-account
transition whose matching completed receipt was not finalized before process
termination. Its existing recovery reconstructs the same canonical receipt,
invokes the paper-cycle runtime zero times, and leaves the committed transition
bytes unchanged.

Architecture 109 wraps that existing behavior in personal-desktop authority,
ordering, gating, and real-host validation suitable for later unattended paper
operation.

This architecture authorizes no recovery effect by itself. Provider call #7,
broker submission, live trading, unattended scheduling, production account or
ACL changes, and v1 cleanup remain outside PD3.

## Existing recovery mechanisms are distinct

The source already contains:

```text
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED = False
```

That gate belongs to Architecture-103 **provisioning-staging recovery** for the
fixed `.Paper-v2.provisioning` tree. It is not steady-state Architecture-67
receipt recovery and must not be overloaded for PD3.

PD3 therefore introduces a separate source-owned gate:

```text
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED = False
```

The existing provisioning-recovery gate remains unchanged and false.

For an effectful receipt-recovery invocation, gate state must be exactly:

```text
PERSONAL_DESKTOP_PAPER_V2_PRODUCTION_EFFECTS_ENABLED           = False
PERSONAL_DESKTOP_PAPER_V2_RECOVERY_EFFECTS_ENABLED             = False
PERSONAL_DESKTOP_PAPER_V2_SUPERVISED_EXECUTION_EFFECTS_ENABLED = False
PERSONAL_DESKTOP_PAPER_V2_RECEIPT_RECOVERY_EFFECTS_ENABLED     = True
```

Any other combination fails closed before opening a write capability. Normal
source and all ordinary tests keep all four gates false.

## Why ordinary account authority cannot be reused

`read_personal_desktop_paper_account()` intentionally rejects an installed
lineage whenever a finalized transition lacks a verified completed receipt. That
is correct for ordinary execution admission: an incomplete operation must not be
mistaken for a healthy account.

PD3 must not weaken that invariant.

Instead, PD3 adds a dedicated **read-only recovery qualification** path. It may
tolerate exactly one missing receipt only for the operation being qualified for
recovery, while preserving the ordinary account reader unchanged.

## Recoverable state

A production state is `RECEIPT_RECOVERY_REQUIRED` only when every condition
below is proven inside one account-mutex lifetime:

1. genuine C1 authority and exact non-admin Trading principal are valid;
2. the fixed Paper-v2 anchor and GENESIS verify exactly;
3. the complete installed transition graph has one unique A66 lineage tip;
4. every transition edge, report, successor checkpoint, and historical snapshot
   verifies through the existing A66/A67 contracts;
5. every installed receipt other than the target fully verifies with its exact
   retained historical cycle-configuration bytes;
6. exactly one finalized transition lacks its matching completed receipt;
7. that transition is the **terminal edge** of the installed lineage;
8. no transition staging, receipt staging, malformed layout, case-fold collision,
   extra recognized object, conflicting edge, invalid receipt, or unsafe object
   exists;
9. the caller-supplied semantic facts for the original operation reconstruct the
   predecessor-lineage prefix, request, strategy plan, operation ID, application
   ID, selected snapshot, and cycle-configuration evidence exactly matching the
   finalized terminal transition;
10. a read-only Architecture-67 inspection of those reconstructed original
    inputs reports exactly `BLOCKED / FINALIZED_TRANSITION_WITHOUT_RECEIPT`.

The transition directory name or fields alone never mint recovery authority.
The missing caller idempotency key is not inferred from the transition. The
operator/future scheduler must present the exact original semantic invocation
facts, and PD3 independently reconstructs and verifies them.

A missing receipt on a nonterminal historical edge is blocked. Multiple missing
receipts are blocked. Any uncertainty is blocked.

## No-recovery states

If the exact operation already has a fully verified completed receipt,
qualification returns `ALREADY_APPLIED` / `NO_RECOVERY_REQUIRED` and grants no
write authority.

If the installed account is otherwise healthy but the supplied operation does
not identify the terminal missing-receipt edge, qualification is blocked rather
than searching for or guessing a different operation.

A valid failed receipt remains terminal failure evidence and is never converted
into receipt recovery.

## Recovery-only Architecture-67 boundary

PD3 must not invoke `execute_paper_operation_once()` directly as the production
recovery primitive. That function intentionally supports both a `PENDING`
execution path and the missing-receipt recovery path; calling it behind a
recovery gate would leave a path to the paper-cycle runtime if state or inputs
were unexpectedly classified `PENDING`.

PD3 therefore adds a recovery-only Architecture-67 entry point, conceptually:

```python
recover_paper_operation_receipt_once(
    operation_root,
    inputs,
    *,
    output_capability,
)
```

It reuses the existing Architecture-67 receipt-recovery implementation and
verification logic but has **no paper-cycle runtime call path**.

Required behavior:

```text
exact BLOCKED / FINALIZED_TRANSITION_WITHOUT_RECEIPT
  -> reread/reverify the finalized transition
  -> reconstruct and verify the same canonical receipt
  -> stage + verify + no-clobber finalize receipt
  -> verify finalized receipt
  -> RECEIPT_RECOVERED

exact ALREADY_APPLIED
  -> ALREADY_APPLIED
  -> zero writes

anything else
  -> BLOCKED/CONFLICTING as appropriate
  -> zero writes
```

No branch in this recovery-only function may call
`execute_checkpointed_verified_snapshot_paper_cycle`, create a new transition,
record a failed receipt, generate a replacement caller key, or retry execution.

## Personal-desktop recovery preparation

The public production-facing PD3 boundary accepts genuine C1/P2 provenance and
the same semantic original-operation facts needed to reconstruct the intended
operation. It accepts no caller-selected filesystem root, output capability,
native API, mutex name, Trading SID, prepared `VerifiedPaperOperationExecutionInputs`,
inspector, recovery function, or gate override.

Preparation must:

```text
genuine C1 + exact Trading token
-> exact P2 selected-snapshot provenance
-> obtain immutable paper_account_id
-> acquire the existing PD2A account mutex
-> perform dedicated recovery qualification under the mutex
-> reconstruct the exact predecessor-lineage prefix
-> rebuild + detached-verify the original P1 strategy plan
-> rebuild the original PaperOperationIntent/application ID
-> build private recovery execution inputs
-> require exact FINALIZED_TRANSITION_WITHOUT_RECEIPT
```

The private raw Architecture-67 inputs and fixed operation root exist only while
the account mutex remains held. They are not serialized or returned.

## Recovery output capability

The existing runtime output capability implementation may be reused, but the
production opener for PD2C execution must remain unchanged. PD3 adds a distinct
receipt-recovery opener that issues the same fixed-namespace one-shot capability
only when the receipt-recovery gate is true and the publication, provisioning
recovery, and supervised-execution gates are all false.

The capability may create/write/finalize only the existing Architecture-67
receipt staging/final paths admitted by the fixed Paper-v2 namespace. It grants
no transition creation path beyond what the recovery-only Architecture-67 entry
point calls; the personal-desktop recovery boundary must never expose the
capability to callers.

## Critical ordering

One PD3 production recovery attempt has this fixed order:

```text
genuine C1/P2 validation
-> account mutex acquired
-> read-only recovery qualification
-> exact target/original-input reconstruction
-> require FINALIZED_TRANSITION_WITHOUT_RECEIPT
-> require receipt-recovery gate true and all other effect gates false
-> open recovery-only output capability
-> re-inspect/reverify target state
-> call recovery-only Architecture-67 primitive once
-> require RECEIPT_RECOVERED or benign ALREADY_APPLIED
-> genuine ordinary Paper-v2 account reread now succeeds
-> require recovered operation verifies as ALREADY_APPLIED
-> close capability
-> release account mutex
```

If state changes between qualification and the recovery-only call, the call may
return benign `ALREADY_APPLIED`; every other changed state blocks. It must never
fall through to fresh execution.

The mutex spans the complete read/recovery/final verification interval.
`ABANDONED_OWNER` remains a reconciliation stop and cannot authorize recovery.

## Result surface

The public result is immutable, sanitized, and non-authorizing. It may expose:

```text
paper_account_id
operation_id
application_id
pre_recovery_classification
recovery_classification
recovery_diagnostic
successor_checkpoint_id
receipt_evidence_produced
post_recovery_classification
```

It must not expose filesystem paths, raw receipt/transition bytes, raw execution
inputs, native handles, output capability objects, credentials, or reusable
recovery authority.

## Tests and real-host validation

Focused tests use disposable seams and disposable filesystem roots only. They
must prove at minimum:

- ordinary Paper-v2 read authority still rejects a finalized transition without
  a verified receipt;
- recovery qualification accepts only one exact terminal missing-receipt edge;
- nonterminal/multiple/staging/invalid/ambiguous states block;
- recovery-only Architecture-67 code has zero runtime invocation path;
- exact missing-receipt recovery produces byte-identical canonical receipt
  evidence and leaves transition bytes unchanged;
- already-applied is zero-write;
- output capability requires the dedicated gate combination;
- the account mutex spans qualification through post-recovery verification;
- disposable test authority cannot invoke genuine production callables.

The current real Paper-v2 account is healthy and already contains the completed
first-operation receipt. PD3 real-host validation therefore remains **read-only**:
it must prove the current operation classifies `ALREADY_APPLIED` / no recovery
required while every recovery gate is false. PD3 must not manufacture a crash
inside the real Paper-v2 tree merely to exercise recovery.

A future genuine recovery effect is authorized only after an actual qualified
missing-receipt condition and a fresh explicit operator authorization. No such
authorization is granted by Architecture 109.

## Completion boundary

PD3 is complete when:

1. Architecture-109 source and focused recovery tests are accepted;
2. broad local certification passes at the final PD3 source tree;
3. a Trading-principal read-only real-host qualification confirms the current
   healthy account needs no recovery;
4. all production/provider/broker/scheduling effects remain closed.

An actual production receipt-recovery mutation is **not required** to complete
PD3 when no genuine recoverable crash exists.

After PD3, the next milestone is PD4 unattended simulated paper operation under
the dedicated Trading account. PD4 must retain the exact original invocation
facts needed for any later PD3 recovery instead of depending on process memory.