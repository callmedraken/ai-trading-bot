# Architecture 134-D1R9 — arbitrary-time one-session D1 supervisor validation

Status: SOURCE IMPLEMENTED; local focused source checks passed.
Mapped CI and exact GitHub source acceptance remain required publication gates.

Acceptance objective: prove that one top-level D1R9 authorization can be issued
at an arbitrary time while the PC is ON and safely carry one session across
closed-market/weekend/holiday/premarket waits and process restarts, while
preserving accepted D1R7/D1R8 one-shot safety.

Required classes:

1. Session resolution: Friday after close, Saturday, Sunday and holiday select the
   next published session; current premarket/admitted select current; after
   close-minus-five selects next; cover DST and early close.
2. Durable waits/restart: reconcile NEXT_SESSION_WAIT, PREMARKET_WAIT and
   D1R8_WAIT from current time + durable state; bounded <=60s wait quantum; no old
   sleep duration authority; backward clock safe.
3. D1R7 delegation: durable intent before child entry; accepted source pinned and
   re-admitted; complete READY artifact independently reread/parsed/hashed;
   partial/invalid/ambiguous evidence never retries.
4. D1R8 delegation: separate import/process boundary; ReviewedProof only from
   validated D1R7 bytes; no run before open+5; durable intent before entry;
   complete terminal reconciliation; ambiguity never invokes a second attempt.
5. Effect containment: preserve all accepted D1R8 ceilings; credential
   writes/deletes/OAuth renewal/broker/options/crypto/ACL/D2/live stay zero;
   scheduler plumbing never grants market/session authority.
6. Operator surface: one top-level interactive authorization; noninteractive
   resume requires durable authorization; status/reconcile read-only; no
   date/session/provider/account/price/quantity/evidence/order selectors.

Use a new isolated D1R9 branch/worktree. Keep D1R7/D1R8 and historical evidence
frozen. Focused tests, retained overlay checks, Ruff and diff checks precede one
atomic commit/push. GitHub owns mapped canonical certification. Source acceptance
grants no real operational effects.

Implemented regression module: `tests/review_paper/test_d1_session_supervisor.py`.
Tests use disposable external stores and the accepted D1R8 pure controller with
fake credentials, Alpaca transport and Robinhood adapters. All scheduler/process
edges are fake or source-inspected; no native COM/task invocation occurs.

The matrix covers fixed-source admission for all three worktrees, runtime content
and identity drift, consumed native claims, safe NO_SIGNAL / RISK_REJECTED /
PAPER_EXECUTED counters, invalid child artifacts, restart reconciliation, bounded
waiting, NYSE DST/holiday/early-close selection and closed CLI selectors. Journal
verification includes O_EXCL, flush/fsync/readback, stable file identity, attempt
limits and lifetime-lock exclusion. Windows pathname and opened-handle timestamps
are compared within their respective namespaces because Windows reports distinct
creation/change-time values through lstat and fstat.

Publication requires the complete affected checkpoint-runner `test_ci.py`, focused
successor-overlay regressions, touched Ruff check and format-check, diff checks,
exact-file atomic commit/push, and terminal mapped CI. The full ROBINHOOD profile
belongs to GitHub. Actual PC-ON logon/restart, native scheduler normalization and
protected child execution require a subsequent distinct reviewed host boundary;
source tests cannot certify those real effects. Zero real protected effects have
been performed by this source implementation checkpoint.

Final local focused results: 136 supervisor cases plus the two corrected explicit
profile-inventory cases passed (138 total); the complete affected
`tests/runtime/checkpoint_runner/test_ci.py` passed all 97 cases. Changed current
successor assertions were exercised with exact function selectors; the detected
positional/module-inventory assertions were corrected and their affected cases
retested. Both touched Ruff phases passed for 30 Python files; the PowerShell
adapter parsed without execution; `git diff --check` passed. The source authority
chain passed with all 69 frozen predecessor dictionary digests unchanged. Local
iteration failures are not CI attempts and no broad local profile was run.

## Corrective checkpoint D1R9-C1

Implementation `776d68d6b529a665d9d6e3670298687add3d8f1a`, tree
`d94640c2758609f3861f458e1fa672b0dcc6a718`, reached terminal failure in
Checkpoint Source Gates #605 / 39019001334 / push / attempt 1. Source-static
passed; active tests reported 3318 passed / 5 skipped / 35 failed. Canonical
ROBINHOOD reported 10325 cases: 10284 passed / 6 skipped / 35 failed / 0 errors,
wall 293.795 seconds (hygiene passed). Both jobs exposed the same test-only
failures: 33 source-admission fake cases depended on the local fixed F: roots
and interpreter; two retained registration assertions omitted D1R9. Original
failed CI artifacts and source remain preserved; no rerun/amend/rewrite occurs.

C1 replaces only those fake root/interpreter bindings and stale registration
assertions and refreshes the D1R9-owned source/test pins. It changes no runtime,
authority, ordering, scheduler, child, protected-effect or workflow semantics.
All predecessor dictionaries/digests and accepted child refs/executables remain
frozen. Focused affected tests and static checks precede one new atomic ordinary
push and its fresh mapped canonical CI run. No real protected effect is invoked.

C1 focused final result: all 35 exact failed cases passed. No broad local
certification was run; the replacement mapped run remains GitHub-owned.

## Corrective checkpoint D1R9-C2

The bounded read-only Windows host-readiness observation against the accepted
D1R9 source passed source, predecessor, runtime and prospective-slot admission,
but the exact D1R9 scheduler observer returned `{"status":"BLOCKED"}` with
exit code 2. A separate read-only COM diagnostic established that the Schedule
service, COM connection and root folder were healthy, while lookup of
`AITradingBot-Arch134-D1R9-OneSessionSupervisor-v1` raised
`System.IO.FileNotFoundException` with HResult `-2147024894`
(`0x80070002`). The task was therefore genuinely absent; no scheduler effect
occurred.

C2 changes only the missing-task classification in
`scripts/arch134_d1r9_scheduler.ps1`. Its bounded
`Test-TaskNotFoundException` helper inspects the caught exception and at most 32
inner exceptions for the exact HResult. It does not inspect localized message
text, and all other observation failures remain fail-closed as
`{"status":"BLOCKED"}` with exit code 2. Task shape, scheduler identity,
Create/Run behavior, supervisor authority, child boundaries, evidence and
effect ceilings remain unchanged.

Focused source tests exercise direct and nested `FileNotFoundException`
instances, intermediate-chain matches, nonmatching HResults, message-only
lookalikes and excessive-depth traversal through a PowerShell AST harness that
never invokes Task Scheduler. The C2 checkpoint performs no real Observe,
Create, Run, scheduler mutation, journal reservation, child entry, credential,
provider, paper, broker, ACL, D2 or live effect.
