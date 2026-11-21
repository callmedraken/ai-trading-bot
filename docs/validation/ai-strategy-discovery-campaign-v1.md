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

### Current campaign state

The accepted G1 population consumed 22 trials. Its proposal set is
`b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b`, its complete-panel analysis is
`d5ca081e-7490-5590-921d-10cee373d012`, and its terminal ledger is
`68418f44-7db0-5080-a6bd-a956a928bd4a`. Twelve programs were SHORTLISTED and ten
were ECONOMICALLY_REJECTED.

The G2 population consumed six trials. Its proposal set is
`c958130d-7594-535b-aa46-065525a10c46`, its batch is
`8c85731c-75dd-5a60-9456-10f237a6b0dd`, its analysis is
`821697c8-9917-5b76-b519-f81a2452d7f6`, and its terminal ledger is
`e86be80c-562c-5243-bc56-9e4a9e4c9f6d`. Zero candidates passed confirmation and
all six were CONFIRMATION_REJECTED. The G2 momentum-admission hypothesis is
rejected. Do not mutate or rerun G2, and do not use its 2022-2023 results to
design another candidate.

The current implementation milestone is a source-only selection-bias analysis
for the 12 G1 shortlisted programs. Its tests use synthetic inputs. Real
selection-bias observation is deferred until the source checkpoint is accepted.
The 22 G1 programs form the complete primary search distribution. G2 contributes
only its six consumed trials to the separately labeled campaign-wide
Bonferroni sensitivity, making that sensitivity count 28. G2 identities,
outcomes, confirmation visibility and metrics do not enter G1 candidate
selection or its DSR benchmark. `FINAL_HOLDOUT` remains sealed.

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
selection-bias analysis. Before any candidate advances beyond exploratory
BACKTESTED status, this campaign requires a trial-count-aware correction.
Bailey and López de Prado's Deflated Sharpe Ratio is the primary method.

For candidate daily Sharpe `SR`, sample length `T`, skewness `γ1`, and raw
Pearson kurtosis `κ`, the non-normality-adjusted statistic is

`z = (SR - SR0) * sqrt(T - 1) / sqrt(1 - γ1 * SR + (κ - 1) * SR^2 / 4)`

and DSR is `Φ(z)`. The primary search benchmark uses all 22 G1 daily Sharpe
values, including the ten economically rejected programs. Its frozen
zero-centered expected maximum is

`SR0 = sqrt(sample_variance(SR_1, ..., SR_22, ddof=1)) * [(1 - γ) * Φ^-1(1 - 1/22) + γ * Φ^-1(1 - 1/(22e))]`.

No empirical mean of the 22 Sharpe values is added to this zero-centered null.
Here `γ` is the Euler-Mascheroni constant.
The independence approximation is explicit. The 22 G1 trials are treated as
independent in the expected-maximum formula even though their strategies may be
dependent.

Candidate daily Sharpe is arithmetic mean daily return divided by sample
standard deviation with `ddof=1`. The annualized display is daily Sharpe times
`sqrt(252)` and is not used in the DSR calculation. Central moments use divisor
`T`, with skewness `m3 / m2^(3/2)` and raw Pearson kurtosis `m4 / m2^2`. Raw
kurtosis is not replaced with excess kurtosis, and no finite-sample bias
correction is applied. Statistics use a fixed Decimal context with precision 60
and `ROUND_HALF_EVEN`. The deterministic normal calculation uses an erf power
series through absolute z-score 8, a Mills-ratio continued fraction above 8,
and bisection for inverse upper-tail quantiles.

The separate campaign-wide sensitivity uses a zero-benchmark one-sided PSR
p-value. It uses

`z0 = SR * sqrt(T - 1) / sqrt(1 - γ1 * SR + (κ - 1) * SR^2 / 4)`

and `p_campaign = 1 - Φ(z0)` with `alpha = 0.05 / 28`. A shortlisted G1
candidate passes only when DSR is at least `0.95` and this p-value is at most
the campaign alpha. This count includes six consumed G2 trials, but no G2
Sharpe values are pooled with the G1 population. The PSR sensitivity is distinct
from the DSR.

The campaign literature includes Bailey and López de Prado, *The Deflated
Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and
Non-Normality* (2014), https://doi.org/10.3905/jpm.2014.40.5.094.

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

