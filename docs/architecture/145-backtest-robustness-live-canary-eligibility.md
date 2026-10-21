# Architecture 145 / RCL-8 — robust historical qualification for bounded live-canary eligibility

Status: **DESIGN FROZEN; source implementation is next.**

## Objective

Architecture 145 shifts strategy-quality qualification away from extended paper
P&L and toward deterministic historical robustness evidence.

It does not remove or reinterpret accepted Architecture 144/144-C. F1 and 144-C
remain operational/provenance evidence. Architecture 145 is a separate research
successor whose positive output means only that a strategy has earned review for
a later tiny-capital live canary.

It never grants provider, credential, scheduler, paper, broker, D2, promotion or
real-money authority.

## Motivation

Paper execution is useful for integration and restart testing but cannot fully
represent real queue position, spread capture, partial/missed fills, rejects,
latency, broker routing or live slippage. Conversely, a single attractive
backtest is vulnerable to overfitting and data snooping.

The qualification therefore requires both:

1. broad historical/out-of-sample evidence; and
2. conservative deterministic execution-stress evidence.

Real execution behavior is learned only in a later separately bounded live
canary.

## Isolation

Expected branch:

`feature/research-backtest-robustness-live-canary-eligibility-current`

Expected worktree:

`F:\AI\worktrees\ai-trading-bot-research-backtest-robustness-live-canary-eligibility-current`

Base: current reviewed `develop` descendant.

Architecture 145 must not read or mutate:

- `F:\AI\temp\qualification` F1 operational evidence;
- production SQLite/runtime state;
- Windows Credential Manager;
- Task Scheduler;
- provider/network/broker endpoints.

## Existing accepted inputs

Reuse public deterministic primitives where compatible:

- historical experiment/backtest runners;
- `HistoricalExperimentWalkForwardResult`;
- walk-forward aggregate analytics;
- walk-forward stability/sensitivity;
- accepted research-candidate and strategy-native evaluation artifacts;
- deterministic canonical Decimal/UUID/source-provenance conventions.

Do not modify frozen predecessor schemas merely to fit Architecture 145.
Use additive successor artifacts.

## Qualification model

Architecture 145 adds a canonical, immutable
`ResearchStrategyRobustnessQualificationPolicy` and a positive-only
`ResearchStrategyLiveCanaryEligibility` artifact.

A policy must be fully materialized and identity-bound **before** evaluation of
the sealed final holdout. The policy cannot be inferred from, relaxed after, or
selected by the holdout result.

The policy must explicitly bind:

- strategy identity/version and canonical configuration;
- historical-data fingerprint(s);
- development / walk-forward partitions;
- sealed final-holdout partition;
- minimum completed-trade/sample requirement;
- allowed maximum drawdown;
- required net-return or comparable profitability floor after modeled costs;
- required walk-forward fold pass/stability constraints;
- parameter-neighborhood sensitivity constraints;
- the exact deterministic execution-stress suite;
- any benchmark/comparison rule used for qualification.

The framework may support multiple policies/strategies, but one eligibility
artifact binds one exact strategy/config/policy/data lineage.

## Required research sequence

For each strategy candidate:

1. **Development backtests** may be used for hypothesis and parameter selection.
2. **Walk-forward evaluation** must use non-overlapping out-of-sample test folds
   with no lookahead.
3. **Parameter sensitivity** must test a canonical neighborhood rather than only
   the single selected optimum.
4. **Time/regime sensitivity** must demonstrate that performance is not created
   by one narrow start/end window.
5. **Execution stress** must rerun the frozen candidate under deterministic
   adverse execution assumptions.
6. **Final holdout** remains sealed until the policy, strategy configuration and
   stress suite are frozen. It is evaluated once for that candidate version.
7. Positive eligibility may be created only when every frozen requirement passes.

No automatic search may repeatedly open new holdouts until one passes.

## Execution-stress requirements

The source must support deterministic stress cases covering at least these
failure dimensions:

- higher modeled slippage/transaction cost than the baseline;
- delayed fills relative to the baseline next-open model;
- missed/rejected-order fault injection;
- partial-fill behavior where the strategy/order model permits it;
- gap/adverse-price behavior caused by delayed execution;
- reconciliation of ending cash/positions/equity after every scenario.

Stress scenarios are research simulations, not claims about exact broker
probabilities. Their purpose is to reject strategies whose economics collapse
under modest execution degradation.

The exact v1 scenario set and numerical thresholds must be frozen in source-owned
policy construction and covered by tests before any candidate's sealed holdout
is evaluated.

## Evidence and metrics

Qualification evidence must retain enough canonical information to independently
reconcile at least:

- gross and net P&L/return;
- maximum drawdown;
- trade/fill counts;
- turnover where available;
- per-fold walk-forward results;
- aggregate walk-forward metrics;
- stability/sensitivity results;
- each execution-stress result;
- final-holdout result;
- data/strategy/policy/source identities.

Metrics must use the repository's deterministic Decimal conventions where
applicable. No wall clock, random UUID, locale, object identity, ambient hash,
filesystem path or network response may enter semantic identity.

## Live-canary boundary

`LIVE_CANARY_ELIGIBLE` is evidence only.

A later architecture is required to authorize any real-money action. That later
boundary must separately require:

- explicit human approval;
- production source/runtime/credential admission;
- the reboot=STOP/manual-start operator lifecycle;
- hard low notional/exposure ceilings;
- hard daily and cumulative loss ceilings;
- no leverage or automatic size increase in the initial canary unless separately
  reviewed;
- durable PREPARE/order/fill/reconciliation evidence;
- no retry after ambiguous broker effect;
- measurement of expected vs actual fill price, slippage, rejection/miss/partial
  fill behavior and latency;
- a separate review before any size increase.

Tiny live fills validate real execution mechanics at tiny size; they do not prove
future capacity at larger size.

## F1 relationship

The active Architecture 134-F1 soak remains untouched. Its purpose is operational
reliability across five published sessions. F1 results may be retained as
integration evidence, but F1 profitability is not an input required to create
Architecture-145 historical robustness evidence.

Real-money trading remains **NO-GO** until a later live-canary architecture is
designed, source accepted, operationally admitted and explicitly authorized.
