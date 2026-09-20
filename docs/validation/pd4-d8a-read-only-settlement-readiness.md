# PD4 D8-A Read-Only Settlement Qualification Readiness Runbook

## Status and scope

**READY AS A DOCS-ONLY PRE-EXECUTION CHECKPOINT. D8-A HAS NOT BEEN RUN FROM THIS CHECKPOINT.**

This runbook prepares the protected D8-A Trading-principal read-only qualification without exercising production settlement, receipt recovery, provider capture, decision publication, scheduler mutation, broker effects, or live effects.

It does not authorize D8-B. D8-B remains a separate explicitly approved effectful checkpoint even if D8-A later reports `EXECUTION_READY`.

## Current accepted source state

```text
develop HEAD:                  ec992a9313a077d625d801917213a00d7eccda01
develop tree:                  b481d372c3ef1a2869b63ccfaa4e3c6caccb7479

combined certified source HEAD:
4c2a064e31d460dd3c7534fadad6c50204ffcd82

combined certified source tree:
9d341fcfd6eb5493887012814c5943850d903744

D8/D9 settlement certified source HEAD:
da093791cf6d879f1b07d605665900c28b9a7e9d

D8/D9 settlement certified source tree:
1c9f6840eeae7feb5456892f9d8119eb45466af9
```

The combined operator-observability certification exercised the repository with the D8/D9 source already integrated:

```text
broad non-Architecture-77:        5,789 passed, 17 skipped
Architecture-77 clean harness:      758 passed
combined:                         6,547 passed, 17 skipped
Ruff check/format:                PASS
diff checks:                      PASS
```

A GitHub source-inheritance audit performed after PR #10 integration compared the 22 replacement-certified D8/D9 settlement candidate files with current `develop`. **Zero of those 22 files changed after settlement certification.** All source/test changes after the settlement-certified commit belong to the separately certified operator-observability milestone.

Therefore the accepted D8/D9 settlement implementation remains intact in the current integrated lineage. This proof does not itself authorize a production D8-A invocation.

## Intended settlement target

```text
decision_id:
f2188b5e-e6a4-5398-be41-8867d9268355

decision selected/completed session:
2026-09-18

intended execution session E:
2026-09-21

account predecessor:
ed4640e5-0630-525d-b916-d50e31e3ba2a
```

The earlier D8-A invocation that observed completed session `2026-09-18` and returned `NO_SETTLEMENT_PENDING` is historical read-only evidence only. It does not satisfy the D8-A checkpoint for execution session `2026-09-21`.

## Eligibility gate before any real D8-A invocation

Do not invoke D8-A merely because the wall-clock date is September 21.

Important frozen-timing detail: `completed_xnys_session_at(...)` uses the
strict previous modeled XNYS session by New York exchange date. Therefore
execution session `2026-09-21` is not the D8-A completed session while the
exchange-local date is still September 21. The accepted D5 task trigger is
01:30 Pacific daily. The preferred first meaningful D8-A attempt is therefore
only after the normal **2026-09-22 01:30 Pacific D5 wake** has completed and
read-only evidence shows selected C3 for `2026-09-21` exists.

There is a deliberate interval after the exchange-local date advances to
September 22 but before the normal D5 wake/capture completes in which D8-A can
derive completed session `2026-09-21` yet still return `BLOCKED` because
selected C3(E) is not available. Do not use that predictable early `BLOCKED`
state as retry authority and do not manually start D5 to accelerate it.

A real D8-A invocation is eligible only after all of the following are true:

1. the source-owned XNYS calendar derives the current completed session as `2026-09-21`;
2. a current-C1 selected C3 snapshot exists for `2026-09-21`;
3. the finalized decision targeting `2026-09-21` remains exact and current-C1-backed;
4. the dedicated non-admin `Trading` principal is used;
5. the approved production runtime is used;
6. the source checkout is pinned to an accepted certified executable/source identity;
7. all eight production effect gates are exact `False`;
8. there has been no intervening source, authority, account, scheduler, or durable-state change that invalidates the accepted preconditions.

If any item is uncertain, stop before invoking the production qualifier.

## Execution checkout policy

Unless a later replacement source certification supersedes it, the preferred source checkout for the first meaningful D8-A qualification is the exact combined certified source:

```text
HEAD: 4c2a064e31d460dd3c7534fadad6c50204ffcd82
TREE: 9d341fcfd6eb5493887012814c5943850d903744
```

A disposable detached checkout should be used so the executable source identity is unambiguous and the ordinary development worktrees remain untouched.

Example preparation from an ordinary development account:

```powershell
$Repo = 'F:\AI\ai-trading-bot'
$Checkout = 'F:\AI\worktrees\ai-trading-bot-d8a-production-qualification'
$Source = '4c2a064e31d460dd3c7534fadad6c50204ffcd82'

Set-Location $Repo

if (Test-Path $Checkout) {
    throw "D8-A disposable checkout already exists; do not reuse or delete it blindly."
}

git worktree add --detach $Checkout $Source
Set-Location $Checkout

git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
git status --short
```

Expected source identity:

