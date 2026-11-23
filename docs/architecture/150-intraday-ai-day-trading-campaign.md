# Architecture 150 — Intraday AI day-trading research campaign

Status: **DESIGN FROZEN; FOUNDATION + D1 + D1R + D1R-C1 SOURCE ACCEPTED/INTEGRATED; SPARSE 2016-2023 CUSTODY ACCEPTED; SPARSE-REPLAY SOURCE CHECKPOINT NEXT; REAL STRATEGY P&L REMAINS CLOSED**.

## Product goal

Architecture 150 restores the primary product goal: an autonomous intraday
trading bot that searches for same-day opportunities, opens and closes positions
during the regular session, and finishes every session FLAT.

The objective is frequent daily opportunity, not forced daily profit. A valid
strategy may skip a session when its frozen edge is absent. No strategy may
promise positive P&L every day.

Architecture 149 remains preserved as a secondary low-turnover benchmark and
possible capital-parking strategy. Its 2024-2026 confirmation contract remains
valid but is deferred and does not block Architecture 150.

## Research principle

AI acts only as a bounded hypothesis generator and analyst.

Deterministic repository code owns:

- market-data custody;
- chronology;
- feature calculation;
- entries/exits;
- fills and costs;
- position/risk limits;
- trial accounting;
- walk-forward/holdout boundaries;
- statistics;
- promotion decisions.

AI never directly chooses a live order from natural-language reasoning.

## Primary instruments

Initial research signal universe:

- SPY;
- QQQ.

Initial execution research uses the same unleveraged instrument as its signal.
TQQQ/SQQQ or other leveraged/inverse mappings are a later translation study
only after an underlying intraday edge survives holdout.

This prevents leverage decay/slippage from being confused with signal quality.

## Bar resolution and session

Primary source resolution:

- 1-minute adjusted intraday bars when available from the accepted provider;
- regular XNYS session only;
- explicit published session authority;
- no overnight positions;
- mandatory flat before or at the regular close.

A 5-minute derived view may be built deterministically from accepted 1-minute
bars. No independent 5-minute provider acquisition is needed for the same
interval when exact aggregation is possible.

### Sparse minute-bar semantics after the consumed D1 acquisition

The first real D1 acquisition is immutable and consumed. Both SPY and QQQ
pagination streams exhausted successfully, but the original dense custody rule
blocked because Alpaca emitted no bar for a small number of scheduled XNYS
minutes. A second provider acquisition is forbidden.

Architecture 150 therefore treats the next step as an **offline custody
requalification**, not a retry and not a strategy run. The requalifier may read
only the preserved D1 raw pages/evidence and must perform zero credential,
provider, broker, order, holdout, extension, or strategy-P&L effects.

The sparse custody contract is frozen before detailed missing-timestamp
inspection:

- a missing scheduled minute remains an explicit absent observation; never
  forward-fill, backfill, interpolate, synthesize OHLCV, or substitute another
  symbol;
- every observed regular-session bar must still be exact-symbol, exact-minute,
  unique, strictly ordered, on the accepted published XNYS schedule, and within
  the frozen 2016-2023 boundary;
- pagination must be exhausted for both symbols and every preserved raw-page
  byte/hash/request descriptor must revalidate before sparse custody can be
  READY;
- sparse custody records the exact scheduled-slot count, observed count,
  missing count and missing-timestamp digest per symbol, plus common/union
  missing sets and per-session gap diagnostics;
- the original dense D1 dataset remains BLOCKED and immutable. Sparse
  requalification creates a new identity/schema and never rewrites the original
  attempt or claims that its dense qualification passed;
- no numeric missing-count threshold is selected after seeing the result.
  Sparse custody is a truthful representation of provider bars, not a
  completeness waiver.

Real strategy P&L remains closed after sparse custody. Before the frozen G1
population can be evaluated, a separate source-only sparse-replay checkpoint
must make the accepted deterministic replay semantics explicit:

- no bar-dependent decision or fill occurs at an absent minute;
- confirmation that requires consecutive bars cannot bridge a missing scheduled
  minute;
- VWAP uses only observed eligible-trade bars/volume and receives no synthetic
  price or volume contribution for an absent minute;
- a derived 5-minute bar exists only when all five aligned 1-minute source bars
  exist; otherwise that 5-minute decision point is unavailable;
- elapsed-time hold limits use wall-clock/session time, so an absent minute
  still consumes elapsed holding time;
- an existing position is not retroactively erased because a later minute is
  absent. The replay must remain causal and may evaluate it again only on the
  next observed eligible-trade bar;
- frequency denominators remain the full published XNYS session population for
  the stage, so sparse data cannot inflate activity ratios by deleting hard
  sessions from the denominator.

The sparse-replay checkpoint is synthetic/source-only. It must be accepted
before the complete G1 population is frozen and before any real discovery P&L
is opened.

## Historical research chronology

No future waiting is required.

Freeze the following chronology before acquisition/result visibility:

### Discovery

`[2016-01-01, 2021-01-01)`

Used for bounded AI hypothesis generation and deterministic candidate fitting.

### Validation / walk-forward

`[2021-01-01, 2024-01-01)`

Used for chronological walk-forward validation and candidate reduction.

### Final historical holdout

`[2024-01-01, 2026-01-01)`

Calendar years 2024 and 2025 are the untouched final holdout.

The holdout is not acquired/opened by the campaign until the final candidate
set and all pass/fail rules are frozen.

### Recent-regime extension

`[2026-01-01, 2026-11-01)`