Generation 0 is accepted with inventory identity
`08395fd5-43a4-5a81-9992-877560757a9f`, foundation identity
`00a845be-228a-56c6-9fd1-9b76c2176cf8`, and A147 bundle identity
`3b86c5e0-6053-53af-a499-d297265f3cd8` (SHA-256
`80ff955ce2544f0799d8c1fdc1f77f9c337ecf2b25d01731dda1add90ef392f7`), bound
to A147 source HEAD/tree
`6203cbe8729d585dd3a244448bfa81318c7dfc11` /
`9529749c33fb1dee3b1271e80e7c08f8be0d004d`. Its evaluated-trial count is
zero. `FINAL_HOLDOUT` remains sealed and AI, provider, broker and production
effects remain zero.

## Generation 1A — daily multi-asset hypothesis search

Generation 1A uses the already accepted Architecture 147 daily adjusted
research universe:

`SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`.

No new provider acquisition is required for Generation 1A.

The AI must submit the complete Generation-1A proposal set before any new
Generation-1A strategy result is exposed to it. The first generation is capped
at **32 evaluated candidate programs**, including retained baselines. Duplicate
semantic candidates are rejected but still recorded in the proposal ledger.

The first supported G1 population is frozen at 22 programs. It uses only these
four families; the remaining campaign families below are deferred and cannot
be submitted as supported proposals in this checkpoint. The total budget is 32
evaluated programs with a maximum of 8 programs per family. The unused 10 slots
remain unused; they are not filled with prose variants, duplicate semantics or
extra numeric tuning.

1. **MOVING_AVERAGE_TREND — 6 retained baselines:** `(35,50)`, `(55,100)` and
   `(50,200)`, each with the accepted `BASE_MA` and fixed symmetric 1.0% band
   semantics.
2. **DONCHIAN_BREAKOUT — 6 retained baselines:** the same three MA pairs,
   crossed with prior completed-session channel lengths `20` and `55`.
3. **ABSOLUTE_MOMENTUM — 6 new programs:** lookback `63`, `126` or `252`
   completed sessions, crossed with gate `NONE` or `ABOVE_SMA200`. At completed
   session `t`, positive momentum requires `close[t] > close[t-lookback]`; the
   optional gate also requires `close[t] > SMA200[t]`. Equality is false. The
   result is LONG or FLAT and takes effect at session `t+1` open.
4. **MULTI_HORIZON_TREND — 4 new programs:** horizon set `(21,63,126)` or
   `(63,126,252)`, crossed with vote `2_OF_3` or `3_OF_3`. Each horizon votes
   positive only when `close[t] > close[t-horizon]`; equality is non-positive.
   The result is LONG or FLAT and takes effect at session `t+1` open.

Existing A147 mappings and execution semantics remain intact for both retained
baseline families. The two new families use closed typed specifications and a
separate deterministic evaluator representation; they do not widen the A147
`StrategyConfig` compiler. No custom code, arbitrary expressions, leverage,
short, inverse ETF, options or derivatives are supported. No other family is
currently supported: `VOLATILITY_ADJUSTED_TREND`,
`BOUNDED_MEAN_REVERSION`, `CROSS_SECTIONAL_RELATIVE_STRENGTH`,
`DEFENSIVE_ROTATION`, `CROSS_ASSET_REGIME_GATE` and `FIXED_ENSEMBLE` remain
deferred.

The complete ordered proposal set must be frozen before any G1 result is
visible. It binds the accepted Generation-0 identities, source HEAD/tree,
proposal and semantic-program identities, family counts and budgets; it records
zero G1 result visibility and a sealed `FINAL_HOLDOUT`. Repeated semantic
programs are rejected regardless of differences in prose.

## Deterministic candidate representation

Generation-1 proposals compile only from the exact closed typed specifications
listed above: the two retained A147 baseline families, absolute momentum and
multi-horizon trend. Their signal states are LONG or FLAT, and a completed
session's close can affect execution only at the next session's open. The two
new families remain separate typed programs and do not expand the A147
`StrategyConfig` compiler.

Arbitrary model-generated code and unreviewed program primitives are not
supported. ATR or RSI filters, cross-sectional ranks, top-K selection and fixed
ensembles remain deferred unless separately reviewed and admitted into a future
frozen population. No same-bar close may determine a fill at that same close or
an earlier price.

## Search chronology

The true `FINAL_HOLDOUT` remains sealed.

