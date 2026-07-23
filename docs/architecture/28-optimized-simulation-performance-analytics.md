# Optimized-simulation performance analytics

## Scope and package boundary

`OptimizedSimulationPerformanceAnalyzer` is a read-only portfolio-analytics
adapter over one immutable `OptimizedPaperSimulationResult`. It lives in
`trading_bot.portfolio_analytics.optimized_simulation` because its inputs and
outputs describe ordered multi-symbol portfolio states rather than a
single-symbol backtest.

The analyzer never invokes optimization, target certification, planning, risk,
runtime, execution, ledger, CLI, market-data, broker, scheduling, persistence,
network, GPU, or AI behavior. It neither mutates nor requires access to the live
simulator that produced its source result.

Existing backtest analyzers are unchanged. The optimized analyzer reuses the
public `DrawdownRecord` and `DrawdownAnalysis` contracts but owns its private
observation calculation because simulation timing differs from backtest-close
snapshots.

## Public request and valuation policy

`OptimizedSimulationPerformanceRequest` retains a caller-supplied UUID, the
complete simulation result, `OptimizedSimulationValuationPolicy`, and an
immutable ordered metadata tuple. Metadata keys are unique and the
`optimized_simulation_performance_` prefix is reserved.

Version one supports only
`OptimizedSimulationValuationBasis.FRAME_RISK_PRICES`. Pre- and post-cycle
positions use the frame's risk price. Fill prices change cash, cost basis,
realized P&L, commissions, and slippage but are never substituted as valuation
marks. Missing, nonfinite, nonpositive prices or nonpositive required equity
raise `OptimizedSimulationValuationError`.

## Immutable source validation and reconstruction

Analysis has three phases:

1. Validate the immutable simulation audit, chronology, component-state chains,
   and global order, event, and fill identities.
2. Reconstruct a complete post-cycle portfolio for every frame.
3. Calculate and reconcile frame and aggregate metrics.

The first `derived_state` is the opening state. It provides ordered symbols,
cash, quantities, average costs, risk prices, and equity. Lifetime realized P&L,
opening fills, and original entry timestamps are not present.

Each frame starts from its complete derived state. Fills and application records
are processed together in retained order. A buy reduces cash by notional plus
commission and adds the same amount to cost basis. A sell removes average cost
times quantity, credits notional less commission, and realizes proceeds less
commission and removed basis. Expected cash and the affected public position are
compared exactly with every application record before reconstructed state is
advanced.

Application-level lifetime realized values are used only to validate a stable
unknown pre-simulation baseline. Public analytics report simulation-relative
realized P&L calculated from source simulation fills.

A no-action cycle must contain no orders requiring fills, fills, or application
evaluations and must preserve component state IDs. Its post state equals its pre
state.

Adjacent frames require equal cash, quantities, and average costs between the
prior reconstructed post state and next derived state. Held symbols must remain
covered. New symbols may enter only as flat ordered positions. Price changes are
allowed and represent market performance.

## Valuation, exposure, and positions

For either pre- or post-cycle state at frame risk prices:

```text
market value = sum(quantity * risk price)
equity = cash + market value
gross exposure = sum(abs(quantity * risk price))
net exposure = sum(quantity * risk price)
position count = count(quantity > 0)
unrealized P&L = sum(quantity * risk price - remaining cost basis)
```

The platform is currently long-only, so gross and net exposure normally agree;
both are retained to keep their meanings explicit.

## Execution and forward market performance

Within one frame:

```text
execution P&L = post-cycle equity - pre-cycle equity

BUY impact  = quantity * (risk price - fill price) - commission
SELL impact = quantity * (fill price - risk price) - commission
```

The equity difference must equal the ordered fill-impact sum.

For every nonfinal frame:

```text
forward market P&L = next pre-cycle equity - current post-cycle equity

= sum(current post quantity
      * (next risk price - current risk price))
```

Cash must be unchanged across that boundary. The final frame has
`forward_market_profit_loss=None`; no terminal price is invented.

## Period returns

For nonfinal frames:

```text
period P&L = execution P&L + forward market P&L
           = next pre-cycle equity - current pre-cycle equity
```

For the final frame, period P&L is execution P&L. Each period return divides by
that frame's positive pre-cycle equity.

Cumulative P&L is the period endpoint equity minus initial equity. Cumulative
return is calculated from that exact endpoint ratio, which is algebraically the
ordered product of period growth factors while avoiding additional rounding for
repeating Decimal divisions:

```text
cumulative return = cumulative P&L / initial equity
```

The final values reconcile with:

```text
absolute simulation P&L = final post equity - initial pre equity
simulation return = absolute simulation P&L / initial pre equity
```

A one-frame result therefore measures execution impact only.

## Equity observations and drawdown

The canonical observation order is:

