# AI Trading Bot - Current Handoff

## Current mode

**ARCHITECTURE 144-A+B SOURCE ACCEPTED; ARCHITECTURE 134-F1 SOURCE ACCEPTED;
ARCHITECTURE 144-C SOURCE ACCEPTED AND INTEGRATED.
134-F PROTECTED PREFLIGHT/READINESS REVIEW IS NEXT; NO OPERATIONAL EFFECT IS AUTHORIZED.**

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

## Immediate next milestone - Architecture 134-F2 source implementation

Owner/model: **Codex / Sol High**.

Implement only the frozen F2 read-only preflight boundary and its focused
fake/static tests plus required runner/profile/current-inventory/pin metadata.
Do not modify the seven frozen F1 operational blobs.

The source implementation must not run the real F2 preflight, create/run a task,
reserve a parent/child/claim/lock, read credentials, call providers, invoke
D1R7/D1R8, probe runtime writes, mutate paper/session state, or begin the soak.

Use focused tests and `.\ops.ps1 verify arch134-f2-five-session-soak-readiness`,
then one exact-file atomic commit/push. The one push-triggered CI owns canonical
ROBINHOOD; no duplicate local ROBINHOOD/FULL.

## Protected boundary after 144-C

144-C acceptance opens only the **review** of the separate 134-F protected
preflight/readiness boundary.

A future exact preflight command, if source-reviewed and separately authorized,
may inspect only its frozen bounded prerequisites. Passing such a preflight still
does not authorize the five-session soak. Task creation/run, provider access,
paper effects and the real soak remain separately protected.

Real-money trading remains **NO-GO**.

## Required continuation

Implement Architecture 134-F2 from the frozen design. After terminal CI, return
the exact feature HEAD/TREE, changed paths, focused verification and canonical
ROBINHOOD evidence for ChatGPT exact-source review.

Only after F2 source acceptance may the registered read-only preflight be run.
A preflight PASS still does not authorize the F1 five-session soak.

Do not retry the consumed D1R9 authority and do not begin the real soak.
Real-money trading remains **NO-GO**.