The G1 evaluator receives the accepted A147 adjusted daily universe exactly as
`SPY, QQQ, IWM, EFA, EEM, TLT, GLD, PDBC`. It may use data before 2019 only for
indicator/lookback warm-up. G1 discovery evidence is exactly
`[2019-01-01, 2022-01-01)`, with 2019, 2020 and 2021 calendar slices plus one
continuous 2019-2021 result. The bounded discovery view must remove all bars on
or after 2022-01-01 before strategy evaluation. The G1 evaluator must not
compute or expose 2022-2023 results. `FINAL_HOLDOUT` remains inaccessible.

The frozen Generation-2 confirmation design below preceded the later one-shot
campaign run. That run consumed six G2 trials and rejected all six. Its
confirmation metrics do not enter the current G1 selection-bias analysis, and
the accepted A147 dataset is not reread for G2.

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
- starting cash $100,000 and 95% allocation;
- whole adjusted-share units and next-session-open execution from the prior
  completed session's signal;
- independent per-symbol accounts;
- no synthetic missing prices.

Every evaluated candidate must retain at least:

- net return under base and stress;
- maximum drawdown;
- turnover;
- entry, closed-trade and fill counts;
- time invested/exposure when supported;
- each asset/year result and each continuous-symbol result;
- buy-and-hold comparison where semantically applicable;
- deterministic result/equity/fill identities;
- breadth and concentration diagnostics sufficient to identify dependence on a
  small number of assets, years, observations or trades.

The panel has 8 continuous-symbol cells and 24 asset/year cells. Retain separate
base and stress summaries. For each completed non-zero-trade candidate, classify
`SHORTLISTED` only when all of these hold under stress economics: median
continuous-symbol return is strictly positive; at least 5 of 8 continuous
returns are strictly positive; at least 13 of 24 asset/year returns are
strictly positive; and the candidate is nondominated on the deterministic
Pareto frontier. Its objectives are to maximize stress median continuous-symbol
return, stress minimum continuous-symbol return, positive continuous-symbol
count and positive asset/year-cell count, and to minimize stress worst
continuous-symbol drawdown and stress median turnover. Equal objective vectors
remain ties. Every other completed non-zero-trade candidate is
`ECONOMICALLY_REJECTED`. `ZERO_TRADE` means exactly zero BUY entries across the
full discovery panel. Raw return alone never determines the terminal class.
Stress median turnover is the median across the 24 annual asset/year cells,
following the accepted A147 aggregate-summary convention.

The selection-bias gate applies only to the 12 previously shortlisted G1
programs. Shortlisting itself grants no lifecycle promotion and the separate
selection-bias disposition does not change the G1 terminal ledger.

## Generation filtering

Generation-1 output is descriptive. It does not directly create a production
candidate.

Every frozen G1 proposal receives its acceptance event before the first
evaluation call. The runner keeps interim outcomes private and appends terminal
records only after every proposal has been attempted and the complete ordered
panel has been analyzed. Completed outcomes then expose P&L and diagnostics;
deterministic evaluation failures expose diagnostics only because they have no
result P&L. The consumed G2 proposal set cited exact visible G1 diagnostics
before its one-shot evaluation. Once any G1 terminal output is visible, the
ledger rejects additional G1 proposals.

The deterministic analyzer must validate the complete ordered frozen proposal
set and complete result panel before applying the terminal rule above. It may
not calculate a frontier from a cherry-picked subset. Pareto comparisons use
the six frozen stress dimensions; ties remain ties and no hidden epsilon or
extra tie-break is allowed.

The AI may diagnose the frontier but may not change the already completed
Generation-1 rules.

## Generation 2

Generation 2 was frozen to exactly six structural recombinations. The campaign's
maximum remains **16 evaluated G2 trials**. The six frozen trials were consumed
once, leaving ten unused. No prose variants, additional candidates or reruns
may fill the unused budget.

The accepted G1 proposal set is
`b2b3cadc-c11d-5a7a-be0b-5a2e16b9b39b`, its terminal ledger is
`68418f44-7db0-5080-a6bd-a956a928bd4a`, and its complete-panel analysis is
`d5ca081e-7490-5590-921d-10cee373d012`. The G2 proposal set binds all three
identities, its own source HEAD/tree, the ordered six proposal and semantic
program identities, each exact pair of G1 parent proposal IDs, and both exact
visible parent diagnostic references from that accepted terminal ledger. It
records a maximum budget of 16, six planned evaluations, zero confirmation
result visibility at freeze, and a sealed `FINAL_HOLDOUT`. The G2 source-only
checkpoint created no real proposal or result artifact. The later one-shot
campaign run and its terminal dispositions are recorded above.

