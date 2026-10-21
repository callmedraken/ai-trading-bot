# AI Trading Bot - Current Handoff

## Current mode

**ARCHITECTURE 144-A+B SOURCE ACCEPTED; ARCHITECTURE 134-F1 SOURCE ACCEPTED;
ARCHITECTURE 144-C SOURCE ACCEPTED AND INTEGRATED; ARCHITECTURE 134-F2 SOURCE ACCEPTED.
F2 READ-ONLY PREFLIGHT PASSED; F1 FIVE-SESSION SOAK IS AUTHORIZED AND ACTIVE.
REAL-MONEY TRADING REMAINS NO-GO.**

Standing workflow authority remains `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`.

## Accepted executable integration identity

```text
develop HEAD d4d007a5c4a7c6a5158b1fab6f82c082387783f3
develop TREE 47f13748c89784fddf0ef981072a7b23f7d02f22
```

Integration source-gate #653 / 39490843514 / attempt 1 / SUCCESS. The merge tree
is byte-identical to the accepted 144-C feature tree. Its four `full-tests`
jobs were routine broad develop shards, not canonical FULL; active/canonical
certification were correctly skipped.

## Accepted Architecture 144 v1

```text
branch feature/test-suite-arch144-research-paper-eligibility-current
HEAD   20219f65e59dc91287462490d85f41b8fdb2a97e
TREE   a9e0b6fe7b85dbaeef8b3f46f5276483ec6b93bd
CI     #643 / 39386250794 / SUCCESS
FULL   187 modules / 12,436 cases / 12,433 passed / 3 skipped
```

Architecture-144 v1 is frozen. Do not modify its accepted eligibility or
evidence-verifier modules as part of 144-C.

## Accepted Architecture 134-F1

```text
branch feature/robinhood-production-paper-134f-five-session-soak
HEAD   b59ad3b44540a55a30f612d5c4e3e38e26a95b02
TREE   e8a94e3512d7950f2fbc9c4d102a58b63e03244f
CI     canonical ROBINHOOD #649 / 39401319643 / SUCCESS
```

F1 is source accepted. Its initial #648 failure remains preserved; bounded C1
changed no F1 production module.

No real scheduler/provider/credential/D1R7/D1R8/D1R9/paper/broker/promotion/live
effect occurred during F1 source work or integration.

## Accepted Architecture 144-C

```text
branch feature/test-suite-arch144-c-f1-paper-evidence-admission-current
base   c2072179a50b3e8b441b447b18284f0dc2040d88
HEAD   1e86b5dcce19cd45504266b4fa0ac0aca5854d04
TREE   47f13748c89784fddf0ef981072a7b23f7d02f22
CI     #652 / 39410467329 / attempt 1 / SUCCESS
```

Architecture 144-C is **SOURCE ACCEPTED**. No additional canonical
ROBINHOOD/FULL was required.

It adds separate pure V2 observation/eligibility artifacts for truthful F1
provenance while preserving v1 byte-for-byte. The accepted verifier independently
replays supplied F1 parent/child plus D1R7/D1R8 bytes, requires the complete
Architecture-142/143 chain, keeps the unchanged v1 five-session policy, and has
no filesystem acquisition or operational capability.

Frozen v1 blobs remain:

```text
research_strategy_paper_candidate_eligibility.py
fd6b0ad650fb3fb97f587deb7cffc7286e685813

research_strategy_paper_evidence_verification.py
915bdd84bee3ad0b57efcafb0a78da01fce94e66
```

## Accepted Architecture 134-F2

```text
branch feature/robinhood-production-paper-134f2-five-session-soak-readiness
base   9310eec609fcd273d9e248c4e897fe7e5828f953
HEAD   2737f950beb4dd0ba75016ecb544576e1046f86f
TREE   3445945966ad03c5fb399ae890fa48069a896641
```

Initial source `dd6a822d20b3b42a6c61eb5241fc6d5c6045521e` preserved canonical
ROBINHOOD #656 / 39498692559 failure evidence: 104 modules, 10,662 cases,
10,652 passed, six skipped, four failed, zero errors, wall 282.215 s.

Separate bounded C1 `2737f950...` did not change the F2 runtime implementation
blob. It corrected shared-runner pin/historical expectations and added the
frozen-predecessor AST proof.

Final canonical ROBINHOOD #657 / 39501375087 / attempt 1 passed:

```text
104 modules
10,663 cases
10,657 passed
6 skipped
0 failed
0 errors
203.470 s wall
```

All seven frozen F1 blobs remain exact. F1 remains
`preflight=None/execute=None`. F2 is
`preflight=_arch134_f2_preflight/execute=None`.

