# Deterministic rebalance planner

The additive `rebalancing` package converts an immutable `PortfolioState` and
`TargetPortfolio` into an immutable current-price planning estimate. It does
not create trade proposals, run risk, submit orders, mutate accounting, execute
fills, optimize allocations, or integrate with backtests or brokers.

## Request and assumptions

A `RebalancePlanRequest` has a caller-supplied UUID, state, target, assumptions,
optional portfolio constraints, and ordered metadata. State and target must
have identical ordered universes and exact matching UTC timestamps. The state
timestamp is the planning timestamp; no clock is read. Future stale-target
policy may add explicit age inputs.

Planner assumptions contain fixed commission per planned trade, fractional or
whole-share quantity precision, minimum trade quantity and notional, explicit
target-weight tolerance, an additive execution cash buffer, and whether planned
sell proceeds may fund buys. These estimates do not replace `RiskLimits`.

Planning equity is current equity. All target values and trades use unchanged
current prices:

```text
target market value = target weight * planning equity
target quantity = target market value / current price
```

Protected cash is:

```text
target cash weight * planning equity
+ additional execution cash buffer
```

A positive additive buffer may intentionally prevent exact target cash weight
and produce a partial plan.

## Sells, buys, and funding

Sell requested quantity is current quantity minus target quantity. Buy
requested quantity is target quantity minus current quantity. Trade quantities
are always positive. Sells are planned before buys, and both sides follow
configured symbol order.

All partial quantities round down with `Decimal` `ROUND_DOWN`. Buys never round
up. Partial sells never exceed ownership. A target-zero full exit uses exact
owned quantity and is explicitly exempt from increment alignment. A sell whose
gross proceeds are no greater than fixed commission is skipped.

With sell funding enabled:

```text
cash after sells = current cash + gross sell proceeds - sell commissions
buy budget = cash after sells - protected cash
```

With sell funding disabled:

```text
buy budget = current cash - sell commissions - protected cash
```

Sell proceeds still appear in ending cash but do not fund buys. Each buy uses
gross cost plus one commission. Buys process requested quantity, rounded
desired quantity, affordable quantity, their minimum, zero rejection, minimum
quantity, minimum notional, then reserve cash and recheck the budget. A minimum
threshold never increases a trade.

Canonical sequential funding gives earlier configured symbols priority. When
this reduces or skips a later buy, the plan adds
`CANONICAL_FUNDING_PRIORITY_APPLIED`. This is transparent ordering, not an
optimization algorithm.

## Reconstruction, deviations, and status

The planner builds the complete trade tuple before reconstructing all achieved
quantities. Achieved market values use unchanged prices. Ending cash is:

```text
starting cash + gross sell proceeds - gross buy cost - all commissions
```

Ending equity is ending cash plus achieved market values. Achieved weights and
one ordered deviation per symbol are calculated only after full reconstruction.
`PlannedTrade` therefore does not duplicate pre-trade or post-plan weights.

Cash reporting distinguishes:

```text
target cash at ending equity = target cash weight * ending equity
cash value deviation = ending cash - target cash at ending equity
cash weight deviation = achieved cash weight - target cash weight
```

`NO_ACTION` has no trades and all symbol and cash deviations within tolerance.
`COMPLETE` has trades, positive ending equity, nonnegative cash, all deviations
within tolerance, and satisfied achieved allocation constraints. `PARTIAL` is
cash-safe but retains a deviation or achieved constraint failure. `INFEASIBLE`
means no cash-safe plan can be returned; it contains no trades, unchanged-state
deviations and ending estimates, and a hard-failure diagnostic.

Limiting-reason precedence is: within tolerance; commission not covered by
sell proceeds; rounded to zero; below minimum quantity; below minimum notional;
insufficient buy cash; quantity rounding. A reason may describe a skipped trade
or a partially achieved allocation.

Supplied constraints validate the requested target during request construction.
The planner audits achieved cash, position weights, minimum positive weights,
and one-way turnover directly using the same formulas. It does not fabricate a
`TargetPortfolio` for achieved values. Failure normally produces `PARTIAL`.

## IDs and safety boundaries

Request IDs are caller supplied. Plan and trade IDs use UUID5 with a fixed
planner namespace and canonical request, side, symbol, and ordinal inputs. No
random UUID, wall clock, object identity, or mapping order affects results.

`PlannedTrade` is neither an order, risk decision, nor `TradeProposal`.
Conversion remains deferred to a future `RebalanceProposalFactory`, which must
supply workflow timestamps, proposal IDs, reasons, and eligibility policy.
Every resulting proposal must still pass `RiskManager`; planning commission,
cash, and position estimates provide no execution authorization.

Optimization, scenario generation, tax lots, liquidity and slippage models,
partial fills, limit orders, execution-aware replanning, numerical/GPU tools,
AI, backtest and CLI integration, networking, and brokerage functionality
remain deferred.