```text
frame 0 PRE_CYCLE
frame 0 POST_CYCLE
frame 1 PRE_CYCLE
frame 1 POST_CYCLE
...
```

PRE uses `frame.as_of`; POST uses `frame.filled_at`. Equal timestamps are valid;
sequence index and phase preserve deterministic order. Every observation retains
equity, running peak, drawdown amount, and drawdown percentage.

Running peaks update only for a strictly greater equity. Dollar and percentage
drawdown maxima are tracked separately, and ties retain the earliest
observation.

## Simulation-relative P&L

Initial and per-frame unrealized P&L use retained average cost and risk prices.
Every sell contributes simulation-relative realized P&L through average-cost
accounting. The aggregate identity is:

```text
absolute simulation P&L
= cumulative simulation realized P&L
  + final unrealized P&L
  - initial unrealized P&L
```

The analyzer does not construct `TradeRealization`: entry timestamps for
positions opened before the simulation are unavailable. It does not report
lifetime ledger realized P&L.

## Trading notionals and turnover

Per frame:

```text
gross buy notional = sum(BUY fill notional)
gross sell notional = sum(SELL fill notional)
gross traded notional = buys + sells
net buy notional = buys - sells

one-way turnover = max(buys, sells) / pre-cycle equity
two-way turnover = (buys + sells) / pre-cycle equity
```

Aggregate turnover uses average pre-cycle equity, matching the existing
portfolio-analytics denominator convention:

```text
average pre equity = sum(frame pre equity) / frame count
aggregate one-way turnover = sum(max(frame buys, frame sells)) / average pre equity
aggregate two-way turnover = total gross traded notional / average pre equity
```

There is deliberately no ambiguous generic `turnover` alias.

## Commissions and slippage

Commission cost is the fill-commission sum. Signed slippage P&L is:

```text
BUY  = (reference price - fill price) * quantity
SELL = (fill price - reference price) * quantity
```

Adverse slippage cost sums `max(-signed fill slippage, 0)`. Favorable slippage is
retained in signed P&L and is not rejected. Total execution cost is commissions
plus adverse slippage cost. Execution P&L need not be its negative because frame
risk and fill-reference prices can differ.

## Risk and optimization summaries

Each frame retains approved, resized, and rejected risk counts. Rejected
notional is desired quantity times risk price for rejected decisions. Reduced
notional is desired minus approved quantity times risk price for resized
decisions; the two concepts remain separate.

Frame optimization audit includes status, solver, expected portfolio return,
CVaR, objective, target cash weight, and allocation count. Aggregate summaries
are arithmetic mean expected return, worst (maximum) CVaR, and minimum/maximum
target cash weight. Objective values are not aggregated.

## Allocation drift

Post-cycle actual weights use frame risk prices and positive post equity:

```text
asset actual weight = quantity * risk price / post equity
cash actual weight = post cash / post equity
drift = actual weight - target weight
```

Asset records follow exact target order. Cash drift is explicit and does not use
a synthetic symbol. Target and actual totals must equal one, and asset plus cash
drifts must sum exactly to zero. No value is quantized or normalized. Maximum
absolute drift and total absolute drift include cash.

## Deterministic identity and result validation

UUID5 identities use `optimized-simulation-performance-v1`. Frame identity
includes the analytics request, source simulation and cycle IDs, valuation
policy, all canonical frame metrics, and ordered allocation drift. Aggregate
identity includes ordered metadata, frame IDs, observations, separate drawdown
maxima, aggregate metrics, optimization summary, and diagnostic codes.

Canonical finite Decimal text is used. Messages, object identity, clocks,
Python hashes, and incidental mapping order are excluded.

The immutable result validates types, frame and observation ordering, initial
and final relationships, P&L and return identities, ordered sums and counts,
turnover, allocation drift, drawdown maxima, diagnostics, frame IDs, and result
ID. It does not rerun fill reconstruction.

## Exceptions and diagnostics

Expected failures use:

- `InvalidOptimizedSimulationPerformanceRequestError`
- `OptimizedSimulationValuationError`
- `OptimizedSimulationPerformanceReconciliationError`
- `InconsistentOptimizedSimulationPerformanceResultError`

Valid limited results use only `NO_TRADING_ACTIVITY` and
`ALL_CYCLES_NO_ACTION`. Diagnostics never hide malformed source data.

## Limitations and deferred work

CLI configuration may create synthetic bootstrap fills, but those fills are not
part of `OptimizedPaperSimulationResult` and are not simulation activity.
Opening quantities and basis are recoverable from the first derived state;
historical entry timestamps, lifetime realized P&L, and opening fill history are
not.

Annualized volatility, Sharpe ratio, CAGR, irregular-period annualization,
benchmarks, charts, CLI summary/audit integration, persistence, and live
operation remain deferred.
