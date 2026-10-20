# AI Trading Bot - Current Handoff

## Current mode

**ARCHITECTURE 144-A+B SOURCE ACCEPTED; ARCHITECTURE 134-F1 SOURCE ACCEPTED;
ARCHITECTURE 144-C SOURCE ACCEPTED AND INTEGRATED.
134-F2 IMPLEMENTATION PREPARED; EXACT-SOURCE/CI REVIEW PENDING;
NO OPERATIONAL EFFECT IS AUTHORIZED.**

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

## Architecture 134-F2 design freeze

The read-only review established that the accepted F1 checkpoint has no
registered preflight and that no complete F1 readiness command currently exists.

Canonical F2 design:

- `docs/architecture/134-f2-five-session-live-paper-soak-readiness.md`;
- `docs/validation/arch134-f2-five-session-live-paper-soak-readiness.md`.

F2 is source-only implementation of a registered read-only readiness callback.

```text
branch
feature/robinhood-production-paper-134f2-five-session-soak-readiness

worktree
F:\AI\worktrees\ai-trading-bot-production-paper-134f2-five-session-soak-readiness

checkpoint
arch134-f2-five-session-soak-readiness

preflight
implemented read-only callback

execute
None

CI profile
robinhood
```

READY requires frozen F1/D1R7/D1R8 source admission, accepted predecessor
evidence, read-only runtime compatibility, untouched F1 authority namespace,
scheduler ABSENT, five-session preview and final readmission. Credentials,
providers and write-readiness remain NOT_CHECKED.

## Immediate next milestone - Architecture 134-F2 exact-source review

Owner: **ChatGPT**.

The frozen F2 read-only callback, focused fake/static/disposable coverage and
runner/profile/current-inventory/pin metadata are implemented. All seven F1
operational blobs remain frozen. F1 remains `preflight=None`, `execute=None`;
F2 is `preflight=_arch134_f2_preflight`, `execute=None` and CI `robinhood`.

Base HEAD/TREE are `9310eec609fcd273d9e248c4e897fe7e5828f953` /
`dbac92b55169b3a21d1ebee046755707be40f1eb`. This source record does not claim
acceptance or a terminal CI outcome for the unpublished source checkpoint.

The implementing agent completes focused checks, creates one normal unpublished
commit, runs `.\ops.ps1 verify arch134-f2-five-session-soak-readiness` on the
clean commit, and ordinary-pushes once. That push owns terminal active checks
plus canonical ROBINHOOD. Do not duplicate ROBINHOOD locally or run FULL.

ChatGPT must inspect the initial commit plus separate C1, source pins, registered verify
report and terminal CI/canonical evidence. Stop on mismatch or failure. Source
acceptance may open only the separately reviewed read-only F2 preflight.

The real F2 preflight has not run. No task, parent/child/claim/lock, credential,
provider, D1R7/D1R8, runtime-write, paper/session, broker or soak effect has run
as part of implementation. Allowed observations and zero effects are separate
fields in the F2 closed result.

## Protected boundary after 144-C

144-C acceptance opens only the **review** of the separate 134-F protected
preflight/readiness boundary.

A future exact preflight command, if source-reviewed and separately authorized,
may inspect only its frozen bounded prerequisites. Passing such a preflight still
does not authorize the five-session soak. Task creation/run, provider access,
paper effects and the real soak remain separately protected.

Real-money trading remains **NO-GO**.

## Required continuation

Review the implemented Architecture 134-F2 feature after terminal CI. Return
the exact feature HEAD/TREE, changed paths, focused verification and canonical
ROBINHOOD evidence for ChatGPT exact-source review.

Only after F2 source acceptance may the registered read-only preflight be run.
A preflight PASS still does not authorize the F1 five-session soak.

Do not retry the consumed D1R9 authority and do not begin the real soak.
Real-money trading remains **NO-GO**.

## F2 failed attempt and bounded C1

Initial F2 source `dd6a822d20b3b42a6c61eb5241fc6d5c6045521e` / tree
`f2da182ef547f43f38d8f2af5afc43356e3ef1f2` passed its registered local gate
(1,031 cases), source-static and active CI. Canonical ROBINHOOD #656 /
39498692559 / attempt 1 failed four stale runner-pin/historical-expectation
assertions: 104 modules, 10,662 cases, 10,652 passed, six skipped, four failed,
zero errors; wall 282.215 seconds. The failed run and artifact remain preserved.

Separate bounded C1 updates the installation gate's exact read-only preflight
AST pin and the retired recovery test's expected drift set. A new proof removes
only the two F2-only branches and requires the exact frozen non-F2 predecessor
AST. The F2 focused gate now includes all three affected installation/recovery
modules and installation source authority. No F2 runtime behavior, protected
execute behavior, F1 operational blob, ownership baseline or lane policy changes.

C1 has its own focused checks and atomic normal commit/push; it never amends or
reruns the failed attempt. Replacement CI/source acceptance remain pending in
this source record. No real F2 preflight, soak or operational effect is authorized.
