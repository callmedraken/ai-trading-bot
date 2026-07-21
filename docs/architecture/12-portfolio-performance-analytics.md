# Portfolio performance analytics

The additive `portfolio_analytics` package reads an immutable
`MultiSymbolBacktestResult` and returns an immutable
`PortfolioPerformanceReport`. It does not alter strategy, risk, execution,
ledger, backtest, CLI, or reporting behavior. The existing single-symbol
analytics API remains unchanged.

## Average-cost reconstruction

Fills are processed in their recorded global application order while an
independent quantity, cost-basis, and entry-start timestamp is maintained for
each configured symbol. Buy basis is fill notional plus commission. A sell
removes `average cost * sold quantity`; net proceeds are sell notional minus
commission, and realized profit or loss is net proceeds minus removed basis.
Every sell fill creates one reused analytics `TradeRealization`, including a
partial exit. Partial exits retain the earliest contributing buy timestamp.
Full exits normalize quantity and basis to zero and reset that timestamp before
a later re-entry. Realizations remain in global sell-fill order.

`TradeRealization`, `DrawdownRecord`, and `DrawdownAnalysis` are reused because
their contracts are symbol-local or equity-curve based. `PerformanceReport` is
not reused; portfolio reports additionally contain ordered symbol summaries,
executed notional, and exposure history.

## Portfolio metrics

Absolute profit or loss is final equity minus starting cash. Total return is
that value divided by positive configured starting cash. Winners, losers, and
breakeven realizations are classified by exact `Decimal` comparison. Win rate
is winners divided by all realizations, including breakeven realizations.
Gross loss remains negative. Empty category averages are zero. Profit factor
is gross profit divided by absolute gross loss and is `None` when gross loss is
zero.

Two-way executed notional is the sum of `quantity * price` over every buy and
sell fill; commission is excluded. Turnover is executed notional divided by
arithmetic mean snapshot equity. Positive average equity is required unless
both average equity and executed notional are zero, which produces zero
turnover.

Each exposure record uses its actual snapshot timestamp, which must equal the
corresponding frame timestamp. Gross exposure is aggregate positions market
value divided by equity. Zero equity and zero market value produce zero; zero
equity with positive market value is inconsistent. Average and maximum gross
exposure use these close-valued observations. Time in market is the fraction
of snapshots with positive positions market value. No intraday duration or
session-close timestamp is inferred.

Maximum dollar and percentage drawdowns are selected independently from the
snapshot equity curve. Running-peak, earliest-equal-peak, earliest-equal-trough,
and flat-curve behavior match single-symbol analytics and use only actual
snapshot timestamps.

## Symbol summaries and final valuation

One `SymbolPerformanceSummary` is emitted for every configured symbol in
configured order, including never-traded symbols. It contains fill counts and
notional, realization classifications and profit or loss, and final position
values. No per-symbol turnover ratio or historical per-symbol exposure is
reported.

For an open final position, market value is final quantity times the symbol's
final-frame close. Remaining basis is quantity times average cost, and final
unrealized profit or loss is market value minus basis. Buy commissions are
already in average cost; no hypothetical exit commission is deducted. Symbol
realized and final unrealized values are additive monetary amounts, not formal
return attribution or percentage contributions.

## Audit validation and determinism

Analysis validates a nonempty duplicate-free ordered universe; complete frames
in that order; aligned nonempty frame, step, and snapshot tuples; zero-based
contiguous step indexes; exact step/frame/snapshot associations; chronology;
finite financial values; and exact result fill ordering.

Every fill must have a unique ID, occur at an actual frame timestamp, reference
one final order, match its symbol, side, and full quantity, follow one
submission event, and have one matching filled event. The full-fill engine may
not record multiple fills for one order. Final filled order snapshots must
reconcile with their fills. This checks available audit identities without
duplicating the complete `OrderEngine` state machine.

Per-symbol reconstruction rejects overselling and must exactly match final
positions and average costs. Flat positions must be absent. Reconstructed
realized profit or loss, final market value, and final unrealized profit or
loss must match the final snapshot. Final equity must equal cash plus positions
market value, and equity less starting cash must equal realized plus unrealized
profit or loss.

All public collections are immutable tuples. Realizations use global sell-fill
order, summaries use configured-symbol order, and exposure and drawdown records
use snapshot/frame order. The analyzer reads no clock, network, mutable engine
state, or incidental mapping priority, so equal inputs produce equal reports.

## Deferred scope

Historical per-symbol exposure, percentage or return attribution, portfolio
CLI and serialization, annualization, Sharpe and Sortino ratios, CAGR,
benchmarks, target weights, optimization, scenarios, charting, AI, GPU tools,
networking, and brokerage functionality remain deferred.
