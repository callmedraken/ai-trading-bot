# Architecture 134-F2 — five-session soak protected readiness preflight

Status: **SOURCE ACCEPTED at 2737f950beb4dd0ba75016ecb544576e1046f86f / 3445945966ad03c5fb399ae890fa48069a896641; canonical ROBINHOOD #657 passed. Real preflight remains unrun.**

Architecture 134-F2 creates the missing read-only readiness boundary between the
accepted Architecture 134-F1 source and any protected five-session authorization.
It does not authorize the soak, create a task, reserve a parent series, read
credentials, contact a provider, invoke D1R7/D1R8, mutate paper/session state, or
grant live authority.

## Exact predecessor identities

Design predecessor before this freeze:

```text
branch  develop
HEAD    71c147b2fd21994f5af81e5ce685974183370d0d
TREE    9568290b4d587b838d9cbd08f33d1ea86005143a
```

Accepted F1 operational source:

```text
branch  feature/robinhood-production-paper-134f-five-session-soak
HEAD    b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE    e8a94e3512d7950f2fbc9c4d102a58b63e03244f
CI      canonical ROBINHOOD #649 / 39401319643 / SUCCESS
```

The protected F1 host is intentionally fixed to:

```text
F:\AI\worktrees\ai-trading-bot-production-paper-134f-five-session-soak
```

F1 evidence/provenance remains bound to that accepted feature HEAD/TREE, not to
later integration or documentation descendants.

Accepted F1 operational blobs that F2 must not modify:

```text
src/trading_bot/review_paper/five_session_soak_store.py
3813837e8d10ee2b19150405143704a7f03d474f

src/trading_bot/review_paper/five_session_soak.py
9de15257fc9b6fe97e90314450b097849ff81320

src/trading_bot/review_paper/five_session_soak_child.py
6afcdfe42ac1691bc477efcfb4764c227a0c1bc2

src/trading_bot/review_paper/five_session_soak_host.py
9c3197005811ec0cd2b38f8ce4c7717f6c9e2108

scripts/arch134_f1_bridge.py
1e35f11bf623ac333df37a45dc45e4a0fe282427

scripts/arch134_f1_scheduler.ps1
0cb85477f4958cce32c5b409be66e6013aa9f575

scripts/run_arch134_f1.py
3528cd65d77484d9ab58868b75699a6edcc9aa84
```

Accepted child-source pins remain:

```text
D1R7
HEAD 30322c49b13b80af8d20acee4bdb1efd83d86260
TREE b7dc7f054fca50c3ab784505f264b6f716a45dff

D1R8
HEAD aa07c5ba94e0b55cbd8f920464fcc5bd9efcabd2
TREE fcbfc348dab307fb9c456ce9e17aad0e53d7bd4f
```

Accepted Architecture 144-C remains the pure post-soak evidence-admission path:

```text
HEAD 1e86b5dcce19cd45504266b4fa0ac0aca5854d04
TREE 47f13748c89784fddf0ef981072a7b23f7d02f22
CI   #652 / 39410467329 / SUCCESS
```

## Why a separate F2 source boundary is required

The accepted F1 source checkpoint is deliberately source-only:

```text
checkpoint arch134-f1-five-session-soak
preflight  None
execute    None
```

The F1 host exposes three partial read-only ingredients but no complete protected
readiness contract:

- `run_arch134_f1.py --status` observes only the durable parent journal;
- `arch134_f1_scheduler.ps1 -Mode Observe` observes only the fixed task;
- existing source/runtime/predecessor helpers can perform bounded reads but are
  not composed into a registered fail-closed preflight.

Therefore F1 source acceptance plus 144-C acceptance cannot be converted directly
into an authorization command. F2 must first provide one checked-in,
source-reviewed, registered read-only preflight.

## F2 source checkpoint

Checkpoint:

`arch134-f2-five-session-soak-readiness`

Implementation branch:

`feature/robinhood-production-paper-134f2-five-session-soak-readiness`

Canonical worktree:

`F:\AI\worktrees\ai-trading-bot-production-paper-134f2-five-session-soak-readiness`

Expected primary new source/tests:

```text
src/trading_bot/review_paper/five_session_soak_readiness.py
tests/review_paper/test_five_session_soak_readiness.py
```

The checkpoint runner must register:

```text
preflight  <F2 read-only preflight>
execute    None
```

The preflight source checkpoint is Robinhood/review-paper owned. Map the exact F2
checkpoint to CI-owned canonical `robinhood` before its one terminal
publication. Do not run duplicate local ROBINHOOD and do not select FULL merely
because the boundary is security-sensitive.

The existing `feature/robinhood-*` workflow family already admits the branch.

## Registered preflight invocation

Only after F2 source is exact-source accepted may the operator run:

```powershell
.\ops.ps1 preflight arch134-f2-five-session-soak-readiness
```

The runner's normal preflight admission must require a clean exact F2 worktree
and exact live remote F2 branch HEAD before the callback runs.

The callback must return a closed sanitized result with schema:

`arch134-f2-five-session-soak-readiness/v1`

The only positive status is:

`READY_FOR_SEPARATE_F1_AUTHORIZATION`

Any exception, unknown state, malformed evidence, drift, or unsupported state
must return/raise a bounded BLOCKED result without raw native/provider/credential
details.

## Exact read-only readiness checks

### 1. Frozen F1 source admission

Prove the fixed F1 worktree:

