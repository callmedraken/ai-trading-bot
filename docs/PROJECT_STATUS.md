# AI Trading Bot - Project Status

## Current verified checkpoint

Architecture 144-A+B / RCL-7, Architecture 134-F1, Architecture 144-C, and Architecture 134-F2 are **SOURCE ACCEPTED**.

Accepted Architecture-144 v1 source:

```text
branch  feature/test-suite-arch144-research-paper-eligibility-current
HEAD    20219f65e59dc91287462490d85f41b8fdb2a97e
TREE    a9e0b6fe7b85dbaeef8b3f46f5276483ec6b93bd
CI      Checkpoint Source Gates #643 / 39386250794 / SUCCESS
```

Its final canonical FULL passed on the exact source:

```text
modules 187
cases   12,436
passed  12,433
skipped 3
failed  0
errors  0
wall    256.955 s
```

Do not repeat FULL or add redundant ROBINHOOD coverage on unchanged v1 source.

Accepted Architecture 134-F1 source:

```text
branch  feature/robinhood-production-paper-134f-five-session-soak
base    b3b605fdc0886cd90367027e72d43ecaf8ce5b4c
HEAD    b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE    e8a94e3512d7950f2fbc9c4d102a58b63e03244f
```

Canonical ROBINHOOD #649 / 39401319643 passed on that exact F1 source:

```text
modules 103
cases   10,422
passed  10,416
skipped 6
failed  0
errors  0
wall    287.894 s
```

The initial #648 failure remains preserved. Its eight failures were stale
test-only registry/successor expectations; C1 changed no F1 production module.
Architecture-144 v1 remained byte-for-byte unchanged.

## Architecture 134-F2 operational PASS and active F1 soak

The separately reviewed real Architecture 134-F2 read-only preflight ran once on
2026-10-20 against exact source
`2737f950beb4dd0ba75016ecb544576e1046f86f / 3445945966ad03c5fb399ae890fa48069a896641`
and returned `PASS / READY_FOR_SEPARATE_F1_AUTHORIZATION`.

Preserved evidence:

```text
F:\AI\temp\ai-trading-bot-checkpoints\arch134-f2-five-session-soak-readiness\preflight-20261020T220328.998747Z\report.json
SHA256 973ce41d5ec09e0b603aedfbd2001d3a50bc1117d93002291b46e0006fdd1a5d
```

The report re-admitted exact F1/D1R7/D1R8 source, accepted predecessor evidence,
`PRESENT_COMPATIBLE` runtime, an empty F1 parent/child/claim/lock namespace and
scheduler `ABSENT`. Credentials, provider readiness and runtime write-readiness
remained deliberately `NOT_CHECKED`. All 21 protected-effect counters were
zero. The frozen target window is:

```text
2026-10-21
2026-10-22
2026-10-23
2026-10-26
2026-10-27
```

The separately reviewed interactive F1 authorization then succeeded against exact
accepted F1 source
`b59ad3b44540a55a30f612d5c4e3e38e26a95b02 / e8a94e3512d7950f2fbc9c4d102a58b63e03244f`
and returned `AUTHORIZED_FIVE_SESSION_TASK_STARTED`. The single F1 parent
authority is therefore consumed and active. Automatic retry/re-authorization is
not permitted.

During this F1 soak only, a Windows reboot followed by current-user logon may
automatically invoke the fixed scheduler action with `--resume`. Resume must
first reconcile the durable parent/child/source/runtime state and cannot increase
the frozen effect ceilings. If a target session is missed, or an effect intent is
ambiguous, the series halts rather than backfilling or retrying.

This F1 restart behavior is test-specific and is **not** the desired final
production operator lifecycle. The future production requirement is frozen in
`docs/architecture/134-production-operator-lifecycle-reboot-stop.md`: an
intentional OS shutdown/restart means the bot is stopped, boot/logon must not
automatically resume trading, and a fresh explicit operator start is required
after reboot.

Accepted executable integration state:

```text
develop HEAD d4d007a5c4a7c6a5158b1fab6f82c082387783f3
develop TREE 47f13748c89784fddf0ef981072a7b23f7d02f22
```

Integration source-gate #653 / 39490843514 / attempt 1 passed on the exact
accepted 144-C tree. Its four `full-tests` jobs were normal broad develop
source-gate shards, not a canonical FULL certification; active and canonical
certification jobs were correctly skipped.

## Accepted Architecture 144-C

Architecture 144-C is **SOURCE ACCEPTED AND INTEGRATED**.

Accepted feature source:

```text
branch  feature/test-suite-arch144-c-f1-paper-evidence-admission-current
base    c2072179a50b3e8b441b447b18284f0dc2040d88
HEAD    1e86b5dcce19cd45504266b4fa0ac0aca5854d04
TREE    47f13748c89784fddf0ef981072a7b23f7d02f22
CI      Checkpoint Source Gates #652 / 39410467329 / attempt 1 / SUCCESS
```

ChatGPT independently reviewed the exact one-commit 29-path diff, V2
identity/canonicalization, independent supplied-byte F1/D1R7/D1R8 replay,
complete Architecture-142/143 composition, zero operational capability, frozen
v1 blobs, checkpoint registration and terminal CI.

The frozen v1 implementation blobs remain unchanged:

```text
research_strategy_paper_candidate_eligibility.py
fd6b0ad650fb3fb97f587deb7cffc7286e685813

research_strategy_paper_evidence_verification.py
915bdd84bee3ad0b57efcafb0a78da01fce94e66
```

No additional canonical ROBINHOOD/FULL was selected because 144-C is an additive
pure evidence-admission successor and the exact final tree already passed its
focused/active and broad source-gate coverage. Source acceptance does not grant
scheduler/provider/credential/paper/broker/promotion/live authority.

