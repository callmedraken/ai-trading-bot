# Architecture 148 late-session intraday momentum research — design frozen

## Status and authority

This document freezes the next source-only OPEN research design after the
accepted Architecture 148 churn study rejected CONTROL and all three fixed
churn-reduction variants. It does not contain executable source, report an
evaluation result, select a live strategy, grant provider/broker authority, or
access `FINAL_HOLDOUT`.

The design uses only the already accepted sparse Architecture 148 OPEN dataset
and custody identities:

- dataset `0308b694-c718-5b1a-a51c-9fcc4516bb81`, SHA-256
  `0ba8b2437ef27a98fc48855aa8bb8d27ca3cdc0f2888e214305dde760686dbe0`;
- custody `dbcced6a-b4cc-5d36-a33b-5e6df3d82baa`, SHA-256
  `93db9a9163cf445fdfd61abe68559196d240b09c1c9b70cdc0f7f452e3e8708b`;
- accepted sparse requalification evidence SHA-256
  `bdad3ab1f387617e2cef35644680e397c94d113f77f48cc242857151b352788d`;
- accepted sparse baseline SHA-256
  `38cbba9beae664c675670af1ad96e86a56df2a9060c6cb924c1ad51ea4f9b85f`;
- accepted churn evidence SHA-256
  `5baa7ef9e035f72428c623c798fb9653aa43339027c03e8e417d16c52e08aca8`.

No provider retry or new acquisition is authorized. The dense B1 qualification
failure remains historical and unchanged.

## Research hypothesis and public reference

Gao, Han, Li and Zhou, *Market Intraday Momentum*, Journal of Financial
Economics 129(2), 2018, documents that the first half-hour market return,
measured from the previous day's close, predicts the last half-hour return in
SPY and reports the pattern in other actively traded ETFs:

- https://doi.org/10.1016/j.jfineco.2018.05.009
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866

This project does **not** assume that result transfers to QQQ, TQQQ or SQQQ.
The paper is a research-hypothesis reference only; no third-party code is copied
or imported. The local test is intentionally simpler than a parameter search:
one fixed signal, one fixed entry time, one fixed holding rule and the two
already accepted cost cases.

The local rule is a safety-aligned adaptation rather than a literal replication
of the paper's last-half-hour trade. Architecture 148 retains its mandatory
forced-flat boundary beginning five minutes before official close, so the fixed
research exposure window starts at close minus 35 minutes and ends at close
minus 5 minutes.

## Fixed candidate: `OPENING_DRIVE_LATE_CAPTURE_V1`

There is exactly one candidate. No threshold grid, alternative opening-range
length, volatility filter, cooldown, indicator regime, or post-hoc variant is
part of this checkpoint.

For each expected XNYS regular session:

1. Resolve the immediately preceding expected XNYS regular session.
2. `previous_close` is the close of that prior session's final qualified QQQ
   five-minute bar. If that observation is unavailable, the current session is
   ineligible with reason `MISSING_PREVIOUS_QQQ_CLOSE`.
3. Require all six expected QQQ five-minute bars spanning the current session's
   first 30 regular-session minutes. The sixth bar's close is
   `first_half_hour_close`. Any missing required slot makes the session
   ineligible with reason `INCOMPLETE_FIRST_HALF_HOUR_QQQ`; no interpolation
   or carry-forward is allowed.
4. Compute
   `opening_drive_return = first_half_hour_close / previous_close - 1`
   under the repository's explicit Decimal context.
5. If the return is positive, the day's target is TQQQ. If negative, the target
   is SQQQ. If exactly zero, the session is ineligible with reason
   `ZERO_OPENING_DRIVE`.
6. No EMA, VWAP, RSI, two-bar regime confirmation, magnitude threshold or
   intraday regime flip changes that direction.
7. The only normal entry opportunity is the real target-ETF bar whose timestamp
   is exactly official regular-session close minus 35 minutes. Entry uses that
   bar's OPEN and the existing cost-model execution-price semantics. If the
   exact target bar is absent, skip the session with reason
   `MISSING_SCHEDULED_ENTRY_BAR`.
8. At most one position may be opened in the session. There is no same-session
   re-entry, inverse flip, cooldown, normal regime exit, or second entry.
9. The existing 3.00% hard stop is active immediately from the entry fill and
   retains current conservative entry-bar gap/breach semantics.
10. Otherwise hold the position until the earliest existing mandatory safety
    exit or the existing forced-flat boundary beginning at official close minus
    5 minutes. The current sparse simulator's real-bar-only execution,
    missing-held-bar pending-exit behavior and final-session flatten invariant
    remain authoritative.
