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
- 134-F protected preflight/readiness is now the next review boundary, but no protected command or operational effect is authorized yet.
- The real five-session soak is closed.
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

### Now — workflow CI-efficiency correction recorded; protected boundary remains stopped

The F2 exact-source review is complete. The next operational boundary is the
separately reviewed **read-only** F2 host preflight, but it is not run as part of
source acceptance or this documentation closeout.

The workflow review identified avoidable CI amplification:

- mutable `PROJECT_STATUS` / `AI_TRADING_BOT_HANDOFF` closeouts must remain
  true docs-only updates and must not force Python runner pin refreshes merely to
  record current state;
- when ChatGPT immediately knows the next design-only milestone before publishing
  an acceptance closeout, batch the acceptance closeout and that design freeze
  into one docs-only branch advance rather than two sequential CI-triggering
  commits;
- any shared `checkpoint_runner.py` dispatch/function change must audit all
  current AST/pin consumers and include affected historical/current tests in
  focused verification before the first publication.

These rules are recorded in `docs/AI_DEVELOPMENT_WORKFLOW.md`. Existing
legacy mutable-doc pin coupling should be removed only in the next already-needed
runner-touch source checkpoint rather than creating a standalone certification
cycle solely for cleanup.

### Next

Review the exact F2 preflight operator boundary from the accepted feature source.
Do not execute it in this closeout. If/when separately authorized, synchronize
the exact accepted F2 worktree first, then run only the registered read-only
preflight and return its preserved evidence for ChatGPT review.

### Later

Only after a reviewed F2 preflight PASS may an exact interactive F1 authorization
be separately proposed. That future command is the first authority-consuming
boundary and remains separately protected. The real five-session soak and all
provider/paper effects remain closed now.

## History

Use `docs/history/INDEX.md` only for targeted historical reconstruction.
