# AI Trading Bot - Current Handoff

## Current mode

**ARCHITECTURE 144-A+B SOURCE ACCEPTED; ARCHITECTURE 134-F1 SOURCE ACCEPTED;
ARCHITECTURE 144-C IMPLEMENTATION CANDIDATE; EXACT-SOURCE REVIEW PENDING.
PROTECTED 134-F PREFLIGHT AND THE REAL SOAK REMAIN CLOSED.**

Standing workflow authority remains `AGENTS.md` and
`docs/AI_DEVELOPMENT_WORKFLOW.md`.

## Current integration identity

```text
develop HEAD f47deac55e22f5a1f215bed69b3429038d7babb0
develop TREE 6a5e3319729e2d1e4b034631dd1d2edb99ccaa4f
```

Integration source-gate #650 / 39403544950 passed. Its four `full-tests` jobs
were routine broad source-gate shards, not canonical FULL.

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

## Architecture 144-C frozen design

Canonical design:

- `docs/architecture/144-c-f1-paper-evidence-admission.md`;
- `docs/validation/arch144-c-f1-paper-evidence-admission-plan.md`.

144-C adds separate pure V2 observation/eligibility artifacts for truthful F1
provenance while preserving v1 byte-for-byte.

Key rules:

- F1 evidence continues to fail the v1 D1R9 binding;
- V2 pins exact accepted F1 HEAD/TREE and parent/child provenance;
- V2 independently verifies supplied F1 parent/child plus D1R7/D1R8 bytes;
- the complete Architecture-142/143 chain remains required;
- the unchanged v1 five-session policy is reused;
- exactly five consecutive published sessions and at least one
  `PAPER_EXECUTED` are required for positive eligibility;
- `RISK_REJECTED` may be verified but is nonqualifying;
- `SESSION_MISSED`, `BLOCKED`, and `INDETERMINATE` create no positive V2
  observation;
- no filesystem evidence acquisition or operational effect is permitted.

## Immediate next milestone - Architecture 144-C exact-source review

Implementation owner/model: **Codex / Sol High**. Next owner: **ChatGPT** for
exact-source acceptance and certification selection.

Expected branch:

`feature/test-suite-arch144-c-f1-paper-evidence-admission-current`

Expected worktree:

`F:\AI\worktrees\ai-trading-bot-arch144-c-f1-paper-evidence-admission-current`

Primary new source/tests:

```text
src/trading_bot/experiments/research_strategy_paper_candidate_eligibility_v2.py
src/trading_bot/experiments/research_strategy_f1_paper_evidence_verification.py
tests/experiments/test_research_strategy_paper_candidate_eligibility_v2.py
tests/experiments/test_research_strategy_f1_paper_evidence_verification.py
```

Checkpoint:

`arch144-c-f1-paper-evidence-admission`

Authority:

```text
preflight None
execute   None
```

The branch is already covered by the reviewed `feature/test-suite-*` source-gate
family. Do not pre-map ROBINHOOD or FULL. Run focused verification, compose all
predictable runner/inventory/pin/status/handoff changes, exact-file stage, make
one atomic commit, ordinary-push once, and poll the single push-triggered source
gate to terminal.

Codex does not own architecture, source acceptance, certification selection,
merge readiness, or protected-effect authority.

## Protected boundary after 144-C

Only after 144-C source acceptance may ChatGPT review the separate 134-F
protected preflight/readiness boundary.

That later review does not imply retry authority, task creation, provider access,
paper effects, or the real soak until its exact protected command and
prerequisites are separately established.

Real-money trading remains **NO-GO**.

## Required continuation

The implementation candidate adds the independent supplied-byte F1 V2 replay and
positive builders, strict V2 artifacts, and a source-only registered checkpoint.
Both frozen Architecture-144 v1 implementation blobs remain unchanged.

Obtain terminal source-gate evidence and review the exact feature HEAD/TREE,
complete diff, focused results and CI. ChatGPT owns source acceptance and any
additional certification selection. Do not merge or begin protected preflight.
No canonical ROBINHOOD/FULL mapping or local profile run is part of this checkpoint.
