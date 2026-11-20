# AI Strategy Discovery Campaign v1 — design frozen

## Status and purpose

This document freezes the next research direction for the AI Trading Bot.

The project already has deterministic market-data, backtest, multi-symbol,
experiment, ranking, pairwise, Pareto, walk-forward, research-candidate,
production-compatibility and research-governance machinery. This campaign does
not replace those systems with an LLM and does not authorize an LLM to trade.

The AI role is limited to:

1. synthesize existing accepted research evidence;
2. generate bounded, structured strategy hypotheses;
3. explain why a hypothesis may work and what would falsify it;
4. inspect deterministic diagnostics after a research generation completes;
5. propose the next frozen generation within the permitted search grammar.

Repository-owned deterministic engines remain authoritative for input data,
chronology, fills, costs, portfolio accounting, risk, backtest results,
walk-forward evidence, ranking, candidate lifecycle and all production effects.

Automatic strategy promotion remains prohibited. Human promotion remains
required. `FINAL_HOLDOUT` remains sealed until a separately frozen final
candidate or candidate portfolio exists.

## Existing evidence is the starting point

Generation 0 performs **no new backtests**. It consumes only already completed
research evidence that can be independently identified and verified.

The initial evidence inventory includes:

- the accepted Architecture 147 filtered-trend multi-asset research over the
  fixed daily universe SPY, QQQ, IWM, EFA, EEM, TLT, GLD and PDBC;
- the accepted Architecture 148 sparse OPEN baseline and churn study;
- the mechanically valid QQQ/TQQQ bullish volatility-band attribution audit
  supplied for this research session, which is informative but is not yet a
  canonical repository artifact;
- the frozen Architecture 148 late-session intraday-momentum design, which
  remains an unevaluated queued hypothesis;
- prior canonical experiment, ranking, Pareto, walk-forward and research
  candidate evidence available through existing repository contracts.

Generation 0 must distinguish canonical repository evidence from session-local
or externally supplied research notes. It may not silently promote the latter
to canonical evidence.

Its output is an evidence map, not a strategy selection. At minimum it records:

- strategy family and exact tested semantics;
- dataset/universe/timeframe;
- evaluation periods;
- base and stress trading costs;
- return, drawdown, turnover/trade count and concentration evidence when
  available;
- cross-asset and cross-year behavior;
- failure mode;
- whether the result is canonical, queued, rejected, or noncanonical;
- which questions remain unanswered.

## Research ledger and multiple-testing discipline

AI-assisted research creates a larger multiple-testing surface than manual
one-candidate research. Every candidate that reaches deterministic evaluation
must therefore be retained in one append-only semantic trial ledger.

The ledger must include rejected, failed, invalid, zero-trade and duplicate-
rejected proposals as well as successful results. A discarded trial may never
disappear merely because its P&L was poor.

Each proposal records at least:

- campaign version and generation;
- deterministic proposal identity;
- parent proposal identities, if any;
- strategy family;
- exact structured parameters/rules;
- hypothesis and expected mechanism;
- falsification condition;
- source/reference labels used by the AI;
- market data/results visible to the AI when the proposal was created;
- whether the proposal is original, mutation, recombination or retained
  baseline;
- deterministic evaluation/evidence identities once evaluated;
- terminal disposition.

The exact number of evaluated trials is behaviorally material evidence for
later selection-bias analysis.

Before any candidate advances beyond exploratory BACKTESTED status, the
campaign must evaluate selection bias using a trial-count-aware method. Version
1 targets the Deflated Sharpe Ratio or an equivalently reviewed deterministic
multiple-testing correction. The research literature motivating this boundary
includes Bailey and Lopez de Prado, *The Deflated Sharpe Ratio: Correcting for
Selection Bias, Backtest Overfitting and Non-Normality* (2014):
https://doi.org/10.3905/jpm.2014.40.5.094

Walk-forward evidence remains required but is not treated as sufficient by
itself when a large AI search preceded selection. A later source checkpoint may
add a stronger purged/combinatorial validation layer, but v1 does not silently
invent one.

## Generation 0 — evidence mining

Generation 0 is read-only research analysis.

It must:

- locate the exact accepted A147 research dataset/bundle and accepted A148
  evidence already present on the local machine;
- verify them through their existing public readers/verifiers when available;
- ingest no `FINAL_HOLDOUT` price data;
- perform no provider/network/credential/broker/production effect;
- run no strategy replay merely to reconstruct a missing historical result;
- report unavailable evidence rather than guessing it;
- produce one bounded Generation-0 synthesis artifact under a fresh create-once
  research output directory.