Canonical design remains:

- `docs/architecture/144-c-f1-paper-evidence-admission.md`;
- `docs/validation/arch144-c-f1-paper-evidence-admission-plan.md`.

## Paper-operational readiness

Architecture 134-E's accepted Monday 2026-10-19 D1R9 `FINAL / NO_SIGNAL`
proved one unattended integration session and is consumed.

Architecture 134-F1 now supplies the accepted five-session current-product source
authority, but the real five-session soak remains a separately reviewed
protected effect.

Required sequence:

```text
144-C source accepted and integrated
-> separate 134-F protected preflight/readiness design + read-only review
-> only then an exact separately authorized protected preflight command
-> only after that boundary passes, separately admit the real five-session soak
-> end-of-window reconciliation
-> pure V2 eligibility evaluation
```

The v1 policy remains:

```text
required_session_count = 5
required_paper_executed_count = 1
require_consecutive_published_regular_sessions = true
qualifying_terminal_classifications = ("NO_SIGNAL", "PAPER_EXECUTED")
```

Five sessions are an eligibility boundary, not enough evidence by themselves to
establish long-run profitability.

## Protected and safety boundaries

- Real-money trading remains **NO-GO**.
- The Monday D1R9 authority remains consumed and is not retried.
- The F2 read-only preflight has passed and is consumed as readiness evidence.
- The F1 five-session soak is now authorized and active; the parent slot is consumed.
- Do not re-authorize, retry, delete/replace F1 artifacts, or recreate the task to manufacture another attempt.
- No source/CI/FULL/ROBINHOOD result grants scheduler/provider/credential/paper,
  broker, promotion, D2, or live authority.
- `PAPER_CANDIDATE` materialization and human promotion remain later explicit
  architectures.

## Accepted Architecture 134-F2

Architecture 134-F2 is **SOURCE ACCEPTED** on its isolated feature branch.

```text
branch  feature/robinhood-production-paper-134f2-five-session-soak-readiness
base    9310eec609fcd273d9e248c4e897fe7e5828f953
HEAD    2737f950beb4dd0ba75016ecb544576e1046f86f
TREE    3445945966ad03c5fb399ae890fa48069a896641
```

The accepted source consists of two commits above the frozen design base:

```text
dd6a822d20b3b42a6c61eb5241fc6d5c6045521e
feat: add read-only five-session soak readiness preflight

2737f950beb4dd0ba75016ecb544576e1046f86f
fix: align F2 preflight authority pins and historical assertions
```

The initial publication's canonical ROBINHOOD #656 / 39498692559 / attempt 1 is
preserved as a failed checkpoint attempt: 104 modules, 10,662 cases, 10,652
passed, six skipped, four failed, zero errors, wall 282.215 s. Source-static and
the active F2 checkpoint passed; the four failures were stale shared-runner
pin/historical-expectation assertions.

Bounded C1 changed no F2 runtime implementation. It updated only current docs,
runner pin/coverage metadata, the F2 frozen-predecessor AST proof and one
historical recovery expectation. The F2 implementation blob is identical across
both commits:

```text
src/trading_bot/review_paper/five_session_soak_readiness.py
6b9196a7812bf854ac55d443cbd3d34b979de2d8
```

C1's AST proof removes only the two F2-specific branches from
`preflight_checkpoint` and requires the reconstructed non-F2 predecessor to
hash exactly to the preserved historical pin.

Canonical ROBINHOOD #657 / 39501375087 / attempt 1 passed on the exact final
HEAD/TREE:

```text
modules 104
cases   10,663
passed  10,657
skipped 6
failed  0
errors  0
wall    203.470 s
```

Source-static, active-tests, canonical ROBINHOOD and the terminal source-gates
aggregator all passed; `full-tests` was correctly skipped.

All seven frozen F1 operational blobs remain exact. F1 remains
`preflight=None`, `execute=None`. F2 is registered with the read-only
`_arch134_f2_preflight`, `execute=None`, and CI profile `robinhood`.

The real F2 preflight has **not** run. No F1 parent/child/claim/lock, scheduler
mutation, credential/provider access, runtime write probe, D1R7/D1R8 operation,
paper/session mutation, broker effect or soak effect occurred.

## Active work

### Now — Architecture 134-F1 five-session soak active

The current protected objective is to let the accepted F1 authority progress
through its five frozen published sessions while preserving the no-retry,
no-backfill and exact durable-reconciliation contract.

A PC reboot is allowed during F1. After the same user logs in, the fixed logon
trigger may automatically start `run_arch134_f1.py --resume`. That automatic
resume exists to test restart/idempotency behavior across the soak and must not
be generalized into the future production lifecycle.

Owner: **runtime / accepted F1 source**. ChatGPT owns read-only review and
classification of preserved evidence. No new source/CI checkpoint is required
merely because the supervisor remains active.

### Next

Use only read-only status/reconciliation observations while the soak is active.
Do not run F1 authorization again. A reboot, process restart, or scheduler restart
does not grant new authority; it must reconcile the already-consumed durable
parent state. A missed session halts the series and is never replaced.

After the five-session parent reaches a terminal state, perform independent
end-of-window reconciliation and then the pure Architecture-144-C V2 eligibility
evaluation. Five sessions remain an operational/eligibility threshold, not a
profitability conclusion.

### Future production lifecycle

Before the bot is treated as an operator-facing production deployment, implement
and source-review the reboot/stop requirement frozen in
`docs/architecture/134-production-operator-lifecycle-reboot-stop.md`.
Shutdown/reboot must leave the bot stopped after boot; resuming trading requires
a new explicit operator start after state reconciliation. F1's automatic
logon-resume mechanism is a soak-only exception.

## History

Use `docs/history/INDEX.md` only for targeted historical reconstruction.