The F2 callback admits only read-only observations: exact source/worktree state,
bounded predecessor evidence, read-only runtime compatibility, untouched F1
namespace, scheduler `ABSENT`, preview targets and final readmission. Credential,
provider and write-readiness remain `NOT_CHECKED`; all effect counters are
required zero.

## Active operational state — Architecture 134-F1 soak

The real F2 read-only preflight passed once on the accepted F2 source:

```text
HEAD     2737f950beb4dd0ba75016ecb544576e1046f86f
TREE     3445945966ad03c5fb399ae890fa48069a896641
result   READY_FOR_SEPARATE_F1_AUTHORIZATION
evidence F:\AI\temp\ai-trading-bot-checkpoints\arch134-f2-five-session-soak-readiness\preflight-20261020T220328.998747Z\report.json
sha256   973ce41d5ec09e0b603aedfbd2001d3a50bc1117d93002291b46e0006fdd1a5d
```

It observed exact F1/D1R7/D1R8 source, accepted predecessors,
`PRESENT_COMPATIBLE` runtime, scheduler `ABSENT`, no F1 namespace artifacts,
and zero for all 21 protected-effect counters.

The subsequent exact interactive F1 authorization succeeded and printed
`AUTHORIZED_FIVE_SESSION_TASK_STARTED`. The one parent authority is consumed.
The frozen target sessions are 2026-10-21, 2026-10-22, 2026-10-23, 2026-10-26,
and 2026-10-27. Do not authorize a second F1 series or manufacture retries.

### Restart behavior during F1

F1 deliberately uses a current-user logon-triggered Task Scheduler action that
runs the fixed launcher with `--resume`. Therefore a reboot followed by login
may automatically resume the active soak. Resume is not fresh authority: it must
reconcile durable parent/child/source/runtime state before progression and it may
not exceed the frozen effect ceilings. If the machine stays down long enough to
miss a target session, the series halts with no catch-up/backfill.

This is a soak/restart-reliability mechanism, not the target production UX.

### Frozen future production operator requirement

`docs/architecture/134-production-operator-lifecycle-reboot-stop.md` freezes
the desired production lifecycle:

- intentional OS shutdown/reboot means **stop the bot**;
- Windows boot/logon must not automatically resume trading;
- durable state is preserved and may be inspected/reconciled read-only after boot;
- resuming trading requires a fresh explicit operator start after reboot;
- the active F1 auto-resume behavior must not be copied into the final production
  scheduler/launcher design.

## Revised strategy qualification direction

The active F1 five-session soak remains important, but only as an operational
soak: scheduler/restart behavior, durable authority, provider integration,
session handling and paper execution plumbing. Its P&L is not the project's main
strategy-quality signal.

The preferred research-to-live progression is now:

```text
extensive historical backtests
-> walk-forward / out-of-sample qualification
-> parameter/regime stability
-> conservative execution stress, including fill delay/miss/reject modeling
-> sealed final holdout
-> inert LIVE_CANARY_ELIGIBLE evidence
-> separately reviewed tiny-capital live canary
-> real fill/slippage/reject/reconciliation measurement
-> later gradual scaling review
```

Architecture 144-C remains frozen and useful for F1 provenance. It does not need
to become a months-long paper-profitability program. Extended paper trading is
diagnostic, not the default promotion path.

The next safe parallel source milestone is **Architecture 145 / RCL-8**, frozen
in `docs/architecture/145-backtest-robustness-live-canary-eligibility.md` and
its validation plan. It is offline/source-only and cannot authorize real money.

## Protected boundary after 144-C

144-C acceptance opens only the **review** of the separate 134-F protected
preflight/readiness boundary.

A future exact preflight command, if source-reviewed and separately authorized,
may inspect only its frozen bounded prerequisites. Passing such a preflight still
does not authorize the five-session soak. Task creation/run, provider access,
paper effects and the real soak remain separately protected.

Real-money trading remains **NO-GO**.

## Required continuation

Keep the current F1 authority running under its accepted five-session contract.
Do not re-authorize or retry the parent. Read-only status/reconciliation is the
next safe operator action.

A reboot during F1 is permitted and may auto-resume after user logon. Treat that
as deliberate soak-test behavior only. For future production, preserve the
separate reboot=stop/manual-start requirement frozen in
`docs/architecture/134-production-operator-lifecycle-reboot-stop.md`.

While F1 continues, implement Architecture 145 / RCL-8 in an isolated research
worktree with zero access to the active F1 operational namespace. After F1
reaches terminal state, independently reconcile its evidence and run the pure
Architecture-144-C V2 evaluation for provenance/operational qualification.

Do not treat a five-day or longer paper P&L series as the main profitability
gate. Strategy-quality evidence should come primarily from the frozen 145
historical/walk-forward/stress/holdout path. Any real-money test remains a later,
separately reviewed tiny-capital live-canary authority.

Real-money trading remains **NO-GO**.
