# Architecture 149 — Monthly cross-asset defensive rotation research

Status: **Design frozen; source accepted/integrated; real exploratory replay NOT RUN.**

Accepted source identity:
- HEAD `57087af056767c59ee48e3edb86063ac4f20c10d`;
- tree `da80c3f560d54d959822f7716a50fc45c3ead716`;
- direct parent `088f5aa4581bcb2b211c69f71f447ab9cb98e645`;
- feature mapped FULL `44914956812`, attempt 1, SUCCESS;
- develop source gate `44935678418`, attempt 1, SUCCESS with exact feature
  certification reuse and no duplicate FULL.

Real 2017-2023 exploratory evidence remains NOT RUN.

## Purpose

Architecture 149 starts a new independent research family after the consumed
Architecture-147 daily trend/AI discovery branch and the consumed
Architecture-148 intraday opening-drive branch produced no viable survivor.

It does not mutate those strategies, reuse their result rankings, or tune a
parameter from their visible P&L. The only shared research input is the already
accepted adjusted daily multi-asset dataset and its immutable custody.

The fixed candidate is:

`MONTHLY_CROSS_ASSET_DEFENSIVE_ROTATION_V1`

There is exactly one candidate and therefore one new strategy trial.

## Public research basis

The hypothesis is motivated by published evidence that momentum appears across
multiple asset classes and that one-to-twelve-month own-return persistence has
appeared across diversified liquid markets:

- Moskowitz, Ooi and Pedersen, *Time Series Momentum*, Journal of Financial
  Economics 104(2), 2012:
  https://doi.org/10.1016/j.jfineco.2011.11.003
- Asness, Moskowitz and Pedersen, *Value and Momentum Everywhere*, Journal of
  Finance 68(3), 2013:
  https://doi.org/10.1111/jofi.12021

The design also treats trading-cost evidence as a first-class constraint rather
than assuming gross momentum returns survive implementation. Lesmond, Schill
and Zhou, *The Illusory Nature of Momentum Profits*, Journal of Financial
Economics 71(2), 2004, is a cautionary reference:
https://doi.org/10.1016/S0304-405X(03)00206-X

These references motivate the family only. No paper result or third-party code
is imported as local evidence.

## Accepted exploratory data

Reuse only the accepted Architecture-147 adjusted daily dataset:

- identity `d5aa8ed7-b5cd-53a3-8671-5370f976e8e3`;
- SHA-256
  `ebe1839d510db0f24f58f9ebe02b7efb09221d4b8c06c23122f84912c3225214`;
- universe, exact order:
  `SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`;
- logical interval `[2016-01-01, 2024-01-01)`;
- price basis `ALPACA_ALL_ADJUSTED_PRICE_V1`.

No new historical acquisition is authorized for the exploratory step.

2016 is warmup only.

Exploratory performance is reported only over
`[2017-01-01, 2024-01-01)`.

No 2024+ daily data may be opened by this campaign until the exploratory
candidate is terminal and a separately reviewed confirmation acquisition is
authorized.

## Fixed signal

Signals are evaluated only on the final qualified regular session of each
calendar month.

For a month-end signal session at index `t`, every symbol must have the exact
required completed adjusted closes at:

- `t - 21` qualified sessions;
- `t - 252` qualified sessions.

The frozen relative-strength score is:

`score = close[t - 21] / close[t - 252] - 1`

This is a 12-minus-1-session momentum measure. The most recent 21 qualified
sessions are excluded from ranking.

All eight symbols must have valid observations for the signal. Missing input is
a deterministic no-rebalance diagnostic; no interpolation, carry-forward or
partial-universe ranking is allowed.

Rank all eight scores descending.

Tie break is the frozen universe order:

`SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`.

The top-ranked symbol is the only possible asset target.

## Absolute defensive gate

The candidate owns exactly one risk gate.

If the top-ranked score is strictly positive:

- target the top-ranked ETF.

If the top-ranked score is zero or negative:

- target CASH.

There is no alternate defensive ETF, second-ranked fallback, volatility
filter, moving-average overlay, stop, leverage, inverse exposure, shorting,
options, or discretionary override.

## Execution

The target determined from completed month-end session `t` becomes actionable
only at the next qualified session `t+1` OPEN.

One portfolio starts with $100,000 cash.

Use:

