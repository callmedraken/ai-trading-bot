# PD4 Single-Deferred Settlement Validation Plan

Status: frozen validation plan for Architecture 121. Source-only until a
separately approved protected D8-R2 effect. This plan authorizes no Paper-v2
mutation, receipt recovery, provider capture, decision publication, storage
provisioning, scheduler mutation, broker effect, or live effect.

## 1. Objective

Implement and certify a narrow pre-D10 recovery path for the observed state in
which the first accepted finalized unattended decision targets a session that is
no longer the source-derived current completed session.

Observed production state motivating this plan:

```text
current completed session: 2026-09-22
2026-09-21 decision: FINALIZED / current-C1 provenance verified
2026-09-22 decision: NONE / current-C1 provenance verified
all eight gates: false
D8-A invoked during observation: false
```

Ordinary Architecture-114 D8 remains unchanged and current-session-only.

## 2. Development branch and protection boundary

Docs/design branch:

```text
branch: feature/pd4-single-deferred-settlement-authority
base: 91392bb3667eac24ebcc613d309b030a766bbfff
```

During source work:

```text
armed D5 worktree/task                  unchanged
existing production qualification trees unchanged
all committed effect gates              False
real deferred settlement                 NOT AUTHORIZED
D8-A retry                               NOT AUTHORIZED
D8-B                                     NOT AUTHORIZED
receipt recovery                         NOT AUTHORIZED
broker/live                              NOT AUTHORIZED
```

Do not reuse or advance an existing protected production-qualification checkout
for source implementation.

## 3. Implementation routing

This milestone changes production authority, ordering, and external-effect
containment.

Implementation model: **Sol High**.

ChatGPT owns architecture, exact diff review, test-gate decisions,
certification, merge readiness, production preflight, and operator boundaries.

## 4. Source checkpoint R1 — public read-only namespace/candidate authority

Add the smallest public read-only storage interface needed to derive the
Architecture-121 candidate without importing private storage helpers.

Required behavior:

```text
read complete fixed namespace once through reviewed Windows read authority
require genuine Trading token and current validated C1
verify every finalized artifact canonically
reject staging / malformed / unknown / conflicting namespace state
derive exactly one finalized decision total
require its E < current completed C
return only bounded immutable decision evidence / binding with same-process provenance
no filesystem ordering or caller session/decision input
```

Focused tests must cover zero/one/multiple decisions, staging/conflict,
canonical replay, token drift, current-C1 provenance, and absence of mutation.

## 5. Source checkpoint R2 — D8-R1 read-only deferred qualification

Add a distinct zero-semantic-argument qualification boundary. Do not widen the
existing D8-A current-session implementation.

D8-R1 independently reconstructs:

```text
unique deferred candidate
C1 / Trading token
selected C3(S)
selected C3(E)
verified open(E)
exact Architecture-94 final plan
installed-only historical configuration dependencies
current Paper-v2 account/predecessor
PD4-C startup classification
all eight gates closed
```

Required classifications should be bounded and non-authorizing, including:

```text
NO_DEFERRED_SETTLEMENT
EXECUTION_READY
ALREADY_APPLIED
RECEIPT_RECOVERY_REQUIRED
BLOCKED
```

`real_effect_performed` must always be false.

## 6. Source checkpoint R3 — D8-R2 one-shot deferred settlement source

Prepare a separate zero-semantic-argument production boundary, effects closed by
default.

Required behavior:

1. independently repeat D8-R1 source-owned derivation;
2. never trust D8-R1 public output as authority;
3. require all eight gates false at entry;
4. reuse exact PD4-C / PD4-D / Architecture-67 identities;
5. open only unattended-execution process-locally;
6. call the existing unattended execution composition at most once;
7. restore the gate in `finally`;
8. never perform receipt recovery;
9. never create or publish a missed decision;
10. never loop across prior sessions.

Any ambiguous result stops and grants no retry.

## 7. Source checkpoint R4 — D9-R1 independent deferred reconciliation

Add a fresh-process, zero-semantic-argument, all-gates-closed reconciliation
boundary that independently reconstructs the same unique first-settlement
candidate and proves durable convergence.

Success requires exact:

```text
decision
C3(S)
C3(E)
verified open(E)
final plan
invocation
operation / application
completed receipt
successor checkpoint
account tip
predecessor -> successor lineage
current C1 / Trading token
eight closed gates
```

No D8-R2 output is authority.

## 8. Focused verification during implementation

Run focused tests/checks only while iterating:

- Architecture-121 candidate-storage tests;
- D8-R1 tests;
- D8-R2 effect-containment tests;
- D9-R1 reconciliation tests;
- existing Architecture-114 D8/D9 tests proving no regression;
- finalized-decision storage tests;
- selected-C3/open/plan tests directly touched;
- PD4-C/PD4-D tests directly touched;
- Ruff check/format on changed Python;
- `git diff --check`.

Do not run the broad suite after each correction.

## 9. Final source certification

Only after exact GitHub source review finds the implementation tree stable:

1. run focused regression surfaces;
2. run one complete repository certification with the persistent certification
   runner;
3. run the required Architecture-77 serial lane through that runner;
4. capture exact HEAD/tree and lane/JUnit/result evidence;
5. require Ruff/format/diff checks clean.

Any post-certification source change invalidates only the affected certification
scope as determined by ChatGPT; do not reflexively rerun the broad suite for
docs-only changes.

## 10. Protected production sequence

After source integration, create a **fresh** detached production-qualification
checkout from the exact integrated source.

Under non-admin `DESKTOP-I4DOKM7\Trading`:

```text
preflight
  -> exact source/runtime/principal
  -> current completed session
  -> all eight gates false
  -> no effect

D8-R1
  -> read-only deferred qualification
  -> stop and preserve evidence

D8-R2
  -> only after separate explicit one-shot operator approval
  -> at most one unattended execution composition call
  -> stop on every result

D9-R1
  -> fresh process
  -> all gates closed
  -> independent durable reconciliation
```

No source certification, preflight, or D8-R1 result itself authorizes D8-R2.

## 11. Stop conditions

Stop on at least:

```text
source/tree mismatch
wrong/elevated principal
unexpected gate state
namespace zero/multiple/staging/conflicting/malformed
candidate is current/future rather than deferred
decision/C3 provenance contradiction
selected C3(E) missing
verified open(E) mismatch
final-plan mismatch
account predecessor drift
invocation/operation conflict
receipt recovery required
second execution attempt
provider/publication/provisioning/scheduler/recovery/broker/live effect
```

No stop condition authorizes cleanup, a replacement decision, historical
publication, backfill, a new operation identity, or retry.

## 12. Completion and next milestone

Architecture 121 closes only after one deferred first settlement has independent
D9-R1 reconciliation.

Then return to D10 bounded unattended simulated-paper soak. D10 must define the
future operational stale-decision/missed-wake policy before changing the current
capture-only scheduler composition.
