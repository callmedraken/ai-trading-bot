# Architecture 151 — Intraday walk-forward edge search

Status: **DESIGN FROZEN; SOURCE IMPLEMENTATION NOT STARTED; 2024+ SEALED**.

## Goal

Architecture 151 continues the same-day trading goal after terminal Architecture
150. It targets frequent intraday opportunities, never requires a trade every
day, and finishes every XNYS session flat.

Architecture 150 is immutable negative evidence: 24/24 frozen candidates failed
2021-2023 STRESS validation and no G2 survivor exists. Architecture 151 does not
mutate or rerun those programs.

## Historical boundary

2016-2023 is now development-visible.

2024-2025 remains the final local historical holdout and may not be acquired,
opened or evaluated before one final Architecture 151 candidate is frozen.

January-October 2026 is a later recent-regime extension and may open only after
the 2024-2025 holdout passes.

Reuse the accepted Architecture 150 SPY/QQQ sparse one-minute custody for
2016-2023. No provider reacquisition is authorized for development.

Derived 5-minute and 15-minute bars require every aligned one-minute source bar.
Any missing constituent removes that aggregate decision point. All other
Architecture 150 sparse causality rules remain in force.

## Walk-forward development

Candidate structure is frozen before real replay. Development uses five
expanding scored folds:

| Fold | Calibration history | Scored year |
| --- | --- | --- |
| WF1 | 2016-2018 | 2019 |
| WF2 | 2016-2019 | 2020 |
| WF3 | 2016-2020 | 2021 |
| WF4 | 2016-2021 | 2022 |
| WF5 | 2016-2022 | 2023 |

Only explicitly declared rolling statistics may be calibrated, and only from
history strictly earlier than the scored year. A scored result may never change
a later candidate definition.

## Instruments and direction

Signal and execution research remain SPY and QQQ.

Architecture 151 is long-or-flat, unleveraged, session-flat and research-only.
It grants no margin, leverage, short-selling, options or live authority.

## Candidate population

Freeze exactly 16 structural programs: four per family. Each structural program
is evaluated once on SPY then QQQ, yielding exactly 32 ordered trial slots.

Each family has exactly two 5-minute and two 15-minute programs.

### A — Regime-filtered noise/VWAP breakout

Selective continuation beyond a causal historical noise area with VWAP
confirmation and a prior-history volatility-regime gate.

Every program freezes its lookback, breakout distance, confirmation count,
regime gate, entry window, stop/trailing rule, maximum hold and entry limit.

### B — Opening-range breakout retest

No immediate breakout entry. Require completed-bar breakout, bounded retest of
the broken opening-range level and completed-bar reclaim/hold.

Programs freeze opening range, breakout distance, retest delay/tolerance,
confirmation, stop/target/trailing rule and entry window. Maximum one entry per
session.

The rejected Architecture 148 late opening-drive rule remains unrepresentable.

### C — VWAP-deviation mean reversion

Long-only reversion from unusual downside VWAP displacement under a causal
low-directionality regime.

Programs freeze normalization window, deviation threshold, regime gate,
VWAP/reversion exit, adverse stop, maximum hold and cooldown. Maximum two entries
per session; no averaging down.

### D — Cross-ETF confirmed trend pullback

A local SPY/QQQ pullback-reclaim is eligible only when the other ETF confirms
the same broad completed-bar regime.

Programs freeze local trend definition, cross-ETF confirmation, pullback depth,
reclaim rule, entry window, stop/trailing rule, maximum hold and entry limit.

## Trial budget

Exactly 32 real Architecture 151 trials exist. There is no adaptive G2, random
search, Bayesian optimization, post-result parameter nudge or structural
recombination inside this architecture.

A changed grammar after results requires a new architecture.

## Churn/frequency boundary

Every candidate must:

- average at least 100 completed round trips per scored year;
- be active on at least 35% of scored XNYS sessions;
- have median completed trades per active session <= 2;
- never exceed two completed round trips in one session;
- obey any stricter family entry/cooldown rule.

## Costs

Retain Architecture 150 economics for comparability.

BASE = 2 bps adverse slippage per fill.
STRESS = 5 bps adverse slippage per fill.
ZERO is diagnostic only and can never qualify a candidate.

## Development qualification

A candidate reaches selection-bias review only if STRESS results satisfy all:

- aggregate 2019-2023 net return > 0;
- aggregate profit factor > 1;
- positive net return in at least 4 of 5 scored years;
- profit factor > 1 in at least 4 of 5 scored years;
- worst scored-year return > -10%;
- aggregate maximum drawdown <= 20%;
- average completed round trips/year >= 100;
- active-session fraction >= 35%;
- median trades/active session <= 2.

Retain Sharpe, expectancy, positive-month breadth, turnover and worst-year
return as descriptive/ranking metrics.

## Selection-bias correction

Architecture 151 reuses historical years already searched by prior intraday
campaigns. The correction therefore uses:

`effective_trial_count = max(64, 32 + documented_prior_intraday_trials)`.

Use Deflated Sharpe Ratio or an equivalently reviewed correction with pass
probability >= 0.95.

After correction, freeze exactly zero or one final candidate. If several pass,
rank deterministically by:

1. DSR probability descending;
2. worst scored-year return descending;
3. STRESS profit factor descending;
4. STRESS Sharpe descending;
5. maximum drawdown ascending;
6. turnover ascending;
7. immutable slot ID ascending.

Zero survivors terminate Architecture 151 without 2024+ access.

## Final holdout

Only the single frozen final candidate may open 2024-2025.

STRESS holdout PASS requires:

- combined 2024-2025 net return > 0;
- both calendar years > 0;
- combined profit factor > 1.10;
- maximum drawdown <= 15%;
- active-session fraction >= 30%;
- average completed round trips/year >= 80;
- no single month > 40% of total positive P&L.

No strategy mutation is allowed after holdout visibility.

## 2026 extension

Only a holdout survivor may open January-October 2026.

PASS requires STRESS net return > 0, profit factor > 1.05, maximum drawdown <=
15%, at least 6/10 positive complete months and active-session fraction >= 30%.

## Promotion boundary

A full survivor becomes `ARCH151_INTRADAY_RESEARCH_SURVIVOR`.

That permits only a later paper/shadow translation study. It grants no Robinhood
order or live authority.

## Immediate source milestone

Implement source-only Architecture 151 types, the canonical 16-program/32-slot
manifest, deterministic sparse 5m/15m aggregation, five-fold chronology,
qualification records, selection-bias input/final freeze and the 2024+ firewall.

Use synthetic tests only. Real strategy replay remains zero.