Generation 0 may recommend families for Generation 1, but may not alter any
candidate after Generation-1 P&L is visible.

## Generation 1A — daily multi-asset hypothesis search

Generation 1A uses the already accepted Architecture 147 daily adjusted
research universe:

`SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`.

No new provider acquisition is required for Generation 1A.

The AI must submit the complete Generation-1A proposal set before any new
Generation-1A strategy result is exposed to it. The first generation is capped
at **32 evaluated candidate programs**, including retained baselines. Duplicate
semantic candidates are rejected but still recorded in the proposal ledger.

Generation 1A must emphasize materially different mechanisms rather than dense
numeric tuning. The permitted family vocabulary is:

- absolute/time-series momentum;
- multi-horizon trend;
- moving-average trend;
- Donchian/channel breakout;
- volatility-adjusted trend or breakout;
- bounded mean reversion;
- cross-sectional relative strength;
- defensive/risk-on rotation;
- simple cross-asset regime gating;
- fixed strategy ensembles formed only from already declared component
  candidates.

Initial parameter values must come from small explicit sets frozen in the
proposal artifact. The AI may not emit arbitrary continuous thresholds or
custom Python. No family may consume more than one quarter of the 32-candidate
budget.

Long-only and FLAT are the default actions for v1. Any leverage, inverse ETF,
short sale, options or derivatives hypothesis stays outside Generation 1A.

Existing accepted A147 strategies are retained as baseline trials rather than
being hidden from the search count.

## Deterministic candidate representation

Generation-1 proposals must compile from a closed structured strategy
specification. The eventual source implementation may use a typed JSON/AST or a
closed template model, but it must not evaluate arbitrary model-generated code.

The minimum primitive vocabulary may include:

- completed-bar returns over fixed lookbacks;
- moving averages;
- realized volatility / ATR;
- Donchian highs/lows;
- RSI or bounded oscillator state;
- absolute momentum sign;
- cross-sectional rank;
- AND / OR over closed predicates;
- LONG / FLAT;
- fixed top-K selection;
- fixed equal-weight combination.

Every feature must be computed from information available before the execution
decision. No same-bar close may determine a fill at that same close or earlier
price.

Implementation discovery may narrow this primitive set to reuse existing source.
It may not silently broaden it after P&L is observed.

## Search chronology

The true `FINAL_HOLDOUT` remains sealed.

Inside OPEN data, v1 uses staged research visibility rather than allowing every
AI generation to inspect the whole 2016-2023 interval repeatedly.

- warm-up/reference history may use 2016-2018 as required by the frozen
  indicators;
- Generation 1 discovery evidence uses 2019-2021;
- the AI may inspect Generation-1 diagnostics and create exactly one bounded
  Generation-2 mutation/recombination set;
- Generation-2 proposal semantics must be frozen before 2022-2023 confirmation
  evidence is exposed;
- 2022-2023 is confirmation evidence and may not trigger another numeric
  mutation loop;
- `FINAL_HOLDOUT` remains untouched after confirmation.

Prior project research has already exposed some 2022-2023 behavior for other
strategy families. Therefore 2022-2023 is **not** called a pristine holdout.
It is only a campaign confirmation partition. The separately sealed
`FINAL_HOLDOUT` remains the only future holdout authority.

## Evaluation economics and diagnostics

Where an existing accepted strategy engine supplies stronger fixed economics,
reuse them rather than weakening them.

For the daily multi-asset search the default comparison uses the accepted A147
economics:

- base: $1 per fill plus 5 bps adverse slippage;
- stress: $2 per fill plus 10 bps adverse slippage;
- whole adjusted-share units;
- no synthetic missing prices.

Every evaluated candidate must retain at least:

- net return under base and stress;
- maximum drawdown;
- turnover;
- trade/fill count;
- time invested/exposure when supported;
- each calendar-year result;
- each asset result;
- buy-and-hold comparison where semantically applicable;
- parameter-neighbor or structural-ablation evidence when predeclared;
- concentration evidence sufficient to identify dependence on a small number of
  observations/trades;
- deterministic result/equity/trade identities where supported.

Ranking by raw return alone is forbidden.

## Generation filtering

Generation-1 output is descriptive. It does not directly create a production
candidate.

The deterministic analyzer should use existing Pareto/ranking machinery where
the result model permits it. The primary research objectives are:

