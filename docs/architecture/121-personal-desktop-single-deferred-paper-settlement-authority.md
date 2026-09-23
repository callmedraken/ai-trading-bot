# Architecture 121 — Personal-Desktop Single-Deferred Paper Settlement Authority

Status: frozen docs-only PD4 recovery-design checkpoint. No Paper-v2 execution,
receipt recovery, market-data capture, decision publication, storage
provisioning, scheduler mutation, broker effect, or live effect is authorized
by this document.

## 1. Triggering production observation

After the first D8 settlement attempt was delayed by bounded source diagnostics,
source correction, certification-performance work, and repository hygiene, a
fresh non-effect production preflight on 2026-09-23 established:

```text
current completed XNYS session: 2026-09-22
all eight source-owned effect gates: false
D8-A invoked: false
```

A subsequent zero-effect current-C1 decision inspection established:

```text
session 2026-09-21:
  classification: FINALIZED
  decision_id: f2188b5e-e6a4-5398-be41-8867d9268355
  intended_execution_session: 2026-09-21
  selected_session: 2026-09-18
  same-process current-C1 provenance: verified

session 2026-09-22:
  classification: NONE
  decision_id: null
  same-process current-C1 provenance: verified
```

No D8-A or other effect was invoked by either observation.

Architecture 114 deliberately requires ordinary D8 to settle only a finalized
decision targeting the *current* completed session. Therefore ordinary D8 must
not be widened silently to consume the now-prior 2026-09-21 decision.

## 2. Scope and decision

Architecture 121 defines one narrow pre-D10 recovery authority for a
**single deferred already-finalized settlement**.

It does not create general historical catch-up semantics.

The central decision is:

> Before D10 exists, a distinct zero-semantic-argument deferred-settlement
> boundary may resolve at most one source-owned, already-finalized decision whose
> intended execution session is earlier than the current completed session,
> but only when the complete fixed decision namespace and Paper-v2 predecessor
> truth prove that this is the sole unresolved first-settlement candidate. The
> decision must have been finalized under the existing pre-open authority, its
> exact selected C3 execution-session evidence must still verify under current
> C1, and the existing Architecture-94 / PD4 / Architecture-67 deterministic
> identities must be reused unchanged. No missed decision may be created,
> backfilled, substituted, or replayed as a new decision.

Architecture 121 adds a separate boundary. It does **not** weaken or reinterpret
Architecture 114's ordinary current-completed-session D8 rule.

## 3. Why this is not automatic multi-session catch-up

Architecture 111 forbids turning an outage into a burst of retrospective fresh
decisions/effects.

This checkpoint permits neither.

The only potentially effectful object already exists durably: one finalized
pre-open decision. Architecture 121 may complete that decision's deterministic
Paper-v2 settlement at its original verified `open(E)`. It may not:

- create a decision for 2026-09-22 or any other skipped session;
- create more than one deferred settlement;
- iterate over a backlog;
- infer an execution session from directory ordering;
- use the current session's open in place of the decision's execution session;
- advance directly into another publication or settlement effect.

After independent reconciliation of the one deferred settlement, this recovery
boundary stops. D10 must define any future operational missed-wake policy.

## 4. Zero-semantic-argument boundary

The deferred boundary accepts no caller-selected trading facts.

The caller may not supply or override:

```text
decision ID
decision session
execution session
selected snapshot / selection ID
paper account ID
predecessor checkpoint
open reference
history seed
strategy parameters
invocation / operation / application ID
filesystem path
retry count
recovery target
effect flag
```

All candidate identity must come from the fixed durable namespaces, current C1,
the genuine Trading token, and existing deterministic contracts.

## 5. Source-owned single-candidate derivation

Candidate derivation must read the complete fixed unattended-decision namespace
through a reviewed public read-only API. Production code must not import a
private helper merely to enumerate the namespace.

For this pre-D10 first-settlement recovery, admission requires:

```text
complete fixed decision namespace is readable and security-valid
no staging / malformed / unknown / conflicting decision entry
exactly one finalized decision exists in the namespace
its intended execution session E is strictly earlier than current completed C
its canonical bytes replay exactly
its decision identity is deterministic and unchanged
its predecessor checkpoint is compatible with current Paper-v2 truth
no later finalized decision exists
no caller-supplied session or identity influenced candidate selection
```

Any zero, multiple, staging, malformed, conflicting, ambiguous, or
security-unverifiable candidate state fails closed.

The "exactly one finalized decision" restriction is intentionally narrow and
pre-D10. Architecture 121 is not a general future queue processor.

## 6. Exact deferred execution evidence

For the unique candidate decision selected in section 5, the boundary must
independently rederive:

```text
current validated production C1
genuine non-admin Trading token
current completed XNYS session C
deferred intended execution session E
decision's original selected session S
current-C1 selected C3(S)
current-C1 selected C3(E)
exact persisted decision C3 evidence
verified daily-bar open(E)
exact Architecture-94 final plan for S -> E
current Paper-v2 account / predecessor truth
exact unattended invocation identity/state
exact Architecture-67 operation/application identity/state
current receipt-recovery qualification
```

