# Architecture 133 — Single-Session Unattended Review-Paper Validation Plan

Status: frozen design plan. No provider access, scheduler mutation, activation
publication, paper mutation, or broker/live effect is authorized by this plan.

Baseline:

```text
develop HEAD 1419b551230b00102291cd3bab2f23e4e1a3588b
develop TREE 5d98221b3a2933726b56692c5092d715455807f4
Architecture 131 merged via PR #24
post-merge source gate #222 SUCCESS
```

## Goal

Prove that one pre-authorized proposal can cross one unattended Robinhood
review-only/synthetic-paper wake without human mid-wake input while retaining
Architecture-131 session, risk, quote-freshness, exactly-once, ambiguity,
evidence, and zero-real-order guarantees.

The first qualification targets exactly one NYSE session. Multi-session
recurrence is deferred.

## 133-A focused validation — ACCEPTED

Accepted exact source:

```text
HEAD b0751e1ff2109b7f99725910ee901685e293e175
TREE 2230e11bcb3a2b27171aaa506f12110c31ae77a0
CI   #227 / 37388706716 SUCCESS
```

The exact six-file GitHub review found no correction requirement. The complete
133-A module is AST-pinned by the source gate, the checkpoint is source-only
with no preflight/execute callback, and #227 passed the optimized batch,
Ruff check/format, diff check, identity-stability check, and 133-A authority
check.

Accepted validation covers:

- strict closed schemas and canonical serialization;
- deterministic activation/wake identities;
- exact proposal/order/session binding;
- filesystem path retained as exact storage material but excluded from
  deterministic identity under the repository-wide identity rule;
- legal and illegal state transitions;
- completed/stopped/indeterminate terminal replay with no transition authority;
- review-started failure -> INDETERMINATE only;
- timezone normalization and malformed timestamp rejection;
- ambient-Decimal-context independence;
- no UUID4, filesystem, SQLite, network/provider/OAuth, risk, scheduler,
  retry/polling, or paper-write capability in the pure module.

Focused implementation verification reported 233 core cases, 1,018 runner
cases, and two certification-inventory cases across the focused and
corrected-failure runs. No broad suite was required at this pure source boundary.

## 133-B focused validation — FROZEN

Durable state/reconciliation tests must cover:

- closed SQLite schema/version and exact canonical row material;
- create-only activation + READY wake admission in one transaction;
- exact-identical reopen is read-only/idempotent;
- same activation ID with different canonical activation bytes is a hard
  conflict, including a changed stored filesystem path;
- exact expected wake/revision compare-and-swap transitions;
- stale writer rejection and transaction rollback without internal retry;
- legal 133-A transition delegation rather than a second transition matrix;
- completed/stopped/indeterminate durability across close/reopen;
- no transition authority from terminal states;
- independent verifier using SQLite URI `mode=ro` without constructing the
  writer;
- verifier rejection of malformed metadata/schema, partial rows, noncanonical
  activation/wake JSON, mismatched activation/wake binding, duplicate/conflict
  rows, and stale expected identity;
- deterministic complete-store fingerprint independent of SQLite row-return
  order;
- the Architecture-131 paper-store path remains inert serialized material and is
  never opened by 133-B;
- zero provider/OAuth/risk/review/paper-fill/scheduler/subprocess/environment
  capability;
- source-only checkpoint registration immediately after 133-A with no
  preflight/execute callback.

## 133-C focused validation

Composition tests use doubles at all provider/effect boundaries and prove:

- exact 131-S target-session schedule;
- one quote acquisition maximum;
- exact 131-N/O snapshot/risk material;
- quote deadline remains valid at effect admission;
- risk rejection never reaches review;
- durable review-start fence precedes review invocation;
- one review invocation maximum;
- one synthetic fill maximum;
- any ambiguity forbids same-activation retry;
- zero historical catch-up;
- forbidden mutation tools are unreachable.

## 133-D focused validation

Execution tests must cover BUY/SELL, APPROVED/RESIZED/REJECTED, provider
exception, process-boundary ambiguity, operator PASS/FAIL, exact deterministic
paper idempotency, persisted-OAuth-only behavior, and all four forbidden mutation
counters fixed at zero.

The existing accepted Architecture-131 verifier semantics remain regression
coverage. Do not weaken 131-V human-supervised behavior to implement unattended
mode.

## 133-E focused validation

Launcher/scheduler-source tests must prove:

- zero semantic CLI arguments;
- no browser/interactive OAuth path;
- exact source/runtime/activation admission before provider access;
- scheduler spec points only at the reviewed launcher;
- no task retries;
- no overlapping effect authority;
- task identity is distinct from historical D10;
- task state is not activation authority;
- source tests never mutate Task Scheduler.

## Certification topology

Use the Architecture 132 policy:

```text
FOCUSED
-> source-gate CI for each pushed registered checkpoint
-> ROBINHOOD at the first coherent complete Robinhood boundary
-> FULL at final Architecture-133 current-product integration
-> LEGACY/EXHAUSTIVE only if a later change actually touches historical compatibility
-> PROTECTED always separately authorized
```

## Protected qualification gates

### Q133-1 — provider-free host preflight

Read-only. Verify exact accepted source/runtime identity, persisted OAuth
availability without browser interaction, paper-store predecessor state,
single-session activation material, proposed scheduler spec, and zero consumed
wake state.

### Q133-2 — activation publication

Fresh explicit approval. Publish exactly one reviewed single-session activation.
No provider request and no scheduler mutation.

### Q133-3 — scheduler installation/update

Fresh explicit approval. Create/update exactly the distinct Architecture-133
one-session task and verify by readback. No manual provider/trading invocation.

### Q133-4 — first unattended wake

Fresh explicit approval to allow the installed one-session task to perform its
single bounded provider wake. The wake may use the accepted read/review tools and
write one synthetic local paper result only. No placement/cancel/options/crypto.

### Q133-5 — provider-free reconciliation

Read-only. Reconcile activation/wake state, operator evidence, paper BEFORE/AFTER
fingerprints, call counts, and zero mutation counters. No retry.

### Q133-6 — task/activation closeout

Prove the single-session authority cannot fire again before deciding on any
multi-session extension.

## Stop conditions

STOP rather than retry on:

- source/runtime/activation mismatch;
- noncanonical or conflicting wake state;
- missed/expired target session;
- quote/session freshness failure;
- risk rejection or risk drift;
- interactive OAuth requirement;
- provider ambiguity;
- any attributable real order;
- any forbidden mutation call;
- durable paper conflict;
- independent verifier disagreement;
- unexpected scheduler identity;
- any already-consumed review-start state.

A STOP/INDETERMINATE result grants no next attempt.

## Exit

A successful Q133-1 through Q133-6 sequence establishes only that one unattended
single-session review-paper wake is safe under the frozen authority. It does not
authorize a multi-session soak, broker-paper, or live trading.
