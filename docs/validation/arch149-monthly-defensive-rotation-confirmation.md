# Validation — Architecture 149 2024-2026 confirmation

Status: **CONFIRMATION CONTRACT FROZEN; SOURCE NOT IMPLEMENTED; REAL CONFIRMATION DATA UNOPENED**.

## Authority and prerequisite evidence

Accepted strategy source:

- HEAD `57087af056767c59ee48e3edb86063ac4f20c10d`;
- tree `da80c3f560d54d959822f7716a50fc45c3ead716`;
- strategy `MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1`.

Consumed exploratory evidence:

- report identity `8a3d7c3a-d2f9-5f10-91e6-ba06c3935d84`;
- report SHA-256
  `69f941721aaba736cef45b80543f7a238a30dcdb74f03c046c3fc01aabb5dbcf`;
- classification `EXPLORATORY_CANDIDATE_ONLY`;
- one Architecture-149 strategy trial consumed.

Frozen STRESS exploratory facts:

- full net return `0.82594481961`;
- CAGR approximately `0.0898215176`;
- maximum drawdown approximately `0.2814918643`;
- Sharpe approximately `0.5182991611`;
- median annual return approximately `0.1086090702`;
- positive years `6 / 7`.

These facts authorize confirmation only.

## No-mutation rule

Confirmation uses the exact accepted strategy:

- universe/order `SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`;
- month-end signals only;
- score `close[t-21] / close[t-252] - 1`;
- frozen universe-order tie break;
- strictly positive top score selects the top ETF, otherwise CASH;
- 95% whole-share allocation;
- next-qualified-session OPEN execution;
- sell-before-buy switching;
- exact BASE and STRESS A147 costs.

No alternative threshold, lookback, filter, fallback asset, stop, leverage,
short, inverse ETF, option, ensemble, ML rule, or intra-month trade is allowed.

## Confirmation chronology

Confirmation is exactly:

`[2024-01-01, 2027-01-01)`.

It must contain complete calendar years 2024, 2025 and 2026.

The real acquisition/replay may not run until the final expected XNYS regular
session of calendar 2026 has completed and can be represented in provider data.

Partial-2026, year-to-date, rolling-now, truncated-year, or early-peek
confirmation is forbidden.

## Warmup and first action

The immutable accepted A147 2016-2023 dataset is the sole pre-confirmation
history input:

- identity `d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`;
- SHA-256
  `ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`.

It is warmup/signal history only.

The December 2023 month-end signal is recomputed from pre-2024 history and is
the first confirmation target. It may execute only at the first qualified 2024
OPEN.

Confirmation starts from fresh $100,000 CASH. No exploratory position or ending
equity carries forward.

The December 2026 month-end target is retained as a terminal non-executable
decision because its next OPEN is outside the confirmation interval.

## New confirmation dataset

Acquire and preserve exactly one adjusted-daily dataset for:

`[2024-01-01, 2027-01-01)`.

Use the same universe and A147 daily adjusted-price/provider semantics.

Require deterministic canonical serialization, semantic identity and SHA-256
custody. No synthetic missing price is permitted.

No confirmation provider response, normalized bar, return, target, fill,
statistic or diagnostic may be opened before:

1. this contract is committed;
2. source-only confirmation support is accepted/integrated;
3. a separate acquisition operator is reviewed.

Acquisition and replay are distinct checkpoints.

## Input composition

The confirmation evaluator receives two explicit immutable inputs:

1. accepted A147 pre-2024 history;
2. accepted 2024-2026 confirmation dataset.

Validate both identities and hashes before replay.

The combined view must prove:

- no conflicting overlap;
- no 2024+ bar comes from the A147 history input;
- no pre-2024 period contributes confirmation performance;
- pre-2024 history may be used only for signal lookback;
- every reportable mark/action/fill/return is in 2024-2026;
- no 2027 OPEN is read.

## Replay and reports

Run exactly one confirmation observation under BASE and STRESS.

Each cost case starts a fresh continuous $100,000 portfolio.

Report:

- `CONFIRMATION_FULL` for 2024-2026;
- 2024;
- 2025;
- 2026.

Annual partitions are slices of the same continuous path.

Retain the accepted exploratory diagnostics/identity conventions adapted to the
confirmation interval, including return, CAGR, maximum drawdown, volatility,
Sharpe, annual returns, signals/rebalances/unchanged/CASH/switch/fill counts,
turnover, time invested, final equity, symbol holdings/entries,
target/trade/equity identities, SPY/QQQ descriptive comparators, source/input
bindings and zero-effect counters.

## Frozen confirmation classification

Use STRESS only.

Return `CONFIRMATION_REJECTED` if any is true:

- `CONFIRMATION_FULL` net return <= 0;
- median of 2024/2025/2026 annual returns <= 0;
- fewer than two of three annual returns are > 0;
- maximum drawdown > 0.35.

Otherwise return `CONFIRMATION_CANDIDATE_ONLY`.

Exactly 0.35 drawdown passes this boundary.

No threshold may change after any confirmation data becomes visible.

A pass grants only permission to design a separate post-confirmation
robustness/paper-shadow qualification. It grants no FINAL_HOLDOUT, live, broker,
production or automatic strategy-replacement authority.

## Trial accounting

Architecture 149 remains one fixed strategy.

Exploratory evaluation consumed one strategy trial.

Confirmation is one preregistered out-of-sample observation of the same fixed
strategy, not a new parameter-search trial.

No alternative Architecture-149 rule may be tested on confirmation data.

## Source-only checkpoint

Planned route:

`arch149-monthly-defensive-rotation-confirmation`

Planned branch:

`feature/research-arch149-monthly-defensive-rotation-confirmation-current`

Planned worktree:

`F:\AI\worktrees\ai-trading-bot-arch149-monthly-defensive-rotation-confirmation-current`

Source implementation is synthetic/fake-only. It must not open real 2024-2026
data.

Extend the accepted Architecture-149 implementation with a narrow confirmation
input/evidence layer. Do not weaken the existing exploratory post-2023
rejection.

Focused tests must prove the two-input boundary, December-2023-to-first-2024
action, fresh $100,000 capital, exact strategy parity, exact costs,
2024-2026-only performance, December 2026 terminal non-execution, rejection of
partial/truncated/future confirmation data, continuous partitions, frozen
classification boundaries, and zero protected effects.

Real acquisition and real confirmation replay remain separate reviewed
operations after source acceptance.