This fixed extension contains complete calendar months January through October
2026 only. It is opened only after the 2024-2025 holdout result is terminal.

November and December 2026 are not required for Architecture 150 qualification.

## Intraday strategy families

Generation 1 searches only a closed typed grammar across three independent
families supported by public intraday research.

### A. Noise-area / VWAP momentum

A deterministic version of the published intraday momentum family:

- intraday equilibrium/noise band derived only from past sessions;
- VWAP confirmation;
- fixed regular-session decision grid;
- same-day trailing/exit logic;
- flat by close.

No leverage is allowed in Generation 1.

### B. VWAP regime trend / reversal

Deterministic VWAP-relative state rules using only completed bars:

- continuation above/below VWAP;
- bounded reversal after statistically extreme displacement from VWAP;
- same-day entry/exit only;
- explicit churn limits.

Always-in-market high-churn VWAP switching is a benchmark, not an automatic
promotion candidate.

### C. Opening-range / early-session breakout-reversal

Deterministic rules built from a fixed early-session range and later completed
bars.

Both continuation and reversal forms may exist in the grammar, but each program
must declare one direction model before evaluation.

The rejected Architecture-148 first-half-hour-to-last-half-hour rule is excluded
from this family and may not be regenerated.

## Candidate budget

Generation 1 maximum:

- 24 total evaluated programs;
- maximum 8 per family.

Every attempted program consumes one trial, including:

- invalid;
- duplicate;
- zero-trade;
- deterministic failure;
- economically rejected;
- shortlisted.

Generation 2, if separately authorized, is limited to at most 12 structural
recombinations of already frozen G1 survivors.

No open-ended optimization or Bayesian search is allowed.

## Frequency boundary

The bot is intended to trade intraday frequently.

A completed candidate cannot advance from validation unless, under STRESS:

- it has at least 100 completed round trips per validation calendar year on
  average; and
- it trades on at least 35% of validation regular sessions; and
- median trades per active session is no more than 3.

This rejects both near-buy-and-hold behavior and pathological hyper-churn.

No rule is forced to trade every session.

## Session and risk boundary

Every candidate:

- starts each session flat;
- ends each session flat;
- may hold at most one directional position per instrument;
- may not carry overnight;
- may not pyramid;
- may not martingale;
- may not average down;
- may not use options;
- may not use external news/LLM sentiment in Generation 1.

Maximum simultaneous gross exposure in research is 100% of portfolio equity.

## Costs

Freeze explicit per-fill economics before evaluation.

BASE:

- $0 commission;
- 2 bps adverse slippage per fill.

STRESS:

- $0 commission;
- 5 bps adverse slippage per fill.

Also preserve a zero-friction diagnostic, but zero-friction P&L can never qualify
a candidate.

These ETF-focused assumptions are separate from the older A147/A148 cost
contracts and are frozen for Architecture 150 before any P&L is opened.

## Discovery and validation ranking

Raw return alone is forbidden.

Use deterministic multi-objective ranking on validation including at minimum:

- net return;
- Sharpe;
- maximum drawdown;
- profit factor;
- median trade expectancy;
- positive-month breadth;
- active-session fraction;
- turnover;
- worst calendar-year return.

Candidates with nonpositive STRESS validation net return are rejected.

Candidates with profit factor <= 1 under STRESS are rejected.

Candidates failing the frequency boundary are rejected.

Selection-bias correction is required across the complete trial ledger before
any final holdout access.

Use DSR or an equivalently reviewed multiple-testing correction against all
consumed search trials.

## Final holdout

Before 2024-2025 data is opened, freeze the final candidate set.

No mutation is allowed after holdout visibility.

A candidate passes historical holdout only if under STRESS:

- combined 2024-2025 net return > 0;
- both 2024 and 2025 calendar returns are > 0;
- profit factor > 1;
- maximum drawdown <= 0.25;
- active-session fraction >= 0.30;
- no single calendar month contributes more than 50% of total positive P&L.

Passing the holdout does not authorize live trading.

## 2026 recent-regime extension

Only candidates that pass 2024-2025 may open the fixed
`[2026-01-01, 2026-11-01)` extension.

No parameter or rule may change.

The extension passes only if under STRESS:

- net return > 0;
- profit factor > 1;
- maximum drawdown <= 0.20;
- at least 6 of the 10 complete months are positive;
- active-session fraction >= 0.30.

This extension is a recent-regime robustness check, not another search sample.

## Promotion boundary

A strategy that survives discovery, validation, selection-bias correction,
2024-2025 holdout and Jan-Oct 2026 extension becomes:

`INTRADAY_RESEARCH_SURVIVOR`

That grants permission only to build the deterministic paper/shadow runtime
binding.

It does not itself grant Robinhood order authority or replace the current live
strategy.

## Public research context

The campaign is motivated by evidence that intraday time-series momentum exists
in multiple markets, by published SPY noise-area/VWAP momentum work, and by
VWAP-based ETF day-trading research.

Those results are hypotheses, not accepted local evidence. Independent 2026
replication work also reports material deterioration of the SPY momentum
strategy after 2024, so Architecture 150 requires its own untouched historical
holdout and recent-regime extension rather than trusting headline in-sample
returns.

## Immediate milestone

The next checkpoint is source-only/fake-only campaign infrastructure plus a
historical intraday acquisition contract for SPY and QQQ discovery/validation
data only.

Do not acquire 2024+ data in that checkpoint.

Do not implement live execution.

Do not alter Architecture 149 evidence or confirmation semantics.