- long-only whole adjusted-share units;
- target allocation `0.95` of available portfolio equity when entering an ETF;
- residual cash stays cash;
- when changing ETF, sell the existing position before buying the new target;
- when target is unchanged, do nothing;
- when target is CASH, liquidate the existing ETF and remain flat;
- no intra-month trade;
- no stop loss;
- no same-session re-entry;
- no cross-symbol simultaneous holdings.

The portfolio may hold exactly one of the eight ETFs or CASH.

## Cost cases

Freeze exactly the accepted A147 economics:

BASE:
- commission $1 per fill;
- 5 bps slippage.

STRESS:
- commission $2 per fill;
- 10 bps slippage.

Execution uses the real next-session adjusted OPEN. No synthetic missing price
is permitted.

## Exploratory partitions

The candidate is one chronological portfolio replay.

2016 is warmup only.

Report:

- `EXPLORATORY_FULL`: 2017-2023 continuous;
- calendar 2017;
- calendar 2018;
- calendar 2019;
- calendar 2020;
- calendar 2021;
- calendar 2022;
- calendar 2023.

Calendar partitions are reporting slices of the one continuous capital path,
not fresh accounts.

## Required diagnostics

For each cost case preserve at minimum:

- total/net return;
- CAGR;
- maximum drawdown;
- annualized volatility;
- Sharpe ratio with stated convention;
- calendar-year returns;
- month-end signal count;
- executable rebalance count;
- unchanged-target count;
- cash-target count;
- ETF switch count;
- fill count;
- turnover;
- time invested;
- final equity;
- per-symbol months held;
- per-symbol entry count;
- complete target sequence identity;
- complete trade-audit identity;
- complete daily-equity identity;
- QQQ/SPY buy-and-hold descriptive comparators;
- zero-effect counters.

### Reporting semantics

The 2016 interval is warmup only and contributes no signals, actions, or
performance. A December 2023 month-end target remains in the target history as
the terminal non-executable decision. It must not cause a 2024 date or open
price lookup.

Count signals and CASH targets on their signal dates. Count executable
rebalances, unchanged-versus-held outcomes, ETF switches, fills, and turnover
on their action or fill dates. Report a missing-input no-rebalance separately
from a valid signal decision, including a valid decision that targets CASH.
Time invested is the fraction of scoring sessions held at the close. Per-symbol
months held counts qualified month-end closing holdings.

Report returns after costs. Calculate 1-year and 7-year calendar-span CAGR from
the corresponding continuous portfolio path. Daily net returns are simple
returns, with the first daily return measured from the scoring slice's opening
equity. Annualized volatility uses sample standard deviation multiplied by
square root of 252. The zero-risk-free daily Sharpe ratio uses the mean divided
by sample standard deviation, multiplied by square root of 252. It is undefined
when sample standard deviation is degenerate.

QQQ and SPY passive comparisons run from the first scoring-session OPEN through
the last scoring-session CLOSE. They remain descriptive and do not reset the
portfolio path.

## Frozen exploratory classification

The single candidate is `ECONOMICALLY_REJECTED` if any is true under STRESS:

- `EXPLORATORY_FULL` net return is not positive;
- median of the seven calendar-year net returns is not positive;
- fewer than five of seven calendar-year net returns are positive;
- maximum drawdown exceeds `0.35`.

Otherwise classify:

`EXPLORATORY_CANDIDATE_ONLY`.

This is only permission to consider the separately frozen 2024-2026
confirmation acquisition and replay.

It grants no walk-forward, FINAL_HOLDOUT, SHADOW, paper, live, broker or
production authority.

No threshold above may be changed after exploratory P&L is visible.

## Future confirmation firewall

If and only if the exploratory classification is
`EXPLORATORY_CANDIDATE_ONLY`, a later checkpoint may acquire adjusted daily
data for `[2024-01-01, 2027-01-01)`.

That future dataset must remain unread by this campaign until:

1. this design is committed;
2. source is implemented and accepted;
3. the single 2017-2023 exploratory replay is consumed;
4. a separate confirmation contract is frozen.

No exploratory mutation is permitted before or after confirmation.

## Source boundary

The implementation checkpoint is source-only/fake-only.

Suggested ownership:

`src/trading_bot/experiments/arch149_monthly_defensive_rotation.py`

Prefer reuse of the accepted Architecture-147 adjusted daily dataset schemas,
Decimal conventions, whole-share accounting and next-open execution semantics.

Do not reuse the G1 typed signal grammar as research authority. Architecture 149
is an independent one-candidate portfolio-level research path.

No provider, credential, Robinhood, broker, production-state, 2024+ data, or
FINAL_HOLDOUT access is authorized by source implementation.