- resolves exactly to the fixed F1 path;
- is on the exact accepted F1 branch;
- has HEAD/TREE exactly `b59ad3b... / e8a94e...`;
- has the expected origin fetch/push URL;
- tracks the exact remote F1 branch;
- is tracked/index/untracked clean exactly as the F1 operational bridge requires;
- remains registered in the common Git worktree registry;
- matches a read-only `git ls-remote` result for the accepted remote branch.

No fetch, pull, checkout, switch, reset, merge, rebase, clean, branch mutation, or
ref update is permitted inside preflight.

Apply the same exact read-only source admission to the fixed D1R7 and D1R8
worktrees/pins.

### 2. Frozen F1 source bytes

Prove the seven F1 operational blob hashes above before any host observation.
The preflight implementation may not alter, wrap, replace, or loosen those F1
files.

### 3. Qualification parent and predecessor evidence

The qualification parent remains:

`F:\AI\temp\qualification`

Require it to be the exact expected absolute non-reparse directory.

Read and validate the accepted D1R5 and D1R6 predecessor evidence using their
existing bounded canonical readers/binder. Do not invoke D1R7 or D1R8.

A predecessor mismatch is BLOCKED. No repair, replacement, regeneration, retry,
or evidence deletion is authorized.

### 4. Current runtime read-only compatibility

Use only the accepted read-only production runtime inspection semantics equivalent
to `preflight_runtime()`.

READY requires:

`runtime_status = PRESENT_COMPATIBLE`

The preflight may report bounded paper-record and session-reservation counts.

It must not call rollback/write-readiness qualification, open a writable SQLite
transaction, initialize/migrate/repair a store, or write any runtime file.

Write readiness is deliberately reported as `NOT_CHECKED` by F2. Credential
and provider readiness are also `NOT_CHECKED`.

### 5. Fresh F1 authority namespace

A first F1 series can be admitted only when the protected namespace is untouched.

READY requires absence of:

- `arch134-f1-five-session-soak-v1.jsonl`;
- every `arch134-f1-child-*.jsonl`;
- every F1 child `.d1r7.claim` / `.d1r8.claim`;
- parent scheduler-create/run claim files;
- unexpected F1 supervisor/child lock artifacts.

Any existing parent slot is BLOCKED even if canonical or FINAL. F1's fixed slot
is consumed by existence and is never deleted, repaired, overwritten, or reused.
Any unexpected child/claim/lock artifact without the parent is also BLOCKED and
requires a later separate read-only reconciliation design.

The preflight must only inspect existence/metadata; it must not acquire a F1
lifetime lock because the accepted lock helper creates/opens a lock file.

### 6. Fixed Task Scheduler observation

Invoke only the accepted F1 scheduler transport in exact `Observe` mode.

For this first F1 protected series, READY requires:

`scheduler_status = ABSENT`

`MATCH` is not silently accepted here because no F1 scheduler creation has ever
been authorized. A pre-existing matching task is unexpected external state and
must be reconciled before authority can be consumed.

`BLOCKED`, unavailable COM state, shape drift, or any other result is BLOCKED.

F2 may never invoke scheduler `Create` or `Run`, call
`RegisterTaskDefinition`, call `Task.Run`, update/delete a task, or create a
scheduler claim.

### 7. Target-window preview

Using the accepted NYSE published regular-session authority and an aware UTC
clock, derive the same five-session preview as F1 `select_window`.

Return:

- the exact observation timestamp;
- five ordered preview target dates.

The preview is diagnostic only. It is not identity, reservation, or session
authority. The later F1 authorization must recompute and freeze its own target
window from its own admitted clock.

### 8. Final readmission

Before returning READY, repeat the exact F1/D1R7/D1R8 source checks, parent/child/
claim absence checks, runtime read-only compatibility, and scheduler observation.

Any drift between first and final observation is BLOCKED.

## Explicit effect contract

F2 preflight may perform only bounded filesystem/Git/SQLite reads and fixed Task
Scheduler observation.

It must establish all of these as zero:

```text
F1_PARENT_RESERVATIONS=0
F1_CHILD_RESERVATIONS=0
F1_LOCK_CREATIONS=0
F1_CLAIM_CREATIONS=0
SCHEDULER_CREATES=0
SCHEDULER_RUNS=0
SCHEDULER_UPDATES=0
SCHEDULER_DELETES=0
CREDENTIAL_READS=0
CREDENTIAL_WRITES=0
PROVIDER_REQUESTS=0
OAUTH_INTERACTIONS=0
RUNTIME_SQLITE_WRITES=0
RUNTIME_WRITE_PROBES=0
D1R7_OPERATIONS=0
D1R8_OPERATIONS=0
PAPER_MUTATIONS=0
BROKER_MUTATIONS=0
D2_OPERATIONS=0
STRATEGY_PROMOTIONS=0
REAL_MONEY_EFFECTS=0
```

Task Scheduler **reads**, production SQLite **read-only inspection**, Git
read-only commands and bounded predecessor/evidence reads are allowed and must
be represented honestly rather than counted as zero effects.

The runner may write its ordinary external checkpoint evidence report. That
report is not F1 operational state and must remain outside repository/runtime/
qualification authority paths.

## Boundary after a PASS

A F2 preflight PASS grants no soak authority.

After PASS, ChatGPT must independently review the exact preflight evidence and
current state. Only then may the user separately authorize the exact F1
interactive authorization command against the accepted F1 HEAD/TREE.

That later command is the first authority-consuming boundary: it may reserve the
fixed parent slot and, under the already accepted F1 state machine, may create
and demand-run the fixed F1 scheduled task and later delegate bounded D1R7/D1R8
paper-session effects.

No automatic transition from preflight PASS to authorization is allowed.

Real-money trading remains **NO-GO**.
