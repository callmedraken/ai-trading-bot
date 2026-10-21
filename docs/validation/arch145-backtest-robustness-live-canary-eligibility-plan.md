# Architecture 145 / RCL-8 — robust historical qualification validation plan

Status: **DESIGN FROZEN; source implementation is next.**

## Acceptance objective

Prove that Architecture 145 can deterministically qualify or reject one exact
strategy candidate from historical/walk-forward/stress/holdout evidence without
network, broker, paper, scheduler, credential or active-F1 effects.

## Required focused coverage

Tests must prove:

- additive successor schemas; accepted 137/138/142/143/144/144-C artifacts remain
  byte/behavior frozen unless an explicitly reviewed compatibility export is
  required;
- canonical policy identity changes for every semantic policy field;
- no policy or threshold can be changed after sealed-holdout admission;
- no holdout information is available to development/optimization paths;
- repeated attempt to evaluate a consumed holdout for the same frozen candidate
  version is rejected or deterministically reproduces the same immutable result
  without creating new selection authority;
- walk-forward folds remain out-of-sample and no-lookahead;
- parameter-neighborhood and time-window sensitivity are explicitly evaluated;
- insufficient sample/trade count fails closed;
- excessive drawdown fails closed;
- insufficient after-cost performance fails closed;
- unstable walk-forward evidence fails closed;
- each frozen execution-stress scenario is required and independently bound;
- missing/reordered/duplicate stress evidence fails closed;
- delayed-fill, increased-cost, miss/reject and supported partial-fill scenarios
  reconcile final cash/positions/equity;
- one passing baseline with failing required stress cannot produce positive
  eligibility;
- final holdout must pass every frozen positive criterion;
- canonical serialization and source/data/policy provenance are independently
  verifiable;
- malformed, unknown, noncanonical, NaN/nonfinite, float-for-Decimal, source-drift
  and provenance-drift inputs fail closed.

## Purity boundary

Focused/static tests must establish zero capability for:

```text
F1_NAMESPACE_READS
F1_NAMESPACE_WRITES
PRODUCTION_SQLITE_READS
PRODUCTION_SQLITE_WRITES
CREDENTIAL_READS
CREDENTIAL_WRITES
PROVIDER_CALLS
BROKER_CALLS
SCHEDULER_CALLS
PAPER_MUTATIONS
D1_OPERATIONS
D2_OPERATIONS
STRATEGY_PROMOTIONS
REAL_MONEY_EFFECTS
```

No test may depend on the currently active F1 soak's real files.

## Publication

Expected branch:

`feature/research-backtest-robustness-live-canary-eligibility-current`

Expected worktree:

`F:\AI\worktrees\ai-trading-bot-research-backtest-robustness-live-canary-eligibility-current`

Use focused tests plus the unified checkpoint/source-gate workflow. Before first
push, audit every shared runner/AST/blob-pin consumer if runner dispatch is
changed. Publish one fully prepared atomic feature commit and let its one
push-triggered CI admission run to terminal.

Do not run a live canary, provider request, credential read, paper operation or
the active F1 namespace during implementation/certification.

## Acceptance and next boundary

ChatGPT reviews exact source, tests and terminal CI. A passing Architecture 145
checkpoint means only `LIVE_CANARY_ELIGIBLE` research evidence can be created
for candidates satisfying the frozen policy.

Actual real-money canary execution remains a distinct future architecture and
protected operator boundary. Real-money trading remains **NO-GO**.
