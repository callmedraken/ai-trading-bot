# Performance analytics

The performance-analytics layer reads an immutable `BacktestResult` and
derives deterministic metrics without changing strategies, risk decisions,
orders, fills, accounting, or backtest behavior. `PerformanceAnalyzer` is
stateless and returns an immutable `PerformanceReport`.

## Returns and trade realizations

Absolute profit or loss is final equity minus configured starting cash. Total
return is that amount divided by starting cash. Final unrealized profit or loss
therefore contributes to return even though it does not create a realization.

Each sell fill creates one `TradeRealization`; this is not necessarily a full
flat-to-flat round trip. Buys add gross notional plus commission to pooled cost
basis. A sell removes `average cost * quantity`, deducts its commission from
proceeds, and realizes net proceeds minus removed basis. This matches
`PaperLedger`. Partial exits preserve the earliest contributing buy timestamp
as `entry_started_at`; a full exit resets it before a later position begins.

Winning, losing, and breakeven records have profit or loss greater than, less
than, and equal to zero respectively. Win rate is winning realizations divided
by all realizations, including breakeven records. Gross profit sums positive
records and gross loss sums negative records. Average category values are zero
when that category is absent. Profit factor is gross profit divided by the
absolute gross loss. It is `None` when gross loss is zero; console reporting
distinguishes no gross loss from no profit-or-loss activity, while JSON uses
`null` for both.

## Drawdown

The account-snapshot equity curve establishes a running peak. At each snapshot,
dollar drawdown is peak equity minus current equity, and percentage drawdown is
that amount divided by peak equity. A zero peak has zero percentage drawdown.
Equal peaks retain the earliest timestamp, and equal maxima retain the earliest
trough.

Maximum dollar drawdown and maximum percentage drawdown are selected
independently because they can arise from different peaks and troughs.
`DrawdownAnalysis` stores a complete `DrawdownRecord` for each maximum.

## Turnover, exposure, and time in market

Two-way turnover is the sum of absolute executed fill notional (`quantity *
price`) for buys and sells divided by arithmetic mean snapshot equity.
Commission is excluded from executed notional. The formula is deliberately not
divided by two. Zero average equity is allowed only with zero executed notional.

Gross exposure at a snapshot is positions market value divided by equity.
Zero equity with zero exposure produces a zero ratio; zero equity with positive
exposure is inconsistent. Average and maximum exposure use those close-valued
snapshot ratios. Time in market is the number of snapshots with positive
positions market value divided by snapshot count. These are daily close-state
observations and imply no intraday holding duration or market hours.

## Audit validation and determinism

Analysis requires at least one snapshot; equal bar, step, and snapshot counts;
nondecreasing snapshot and fill timestamps; finite nonnegative equity and
market values; unique fill IDs; one matching symbol; and fill timestamps inside
the completed backtest interval. Reconstruction rejects oversells and must
match both final positions and final realized profit or loss. Final snapshot
equity must equal `BacktestResult.final_equity`. Inconsistency fails with
`InconsistentBacktestAuditError` rather than returning partial metrics.

The analyzer copies no mutable engine state, reads no clock or network, and
uses `Decimal` throughout. Equal immutable results produce equal reports.

## Reporting and deferred scope

The offline CLI appends analytics to its console summary. Numeric JSON report
schema version 2 adds a deliberate `performance` section with both drawdown
records, trade statistics, turnover, exposure, time in market, and explicit
realization records.

Sharpe ratio, CAGR, annualized volatility, benchmarks, optimization, charts,
networking, AI, broker functionality, and intraday analytics remain deferred.
