# Architecture 130 — R8I-D1 Failed-Child Effect Reconciliation

## 1. Scope and decision

R8I-D1 is the post-containment, read-only investigation for the terminal first
natural D10 wake on 2026-10-01.

The incident is already fixed and immutable:

```text
soak_id=30e31396-9f51-57ca-a480-d2a3e9cae4a0
wake_start_utc=2026-10-01T08:30:09.370767Z
guard_terminal_utc=2026-10-01T08:30:21.815609Z
guard_reason=CHILD_OUTPUT_INVALID
durable_record_count=2
accepted_wake_count=0
scheduler_containment=DISABLED_VERIFIED
```

The failed child was launched, but its stdout/stderr did not satisfy the launch
guard contract and the guard did not persist those bytes. Therefore R8I-D1 must
not infer effect history from the missing child receipt. It reconstructs effect
history only from independently durable production truth.

R8I-D1 is strictly read-only. It cannot restart the stopped soak, invoke the
child, call the provider, publish a decision, execute Paper-v2, recover a
receipt, mutate Task Scheduler, repair storage, or perform broker/live effects.

## 2. Questions R8I-D1 must answer

The registered reconciliation must independently classify three effect families:

1. provider / C3 effect
   - Was a provider attempt durably recorded for the exact source-owned session
     associated with the failed wake?
   - Did that attempt produce a terminal C3 snapshot and selected-C3 lineage?
2. unattended decision publication
   - Does the fixed unattended decision namespace contain durable publication
     state attributable to the exact decision that could have been built from
     that session and predecessor state?
3. unattended Paper-v2 execution
   - Does the fixed unattended invocation namespace, A67 operation state,
     receipt state, or successor paper-account lineage prove that Paper-v2 was
     invoked or applied?

The public classification for each family is one of:

```text
PROVED_NOT_RUN
PROVED_OCCURRED
INDETERMINATE
```

No weaker evidence may be promoted to either proved state.

## 3. Controlling evidence hierarchy

R8I-D1 uses this authority order:

```text
durable verified production artifact/state
> exact immutable incident evidence
> sanitized process result
> scheduler/process state
```

The failed child's missing stdout/stderr are unavailable and therefore carry no
authority.

Timestamp proximity alone is not proof that an artifact came from the failed
wake. Every positive attribution must bind source-owned semantic identity such
as request bytes, selection/snapshot identity, decision identity, invocation
identity, operation/application identity, predecessor checkpoint, or successor
checkpoint.

## 4. Fixed incident admission

Before reading any effect namespace, the reconciler must re-prove the immutable
incident and containment state from source-owned constants:

```text
deployment_id=d2071f25-5a7c-5293-a28f-5b722c9917a2
attestation_sha256=3ffe4ecf1745599e7edb233d3f08a9707a1b27384d2f050a1805ee4929ebbd71
soak_id=30e31396-9f51-57ca-a480-d2a3e9cae4a0
activation_utc=2026-09-30T22:07:24.000000Z
end_utc=2026-10-07T22:07:24.000000Z
evidence_path=F:\AITradingBot\D10\evidence\wake-30e31396-9f51-57ca-a480-d2a3e9cae4a0.jsonl
evidence_byte_length=453
evidence_sha256=b2b5d5f84db2dd7d41b67d38b0449a1e701b9f1a1e0c4bac825663a0ebf36d7e
record_count=2
wake_count=0
terminal=true
terminal_kind=GUARD_TERMINAL
last_guard_reason=CHILD_OUTPUT_INVALID
```

The Task Scheduler state must be independently observed as the exact accepted
task with `enabled=false` and non-running state after R8I-H1. Any mismatch
blocks reconciliation rather than reopening or repairing containment.

## 5. Provider / C3 reconciliation

Provider reconciliation must use the existing validated production-authority
and read-only C3 lineage contracts.

The reconciler derives the exact source-owned completed session and canonical
`ProductionCaptureRequest` that the failed D10 wake would have considered. It
must not accept a caller-supplied session or request.

Read-only production SQLite access must remain `PRAGMA query_only=ON`, must
match the validated authority database identity, and must not change
`total_changes`.

The reconciler then determines whether durable provider-attempt / terminal-C3 /
selected-C3 state exists for the exact canonical request.

Classification:

```text
PROVED_NOT_RUN
  only when the authoritative durable lineage proves no provider-attempt state
  exists for the exact request and no selected/terminal C3 artifact exists.

PROVED_OCCURRED
  only when authoritative durable lineage proves an attempt/effect attributable
  to the exact request. The result records sanitized attempt, terminal-state,
  selection and snapshot identities when available.

INDETERMINATE
  on malformed/conflicting/duplicate lineage, authority drift, inaccessible
  read-only state, or evidence that cannot distinguish a prior legitimate
  capture from the failed wake.
```

A selected-C3 artifact existing before the failed wake does not prove the failed
child called the provider; attribution must use durable attempt identity and
source-owned request semantics.

## 6. Decision-publication reconciliation

The fixed decision namespace is:

```text
F:\AITradingBot\Paper-v2\runtime\unattended-decisions
```

R8I-D1 must reuse the existing read-only unattended-decision storage and
reconciliation contracts. It may derive expected decision identity only from
validated C1, exact selected-C3/history state, the accepted strategy
configuration, the exact predecessor paper-account state, and source-owned
calendar/timing rules.

Classification:

```text
PROVED_NOT_RUN
  authoritative namespace inspection proves the exact expected decision was
  absent and there is no staging/conflicting artifact attributable to it.

PROVED_OCCURRED
  authoritative inspection proves an exact finalized identical decision artifact
  for the exact derived decision identity.

INDETERMINATE
  staging, conflict, malformed namespace contents, predecessor ambiguity,
  inability to derive one exact candidate, or read-authority failure.
```