11. Early-close sessions use the published XNYS close and the same relative
    `close-35m` / `close-5m` timing. Nothing is hard-coded to 15:25 or 15:55.
12. The session ends FLAT. No position or research state carries overnight.

The candidate therefore changes both the signal architecture and holding
architecture relative to the rejected baseline: one early-session directional
measurement controls one late-session trade, and indicator-regime reversals do
not terminate the holding period.

## Cost cases, capital path and partitions

Run exactly the two already accepted cost cases:

- `ZERO_COST`;
- `CONSERVATIVE_10_BPS`.

Do not add a spread stress, alternate commission, threshold or cost model after
results are visible.

Reuse the accepted OPEN interval `[2016-01-01, 2024-01-01)`, accepted
`ALPACA_ALL_ADJUSTED_INTRADAY_PRICE_V1` price basis and accepted XNYS
schedule. Report `OPEN_FULL` plus the eight disjoint calendar-year partitions
2016 through 2023.

As in the accepted churn study, replay is one continuous compounding path
starting FLAT with $10,000. Each calendar-year reporting partition begins FLAT
with the preceding partition's ending equity; the partition boundary is a
reporting boundary, not a fresh optimization run.

The accepted sparse baseline and churn records are immutable comparators. Do
not overwrite or reinterpret them and do not rerun them merely to create a new
control.

## Required diagnostics

For each cost case and each reporting partition, preserve empty partitions and
report at minimum:

- gross and net strategy return;
- QQQ buy-and-hold return over the same partition;
- maximum drawdown;
- eligible-session count, traded-session count and no-trade count;
- complete no-trade reason distribution;
- TQQQ-entry count and SQQQ-entry count;
- completed trade count and turnover;
- stop, safety and forced-flat exit counts with complete exit-reason
  distribution;
- win rate, average win, average loss, average and median holding duration;
- first-half-hour QQQ direction hit rate against QQQ's return over the fixed
  `close-35m` to `close-5m` research window;
- mean and median QQQ research-window return conditioned separately on positive
  and negative opening drive;
- mean and median realized target-ETF trade return separately for TQQQ and
  SQQQ;
- count of missing previous-close sessions, incomplete first-half-hour sessions,
  missing scheduled-entry bars and any sessions whose open position encounters
  missing held-ETF observations;
- early-close session count and traded early-close session count;
- deterministic trade-audit hash and equity-series hash.

The evidence must bind the exact source commit/tree, design/version identifier,
dataset/custody/requalification identities, schedule identity, simulator
version, cost case, partition and effect counters.

## Frozen result classification

This OPEN study has no automatic live/default promotion rule.

For descriptive continuation only:

- classify `ECONOMICALLY_REJECTED` if the
  `CONSERVATIVE_10_BPS` `OPEN_FULL` net return is not positive **or** the
  median of the eight conservative calendar-year net returns is not positive;
- otherwise classify `OPEN_CANDIDATE_ONLY`.

`OPEN_CANDIDATE_ONLY` means only that a separately frozen confirmation /
holdout decision may be considered. It does not authorize `FINAL_HOLDOUT`,
live-runtime replacement, provider reads, broker effects or production use.
No rule may be relaxed after results are visible.

## Implementation boundary

The intended checkpoint route is
`arch148-intraday-momentum-research`. It is source-only/fake-only and must
have no provider, Robinhood, broker, production-state or holdout dispatch.

Expected source ownership is a new Architecture 148 research policy/replay
module, with the smallest explicit extension to
`arch148_sparse_backtest.py` only if necessary to reuse accepted fill, stop,
missing-bar and valuation semantics. Do not change the accepted live runtime
strategy in this checkpoint.

Focused tests must pin at least:

- previous-session close linkage;
- all-six first-half-hour QQQ completeness;
- exact positive/negative/zero direction mapping;
- close-relative entry timing including early closes;
- one-entry-per-session and no re-entry;
- absence of regime-exit behavior;
- immediate entry-bar hard-stop handling;
- safety and forced-flat priority;
- sparse missing-entry and missing-held-bar behavior;
- deterministic identities/hashes and both cost cases;
- `FINAL_HOLDOUT` exclusion and zero provider/broker effects.

The source checkpoint must freeze these semantics before replay. After an exact
local commit and general source admission, the OPEN evaluation may run as a
separately named offline evidence step bound to that exact source before
publication, following the same evidence-preservation model used by the
accepted churn study. Mapped GitHub CI remains an admission/certification gate,
not the research execution engine.

If implementation discovery requires changing this contract, STOP and return to
ChatGPT for a new design decision before evaluating any P&L.
