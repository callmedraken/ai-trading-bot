# Architecture 130 — D10 First-Wake Incident Reconciliation

## Status

Source-design checkpoint for **R8I-D1** after R8 terminal scheduler containment.
This architecture is diagnostic only. It does not restart, extend, replace, or
graduate the stopped soak.

The fixed incident is:

- deployment: `d2071f25-5a7c-5293-a28f-5b722c9917a2`
- soak: `30e31396-9f51-57ca-a480-d2a3e9cae4a0`
- wake start: `2026-10-01T08:30:09.370767Z`
- guard terminal: `2026-10-01T08:30:21.815609Z`
- guard reason: `CHILD_OUTPUT_INVALID`
- evidence bytes: 453
- evidence SHA-256:
  `b2b5d5f84db2dd7d41b67d38b0449a1e701b9f1a1e0c4bac825663a0ebf36d7e`

R8I-H1 has already disabled the scheduler and verified evidence/lease stability.
Architecture 130 begins only from that contained state.

## Question

The failed child was launched but its output was rejected. The guard did not
persist the rejected stdout/stderr bytes. Therefore two questions must be kept
separate:

1. **What durable effects or effect-lineage records exist?**
2. **Which of those can be attributed to the failed child and incident window?**

Architecture 130 never converts durable presence into causal authorship without
time- or dependency-bearing durable evidence.

## Authority model

The observer is one registered **read-only preflight**. There is no execute
profile.

It may:

- verify the frozen incident evidence, activation lease, and already-disabled
  scheduler through the accepted R8 read-only observers;
- run the administrator-only installed-authority validation;
- open the fixed authority SQLite database read-only through the approved VFS;
- enable SQLite `query_only` and perform bounded SELECTs;
- use pinned Paper-v2 read sessions to enumerate fixed namespaces;
- parse and verify canonical decision and invocation artifacts;
- parse canonical Paper operation receipts;
- parse fixed transition reports/checkpoints through the existing read-only
  account reader.

It must not:

- call the one-week soak controller;
- start the D10 source;
- call a provider;
- publish a decision;
- publish an invocation;
- execute or recover a Paper-v2 operation;
- mutate SQLite;
- mutate Paper-v2 files;
- mutate evidence or lease state;
- start/stop/register/delete/enable/disable a scheduled task;
- perform broker or live effects.

All effect fields in the checkpoint evidence remain `NOT_RUN`.

## Frozen incident sessions

The observer derives session context from the incident timestamp, never from
wall-clock time at diagnosis.

`completed_xnys_session_at(2026-10-01T08:30:09.370767Z)` must derive:

```text
completed session:       2026-09-30
next execution session:  2026-10-01
```

A different derivation blocks the observer.

## C3 reconciliation

The exact source-owned capture request for the incident completed session is
serialized canonically and matched against the fixed authority database by:

- authority epoch ID,
- request bytes,
- SHA-256 request digest.

The observer then reads at most 16 attempts and their joined claim,
reservation, launch, terminal, and selection lineage.

Authority timestamps are durable but only second-resolution. Therefore the
microsecond incident boundary is treated conservatively:

```text
08:30:09Z  -> BOUNDARY_SECOND
08:30:10Z through 08:30:21Z -> DEFINITE_INCIDENT_SECOND
all others -> OUTSIDE_INCIDENT_SECONDS
```

A confirmed provider terminal whose attempt and terminal timestamps are both in
the definite range may be classified `CONFIRMED_INCIDENT_WINDOW`. A lineage
touching the boundary second cannot be promoted beyond
`MAY_HAVE_OCCURRED_IN_BOUNDARY_SECOND`.

No sub-second fact is invented from a second-resolution database column.

## Decision reconciliation

The complete fixed unattended-decision namespace is pinned and enumerated.
Every finalized artifact is canonically verified.

The incident-next decision is the decision whose:

- selected session is `2026-09-30`, and
- intended execution session is `2026-10-01`.

If its current C3 selection/snapshot identities equal the incident C3 selected
lineage, the observer may state:

```text
INCIDENT_C3_DEPENDENT_NO_PUBLICATION_TIMESTAMP
```

This proves that artifact could not predate that C3 selection. It does **not**
by itself prove that the failed child published it, because the decision
artifact has no trusted publication timestamp and R7 did not snapshot this
business namespace.

Staging and unknown namespace entries are preserved as diagnostic facts or
block the read; they are never treated as finalized publication.

## Invocation and Paper-v2 reconciliation

The complete fixed unattended-invocation namespace is pinned and canonically
verified. Incident settlement invocations are those whose execution session is
the incident completed session.

The Paper operation container is pinned and enumerated. Each canonical
operation directory is classified as either:

- receipt present and canonically parsed, or
- receipt absent.

Receipt absence is retained because a finalized transition with a missing
receipt is a known recovery state; absence is not treated as proof that the
effect did not occur.

The fixed runtime namespace is also enumerated. Non-reserved entries are parsed
through the existing read-only transition reader. A transition/receipt whose
snapshot ID equals the incident C3 selected snapshot may be classified as:

```text
INCIDENT_C3_DEPENDENT_PAPER_STATE_NO_EFFECT_TIMESTAMP
```

Again, dependency proves ordering relative to the C3 selection, not failed-child
authorship.

## Attribution result

The observer emits separate fields for:

- `provider`
- `decision_publication`
- `Paper-v2`
- `highest_durable_dependency`
- `causal_limit`

The initial source contract intentionally allows unresolved attribution. It is
better to retain `UNKNOWN`/dependency-only evidence than to infer a write time
that the durable artifact does not contain.

Operator-history evidence may later be evaluated separately, but it must not be
smuggled into this read-only durable-state observer.

## CHILD_OUTPUT_INVALID diagnosis

Exact rejected stdout/stderr are unrecoverable because the guard captured but
did not persist them.

The durable observer can only narrow how far the workflow may have progressed.
The guard reason remains compatible with:

- child non-zero exit;
- non-empty stderr;
- stdout byte/line-count failure;
- stdout JSON parse failure;
- stdout schema/semantic validation failure.

A later source correction may add durable bounded rejected-output diagnostics
for a replacement soak, but the stopped incident is never rewritten.

## Checkpoint

Registered name:

```text
arch130-r8i-d1
```

The checkpoint has:

- source gate;
- read-only preflight;
- live-remote exact-source admission;
- **no protected execute function**.

After source certification, the next host step is one elevated read-only
preflight from the exact accepted remote head. No authorization variable is
needed because there is no effect boundary in Architecture 130.