The execution reference remains `open(E)` from selected C3(E). Wall-clock
lateness does not change the deterministic plan or operation identity.

If selected C3(E), the original decision evidence, predecessor/account truth,
or any current-C1 provenance cannot be reproduced exactly, the result is
`BLOCKED`.

## 7. Existing startup/execution authority remains controlling

Architecture 121 reuses the existing PD4-C / PD4-D / Architecture-67 authority.

It must not create:

- a second account mutex;
- a new idempotency key;
- a replacement decision;
- a replacement plan schema;
- a second operation for the same decision;
- an alternate receipt or recovery path.

The startup boundary remains authoritative for:

```text
HEALTHY / exact execution-ready admission
same-invocation convergence
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

A predecessor mismatch, unrelated account advance, conflicting operation,
ambiguous invocation state, or missing-receipt state cannot be bypassed because
the decision is deferred.

## 8. Effect containment

All eight committed gates must be exact `False` at entry.

If and only if the read-only deferred qualification proves fresh execution is
safe and the operator later authorizes one protected effect, the effect boundary
may open only:

```text
PERSONAL_DESKTOP_PAPER_V2_UNATTENDED_EXECUTION_EFFECTS_ENABLED = True
```

for at most one call to the existing reviewed unattended execution composition,
and restore it in `finally`.

The other seven effect gates remain false.

No same-invocation retry is permitted. Process failure, timeout, ambiguity, exit
code, or partial output grants no retry authority.

## 9. No recovery, provider, publication, scheduler, broker, or live effect

Architecture 121 does not authorize:

```text
receipt recovery
Paper-v2 repair
market-data capture
decision publication
historical decision backfill
storage provisioning
Task Scheduler mutation
broker-paper submission
live trading
```

If receipt recovery is required, stop.

If the unique deferred decision cannot be proven exactly, stop.

## 10. Independent deferred reconciliation

A fresh-process, all-gates-closed reconciliation boundary must independently
rederive the same unique deferred decision and exact deterministic settlement
identity.

Successful reconciliation requires:

```text
same finalized decision bytes / identity
same selected C3(S) and selected C3(E)
same verified open(E)
same final Architecture-94 plan
same expected invocation / operation / application identities
expected Architecture-67 operation == ALREADY_APPLIED
exact completed receipt verifies
exact deterministic successor checkpoint verifies
current Paper-v2 account tip == that successor
lineage proves predecessor -> successor through the exact operation
current C1 / Trading token remain valid
all eight gates remain false
```

A successful effect return is not acceptance authority. Only the independent
all-gates-closed reconciliation closes the recovery checkpoint.

## 11. Protected sequence

Source implementation and certification authorize no production invocation.

The protected sequence is:

```text
D8-R1  single-deferred read-only qualification
       -> zero semantic arguments
       -> complete fixed decision namespace
       -> exactly one finalized deferred candidate
       -> exact C1 / Trading / C3(S) / C3(E) / open(E) / plan
       -> exact current Paper-v2 predecessor/startup state
       -> all eight gates closed

D8-R2  separately approved one-shot deferred settlement
       -> at most one existing unattended execution composition call
       -> only unattended-execution gate temporarily open
       -> no retry / no receipt recovery

D9-R1  fresh-process all-gates-closed independent reconciliation
       -> exact decision / C3 / open / plan / invocation / operation / receipt
       -> exact successor / account tip / lineage
```

Every effect checkpoint requires fresh explicit operator approval immediately
before the protected invocation.

## 12. Required source tests

Source acceptance must prove at least:

- zero semantic arguments;
- complete fixed-namespace read is required;
- exactly one finalized namespace decision is required;
- zero/multiple/staging/conflicting/malformed decisions block;
- candidate execution session must be strictly before current completed;
- ordinary Architecture-114 current-session D8 behavior remains unchanged;
- exact current-C1 selected C3(S) and C3(E) required;
- exact decision replay and verified open(E);
- exact final Architecture-94 plan identity;
- current account/predecessor incompatibility blocks;
- already-applied performs zero fresh effect;
- recovery-required performs zero recovery;
- only unattended-execution gate may open;
- at most one existing execution composition call;
- gate closes in `finally`;
- no provider/publication/provisioning/scheduler/recovery/broker/live boundary;
- independent reconciliation does not trust effect output;
- public results contain no reusable capability/handle/path/credential/raw C1.

## 13. Exit from this recovery checkpoint

After one deferred first settlement is independently reconciled, Architecture
121 is complete and no longer grants ongoing catch-up authority.

The next architecture milestone remains D10 bounded unattended simulated-paper
soak. D10 must explicitly decide how future delayed wakes and stale finalized
decisions are handled operationally before scheduler composition is broadened.

PD5 broker-paper remains later and unauthorized.