```text
HEAD 4c2a064e31d460dd3c7534fadad6c50204ffcd82
TREE 9d341fcfd6eb5493887012814c5943850d903744
status clean
```

Creating or inspecting this disposable checkout does not authorize D8-A. The actual production invocation remains a protected operational checkpoint.

## Production-runtime/source launcher preflight

The approved production interpreter remains:

```text
F:\AITradingBot\runtime\python.exe
```

The D8-A source-checkout launcher is:

```text
scripts\run_personal_desktop_read_only_settlement_qualification.py
```

Before a protected invocation, prove that the launcher is the file from the pinned checkout and that the production interpreter can execute the isolated source-checkout launcher pattern. Do not supply semantic command-line arguments.

The launcher deliberately inserts its own checkout `src` into `sys.path`. The intended production form is:

```powershell
& 'F:\AITradingBot\runtime\python.exe' -I `
  "$Checkout\scripts\run_personal_desktop_read_only_settlement_qualification.py"
```

**Do not run that command until the eligibility gate above is satisfied and the operator explicitly proceeds with the protected D8-A checkpoint.**

D8-A accepts zero semantic arguments. Do not append account IDs, session IDs, decision IDs, paths, effect flags, or other trading facts.

## Expected bounded D8-A classifications

D8-A is read-only. `real_effect_performed` must always be `false`.

### `NO_SETTLEMENT_PENDING`

Meaning: the current completed session has no exact finalized decision to settle.

Action: stop. Do not infer eligibility from the exit code and do not invoke D8-B.

### `EXECUTION_READY`

Meaning: independent D8-A re-derivation reached the existing reviewed startup authority and classified the exact deterministic invocation as eligible for a fresh settlement attempt.

Action: preserve the D8-A evidence and stop at the approval boundary. D8-B requires a separate explicit operator approval.

### `ALREADY_APPLIED`

Meaning: durable startup/account/operation state already converges on the exact expected operation.

Action: do not run D8-B. Proceed only to the separate all-gates-closed D9-A read-only reconciliation checkpoint.

### `RECEIPT_RECOVERY_REQUIRED`

Meaning: exact durable state indicates a terminal operation whose receipt requires the separate recovery authority.

Action: stop. D8-A and D8-B do not authorize receipt recovery.

### `BLOCKED`

Meaning: D8-A could not prove the exact required source/authority/token/C3/decision/open/plan/account/startup state.

Action: stop and diagnose from preserved evidence. Do not retry blindly and do not mutate durable production state as a workaround.

## CLI exit behavior

```text
0  bounded non-BLOCKED D8-A result
2  invalid arguments
5  validation exception before a normal result
6  BLOCKED result
```

Exit codes are diagnostic only. They are never settlement authority. The JSON classification and independently reviewed durable evidence determine the next checkpoint.

## Evidence to preserve

```text
source checkout HEAD/tree
production interpreter path/version
Trading principal identity
D8-A JSON classification
completed_execution_session
decision_selected_session
decision_id
decision_selected_snapshot_id
execution_selected_snapshot_id
final_plan_id
invocation_id
operation_id
application_id
account_predecessor_checkpoint_id
terminal_checkpoint_id
startup_status
all_eight_gates_closed
real_effect_performed
process exit code
```

Do not record credentials, secret-store values, private keys, reusable capabilities, handles, permits, or raw C1 authority.

## Stop conditions

```text
source HEAD/tree mismatch
dirty or reused disposable checkout
unexpected production interpreter
wrong Windows principal or elevation state
current completed session is not 2026-09-21
selected C3(2026-09-21) missing or not current-C1-backed
finalized decision identity/session mismatch
any effect gate open or non-boolean
Paper-v2 predecessor/account contradiction
BLOCKED or validation exception
receipt recovery required
unexpected filesystem/durable-state mutation
provider, publication, scheduler, recovery, broker, or live effect
```

No stop condition authorizes cleanup, backfill, repair, a new operation identity, or automatic retry.

## Work intentionally deferred while waiting

- do not run D8-A repeatedly just to watch the session change;
- do not invoke D8-B;
- do not run D9-A as if settlement had occurred;
- do not modify the D5 scheduler;
- do not begin D10 scheduler-composition changes;
- do not advance to PD5 broker-paper.

Architecture 114 explicitly places D10 after accepted first D8/D9 settlement. The first settlement outcome should be preserved before D10 soak policy and scheduler composition are frozen.

## Next checkpoint

After the normal 2026-09-22 D5 wake has completed, and only when read-only
evidence confirms that the runtime independently derives completed session
`2026-09-21` and current selected C3 evidence for that session exists, perform
one fresh protected D8-A Trading-principal read-only qualification from the
exact accepted source identity.

Then:

```text
EXECUTION_READY            -> stop for explicit D8-B approval
ALREADY_APPLIED            -> skip D8-B; prepare protected D9-A
RECEIPT_RECOVERY_REQUIRED  -> stop
NO_SETTLEMENT_PENDING      -> stop and diagnose timing/decision selection
BLOCKED                    -> stop and diagnose
```

D8-B remains unauthorized by this runbook.