Each G2 program is a closed `ConjunctiveTrendSpec` containing exactly two
supported G1 semantic specifications. The fixed operation for every pair is
`ALL_OF`.

| Order | First G1 parent | Second G1 parent |
| --- | --- | --- |
| 1 | `6ff56e8f-ab41-50f3-aa3b-2474bfb37537` — MA 35/50, fixed 1% band | `926f7b9f-d40f-5c4b-8e56-de498786e440` — 63-session absolute momentum, no SMA gate |
| 2 | `6ff56e8f-ab41-50f3-aa3b-2474bfb37537` — MA 35/50, fixed 1% band | `f6739ed9-f812-5f62-938c-6b0ea7407825` — 252-session absolute momentum plus SMA200 |
| 3 | `6ff56e8f-ab41-50f3-aa3b-2474bfb37537` — MA 35/50, fixed 1% band | `369a6806-1609-53b4-8972-b4d248505e2d` — 63/126/252 multi-horizon, 3_OF_3 |
| 4 | `c5d6574d-a9dc-5b4f-8a68-b95b1cdd3e59` — plain MA 35/50 | `926f7b9f-d40f-5c4b-8e56-de498786e440` — 63-session absolute momentum, no SMA gate |
| 5 | `b4c598f0-688d-5c81-b924-219fabd90e2a` — Donchian-20 plus MA 35/50 | `926f7b9f-d40f-5c4b-8e56-de498786e440` — 63-session absolute momentum, no SMA gate |
| 6 | `b4c598f0-688d-5c81-b924-219fabd90e2a` — Donchian-20 plus MA 35/50 | `369a6806-1609-53b4-8972-b4d248505e2d` — 63/126/252 multi-horizon, 3_OF_3 |

Component order is canonical, so A+B and B+A are one semantic trial. A proposal
uses `ProposalKind.RECOMBINATION`, names exactly those two G1 parent proposal
IDs, and has `GENERATION_2_PRE_CONFIRMATION` visibility. No arbitrary
expression, nested tree, `OR`, `NOT`, custom Python, weighted ensemble, extra
component or other G2 program is supported. At completed session `t`, the
composite is LONG only when both accepted parent signals are LONG. It is FLAT
otherwise. A state change executes at session `t+1` OPEN through the existing
A147 single-symbol path. No portfolio weighting or capital splitting is added.

The frozen confirmation view permitted pre-2022 bars for indicator warmup. Its
reported evidence was limited to `[2022-01-01, 2024-01-01)`, with calendar 2022,
calendar 2023 and continuous 2022-2023 slices. It rejects 2024 and later bars.
The accepted A147 daily dataset was the only market-data source. The original
A147 economics above remained unchanged, each symbol and reported slice used
an independent starting account, and `FINAL_HOLDOUT` was inaccessible.

At the source freeze, six evaluations were planned and zero G2 trials had been
evaluated. The subsequent one-shot campaign run consumed six trials. All six
were `CONFIRMATION_REJECTED`, none were `CONFIRMATION_PASSED`, and the G2
momentum-admission hypothesis is rejected. No confirmation metrics are included
in this validation contract or the G1 DSR search population.

A completed G2 candidate is `CONFIRMATION_PASSED` only if its STRESS metrics
meet all of these requirements.

- 2022 and 2023 median cross-asset returns are strictly positive.
- Continuous 2022-2023 median cross-asset return is strictly positive.
- At least 5 of 8 continuous-symbol returns are strictly positive.
- At least 9 of 16 asset/year returns are strictly positive.
- Continuous worst-symbol return is greater than `-0.10`.
- The candidate is nondominated on the complete completed-candidate population's
  confirmation frontier.

Every other completed result is `CONFIRMATION_REJECTED`.

The frozen Pareto dimensions maximize stress continuous median return, stress
minimum continuous-symbol return, positive continuous-symbol count and positive
asset/year count, while minimizing stress worst continuous drawdown and median
annual turnover. The frontier includes every completed G2 candidate, including
economically failing candidates. Deterministic failures have no metric vector,
remain diagnostic-only and are excluded from the frontier. Equal objective
vectors remain ties, with no hidden epsilon or tie-break.

