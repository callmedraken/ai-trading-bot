# D10 One-Week Unattended Simulated-Paper Soak — Validation and Deployment Plan

Status: frozen Architecture-122 plan. No scheduler mutation or recurring effect is authorized by this document.

Baseline:
- develop HEAD before D10 design: 0024ad86767c76116094688d13ecff6ebf0aa438
- develop TREE: 6da85aacd1704b3541f9c9ac9efb56eb5ea188ec
- Architecture 121 production state: RECONCILED
- installed task: capture-only

## Soak definition

The first D10 soak lasts exactly seven calendar days from accepted activation. It never extends automatically and never graduates automatically to broker-paper.

## Source checkpoints

S1 — D10 orchestration
Add a zero-semantic-argument controller that composes only reviewed public boundaries. Order: capture if required; read-only daily-cycle truth; at most one current-session settlement; fresh read-only settlement reconciliation; at most one next-session pre-open publication; fresh read-only decision reconciliation; final all-gates-closed evidence. No catch-up loop.

S2 — stale and missed-session admission
Add explicit fail-closed handling for stale finalized decisions, missed decision deadlines, and session gaps. Architecture-121 recovery is never called automatically.

S3 — bounded window and evidence
Add source models for activation, exact seven-day end boundary, active/expired state, sanitized per-wake evidence, and a cumulative read-only summary.

S4 — one-week scheduler contract
Define the exact D10 task contract: Trading principal, production Python, zero semantic arguments, fixed D10 launcher, normal daily wake timing unless review changes it, StartWhenAvailable constrained by Architecture 122, no task retries, no overlap as defense in depth, and a deterministic end boundary exactly seven days after accepted activation. Do not mutate the installed task during source work.

S5 — source certification
After exact GitHub review and a stable source tree, run focused D10 tests and then the persistent certification runner once, including the Architecture-77 serial lane.

## Protected deployment

D10-A read-only deployment qualification: fresh integrated checkout under Trading; verify source/runtime/principal, all gates closed, Architecture-121 reconciled durable state, current capture-only task identity, and derive the exact one-week deployment spec without mutation. Stop for review.

D10-B scheduler mutation: requires separate explicit operator approval. Change exactly the reviewed task from capture-only to the one-week D10 launcher and verify it by readback. This approval does not include a manual trading effect.

D10-C first scheduled wake: observe the first automatic wake and require final gates closed plus exact bounded evidence.

D10-D observation: allow normal scheduled wakes while the window is active. Any Architecture-122 stop condition halts the soak. No automatic restart or extension.

D10-E end-of-week closeout: prove no further D10 effects can occur, collect evidence, reconcile Paper-v2 account/receipts/lineage, summarize performance separately from operational safety, and re-evaluate.

## Focused tests

Cover zero arguments; all gates closed on entry/final exit; only one gate open at a time; provider/settlement/publication one-attempt limits; no receipt recovery; stale decision, missed deadline, and session gap stop behavior; duplicate/restart convergence; already-applied and already-finalized idempotency; ambiguity prevents same-wake retry; exact timezone-safe seven-day expiry; expired soak has no effect; scheduler end boundary equals activation plus seven days; sanitized evidence; and existing D5/D7/D8/D9/Architecture-121 regressions.

## Fault exercises

Use disposable/source tests for weekend/holiday, sleep/late StartWhenAvailable, duplicate processes, provider failures, consumed/ambiguous provider attempt, missed deadline, stale decision, history gap, conflicting durable state, already-applied operation, missing receipt, account drift, and process death around reviewed boundaries. Do not intentionally corrupt the real Paper-v2 account.

## Re-evaluation

At seven calendar days, stop and review. Broker-paper and live remain separately unauthorized.