maximize:

- stress-cost return;
- breadth of positive asset/year evidence;
- minimum/median confirmation return;
- persistence across adjacent/predeclared variants;

minimize:

- maximum drawdown;
- turnover/cost sensitivity;
- concentration;
- parameter sensitivity.

A high-return isolated spike is not preferred over a broad robust plateau.

The AI may diagnose the frontier but may not change the already completed
Generation-1 rules.

## Generation 2

Generation 2 is optional and bounded.

After Generation 1 completes, the AI may propose at most **16** candidates.
Every Generation-2 proposal must cite one or more Generation-1 parent proposals
and identify the exact diagnostic that motivates its mutation or recombination.

Permitted changes are structural:

- remove a failing filter;
- add one already permitted regime gate;
- combine two complementary accepted primitives;
- replace one discrete lookback with an adjacent predeclared value;
- build a fixed ensemble from declared Generation-1 components.

Generation 2 may not perform unrestricted parameter search, continuous
optimization, custom Python generation or iterative mutation after confirmation
results are visible.

## Intraday track

The mechanically valid QQQ/TQQQ bullish volatility-band result and the frozen
late-session momentum candidate remain part of the campaign hypothesis library.

They do not block the daily campaign.

After the daily Generation-1 analysis, the AI may recommend a separate intraday
replication wave. The preferred cross-asset panel remains SPY, QQQ, IWM, GLD
and TLT, with new five-minute acquisition only for symbols not already present
in accepted intraday data.

Intraday candidates retain their own cost, sparse-bar, stop and forced-flat
semantics and must not be mixed into daily return accounting.

## Machine-learning track

A later parallel track may test predictive models, beginning with interpretable
tabular baselines such as logistic regression and tree/boosting models before
deep learning or reinforcement learning.

The preferred first ML task is meta-labeling or strategy gating: estimate which
already deterministic strategy sleeve, if any, should be active in the current
market state. Direct opaque model-to-order generation is deferred.

Any ML track must have point-in-time features, explicit training/validation
chronology, fixed model/hyperparameter search budgets and the same trial-ledger
discipline. Model output alone never gains production authority.

## AI/model authority

Source/CI tests use no external AI service.

The first source checkpoint should represent AI proposals as supplied canonical
research input so tests remain deterministic and offline. An online model
connector may be designed later as a replaceable proposal producer.

An AI proposal producer must never have:

- broker credentials;
- Robinhood placement/cancellation authority;
- production-state mutation;
- strategy promotion authority;
- access to `FINAL_HOLDOUT` unless a separately reviewed holdout boundary
  explicitly supplies bounded evidence;
- the ability to bypass the deterministic evaluator.

Model text is research input, not authority.

## Existing lifecycle remains authoritative

The existing conceptual lifecycle remains:

`EXPERIMENTAL -> BACKTESTED -> WALK_FORWARD_PASSED -> SHADOW -> PAPER_CANDIDATE -> AWAITING_HUMAN_PROMOTION`.

The AI campaign does not introduce a shortcut around these stages.

Generation membership, Pareto rank, DSR, AI recommendation or research-only
leader status is not itself a lifecycle transition.

## Immediate source milestone

The first implementation checkpoint is a source-only/fake-only **AI research
campaign foundation**.

It should reuse the existing research engines and add only the smallest missing
pieces:

- canonical AI hypothesis/proposal model;
- append-only semantic trial ledger;
- Generation-0 evidence inventory/synthesis reader;
- closed Generation-1 strategy-spec representation;
- deterministic mapping from supported specs to existing research evaluators;
- trial-count-aware result metadata;
- bounded campaign artifact and verifier;
- focused tests proving no network/provider/broker/production/holdout effects.

Do not rewrite the backtest engine, ranking, Pareto, walk-forward or research
candidate lifecycle.

The source checkpoint runs no real campaign and makes no provider or AI API
call. After source acceptance, Generation 0 is the first real research action.

If implementation discovery shows that a requested strategy primitive requires
a materially new execution model rather than a narrow adapter, STOP and return
to ChatGPT before broadening the source checkpoint.

## Public research references

The campaign design is informed by, but does not copy code from:

- Bailey and Lopez de Prado, Deflated Sharpe Ratio:
  https://doi.org/10.3905/jpm.2014.40.5.094
- Siper et al., ProFiT: Program Search for Financial Trading:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5889762

These are hypothesis/process references only. Local deterministic evidence
controls every project decision.