R8I-D1 must not publish, finalize, repair, delete, or backfill a decision.

## 7. Paper-v2 reconciliation

Fixed production roots include:

```text
F:\AITradingBot\Paper-v2\runtime
F:\AITradingBot\Paper-v2\runtime\paper-operations
F:\AITradingBot\Paper-v2\runtime\unattended-invocations
```

The reconciler uses the existing fixed read-only Paper-v2 authority, unattended
invocation storage reader, Architecture-67 operation inspection, ordinary
paper-account read authority, lineage verification, and successor-checkpoint
verification.

It derives the only candidate unattended invocation from validated source-owned
state. No operation, invocation, application, account, or path identity may be
accepted from argv/environment/operator input.

Classification:

```text
PROVED_NOT_RUN
  the exact invocation namespace is authoritatively absent, no corresponding A67
  operation/receipt exists, and paper-account lineage contains no successor
  attributable to the candidate.

PROVED_OCCURRED
  durable state proves one or more of:
    - exact finalized unattended invocation,
    - exact A67 operation/receipt,
    - exact application identity,
    - exact verified successor checkpoint
  attributable to the candidate.
  The public result states which durable proof was observed.

INDETERMINATE
  staging/conflicting invocation state, missing-receipt ambiguity, malformed A67
  state, incompatible account lineage, multiple candidate identities, or any
  read-authority failure.
```

Presence of a finalized invocation alone proves that the child crossed the
unattended invocation publication boundary, but does not by itself prove the
Paper-v2 account mutation completed. The public result therefore records
separate booleans for durable invocation publication, operation evidence, and
successor-account evidence while the family classification remains conservative.

## 8. CHILD_OUTPUT_INVALID diagnosis

The exact rejected stdout and stderr bytes are unrecoverable from this incident.
R8I-D1 must say so explicitly.

The root-cause diagnostic may narrow only to durable facts. It may report:

```text
EFFECT_PATH_NOT_REACHED
EFFECT_PATH_REACHED_BEFORE_OUTPUT_FAILURE
OUTPUT_CONTRACT_FAILURE_AFTER_DURABLE_EFFECT
OUTPUT_CONTRACT_FAILURE_WITH_NO_DURABLE_EFFECT
UNRESOLVED
```

These are derived from reconciled durable effect state, not from speculation
about the missing bytes.

R8I-D1 must not claim whether the child emitted stderr, malformed JSON,
multiple lines, oversized output, missing output, or a schema-invalid receipt
unless a separate durable source proves that exact condition.

## 9. Read-only implementation constraints

The registered checkpoint must:

- have no protected execute mode;
- accept no semantic argv, paths, identities, dates, sessions, operation IDs, or
  account IDs;
- import only reviewed source at the exact checkpoint HEAD;
- require the accepted non-admin Trading token for production Paper-v2 reads;
- use Administrator rights only if an existing read-only native observer
  requires them; no mutation may be reachable;
- open SQLite only through approved read-only authority;
- use existing pinned/no-follow production read authorities for filesystem data;
- perform before/after source identity checks and live-remote exact-head check;
- prove the scheduler remains disabled/non-running;
- prove durable D10 incident evidence remains byte-identical;
- expose every effect field explicitly as `NOT_RUN`;
- contain no provider call, decision writer/publication permit, Paper-v2 effect
  gate opening, scheduler setter, receipt recovery, cleanup, repair, broker, or
  live boundary;
- fail closed on any unknown filesystem entry, duplicate, staging artifact,
  conflicting lineage, source drift, authority drift, or identity ambiguity.

## 10. Public report

The result schema is:

```text
architecture-130-r8-failed-child-reconciliation/v1
```

At minimum it reports:

```text
status
incident=EXACT_TERMINAL_FIRST_WAKE
containment=DISABLED_NON_RUNNING_EXACT

provider:
  classification
  exact_request_sha256
  attempt_id?
  terminal_state?
  selection_id?
  snapshot_id?

decision_publication:
  classification
  decision_id?
  storage_classification?

paper_v2:
  classification
  invocation_id?
  invocation_published
  operation_id?
  operation_state?
  application_id?
  successor_checkpoint_id?
  successor_verified

child_output_diagnosis

failed_child_effects:
  provider
  decision_publication
  Paper-v2

scheduler_mutation=NOT_RUN
evidence_mutation=NOT_RUN
lease_mutation=NOT_RUN
production_filesystem_mutation=NOT_RUN
source_launch=NOT_RUN
provider_effect=NOT_RUN
decision_publication_effect=NOT_RUN
Paper-v2_effect=NOT_RUN
broker=NOT_RUN
live=NOT_RUN
```

A family classification of `PROVED_OCCURRED` describes a historical effect
proved by durable state; the corresponding current-checkpoint effect field must
still be `NOT_RUN`.

## 11. Acceptance sequence

```text
D1-A  architecture/source design acceptance
D1-B  registered read-only reconciler + focused tests + authority pins
D1-C  exact-source CI acceptance
D1-D  fresh production-host read-only preflight/reconciliation
D1-E  canonical status/handoff closeout
```

No D1 stage authorizes restart or replacement of the stopped soak.

## 12. Next step after D1

If every family is `PROVED_NOT_RUN`, the incident becomes a no-durable-effect
child-output failure and the next source milestone is guard/child-output
diagnostic hardening before a separately designed replacement soak.

If any family is `PROVED_OCCURRED`, reconcile that exact durable lineage first;
do not retry the historical effect.

If any family is `INDETERMINATE`, remain fail-closed and add a narrower
read-only reconciler. Production/live trading remains NO-GO.