Every frozen G2 proposal receives its acceptance event before the first
evaluator call. Interim outcomes remain private until all six evaluations and
complete-panel validation/analysis finish. Each attempted evaluation, including
a deterministic failure, consumes exactly one trial. Completed results may
then expose P&L and diagnostics. Deterministic failures expose diagnostics only.
The G1 ledger prefix and G1 results are immutable. G2 outcomes never promote a
candidate to `WALK_FORWARD_PASSED`, `SHADOW`, `PAPER_CANDIDATE`, live or
production status. DSR or an equivalently reviewed multiple-testing correction
remains required before a survivor may advance beyond exploratory `BACKTESTED`
research status. G2's terminal outcomes remain immutable and do not supply a
survivor for a further G2 generation.

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

The accepted discovery foundation represents AI proposals as supplied
canonical research input so tests remain deterministic and offline. The G1
source checkpoint preserves that boundary. An online model connector may be
designed later as a replaceable proposal producer.

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

The current implementation checkpoint is source-only selection-bias analytics
for the 12 previously shortlisted G1 programs. The G1 proposals, outcomes,
terminal dispositions and A147 behavior remain unchanged. The separate
selection-bias disposition does not modify the G1 trial ledger.

The synthetic return-series helper reconstructs one accepted G1 continuous
stress cell from its exact accepted fill evidence, adjusted daily bars for the
same symbol, the regime `[2019-01-01, 2022-01-01)`, and starting cash of
`$100,000`. It applies accepted fill, cash and position semantics, then marks
positions to adjusted daily close at each session end. It does not compute
signals or call the G1 evaluator. The helper recomputes
`semantic_identity("equity-trace", equity_values)` and requires exact equality
with the accepted `Metrics.equity_trace_identity`. A mismatch is terminal
evidence failure.

The eight continuous symbol sleeves each start with `$100,000`, for aggregate
initial equity of `$800,000`. On each common session the basket equity is the
sum of all eight sleeve equities, and its daily simple return is
`aggregate_equity[t] / aggregate_equity[t-1] - 1`. All eight accepted A147
symbols must be present on every basket session. There is no rebalancing,
capital transfer, optimization, or missing-session zero substitution.

Future real selection-bias observation accepts only the accepted G1 proposal
set, terminal ledger, outcomes and evidence, the accepted A147 dataset, exact
G1 identities and hashes, and the frozen campaign trial-count constants. It
rejects G2 outcomes or analysis objects, 2022-2023 confirmation metrics,
confirmation visibility as a ranking input, and `FINAL_HOLDOUT` data. The six
G2 trials contribute only to the campaign-wide sensitivity count of 28. Their
identities and performance do not affect the G1 ranking or DSR.

The separate versioned selection-bias evidence schema binds the campaign
version, exact G1 proposal-set, analysis and terminal-ledger identities, exact
accepted dataset and evidence identities, source HEAD and tree, the complete
22-program Sharpe population, the 12 eligible proposal IDs, all eight
reconstructed equity-trace identities, the aggregate basket-return identity,
the retained Sharpe and moment inputs, the DSR result, the 28-trial PSR
sensitivity, the terminal selection-bias disposition, zero-effect counters,
and the sealed `FINAL_HOLDOUT` flag. This source checkpoint creates no real
selection-bias artifact.

Only the 12 G1 shortlisted programs are eligible for the separate gate. A
candidate receives `SELECTION_BIAS_PASSED` only when its 22-trial DSR
probability is at least `0.95`, its campaign-wide one-sided PSR p-value is at
most `0.05 / 28`, all eight reconstructed trace identities match exactly, and
no input, evidence or chronology failure exists. Every other eligible program
receives `SELECTION_BIAS_REJECTED`. A pass permits only progression to the
separately frozen walk-forward gate. It does not confer `WALK_FORWARD_PASSED`,
`SHADOW`, `PAPER_CANDIDATE`, live or production status.

All tests for this source checkpoint use synthetic in-memory inputs. They do
not read real G1 outcomes, the accepted A147 dataset, G2 confirmation evidence,
or `FINAL_HOLDOUT`. No replay, real result artifact, AI API call, credential
read, provider or network call, Robinhood or broker call, order effect,
production-state read or write, or strategy promotion occurs in this source
checkpoint.

## Public research references

The campaign design is informed by, but does not copy code from:

- Bailey and Lopez de Prado, Deflated Sharpe Ratio:
  https://doi.org/10.3905/jpm.2014.40.5.094
- Siper et al., ProFiT: Program Search for Financial Trading:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5889762

These are hypothesis/process references only. Local deterministic evidence
controls every project decision.
