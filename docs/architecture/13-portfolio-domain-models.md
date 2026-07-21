# Portfolio domain models

The additive `portfolio` package defines immutable portfolio state, target,
constraint, and solver-boundary contracts. It contains no optimization,
rebalancing, proposal generation, risk decision, execution, backtest, CLI,
network, AI, or broker behavior.

## Current state and ordering

`PortfolioState` stores one ordered `PortfolioPositionState` for every symbol,
including flat symbols. Open entries have positive quantity and average cost;
flat entries have exactly zero quantity and average cost. Every entry has a
positive current price. Fractional quantities are allowed because quantity
precision remains a later planner and risk concern.

Market value is derived as quantity times current price. State equity must be
positive and exactly equal nonnegative cash plus all derived market values.
Position weights and cash weight are derived by dividing these values by
equity. No market values or weights are stored redundantly. A zero-equity state
is rejected because its weights are undefined.

All timestamps must be aware and are normalized to UTC. Decimal negative zero
is normalized to zero. Configured symbol order establishes all later vector
ordering, and normalized duplicate symbols are rejected.

## Targets and exact weights

`TargetPortfolio` contains one explicit `TargetAllocation` per ordered symbol,
including zero-weight entries, plus an explicit cash weight. It enforces only
structural invariants: unique ordered symbols, weights within zero and one, and
an exact combined `Decimal("1")` total. It never applies request-specific cash,
position, minimum-weight, or turnover limits and never normalizes a near-one
target.

Targets record caller-supplied UUID identity, source, optional typed string
metadata, and a UTC `as_of`. Optimizer targets require a nonblank source name.
All IDs are caller supplied; models generate neither random nor clock-derived
identity.

## Constraints and turnover

`PortfolioConstraints` describes minimum and maximum cash weight, maximum
position weight, optional minimum positive position weight, and optional
maximum one-way rebalance turnover. Long-only must remain true and leverage
must remain disabled. Valid limits are not claimed to make an optimization
problem feasible.

`validate_target(state, target)` first requires identical ordered universes,
then checks cash bounds, each position weight, and turnover. The optional
minimum position weight applies only to positive symbol weights, never cash or
zero allocations.

Total weight change includes symbols and cash:

```text
sum(abs(target symbol weight - current symbol weight))
+ abs(target cash weight - current cash weight)
```

One-way rebalance turnover is total weight change divided by two. Generic
turnover comparison does not require equal state and target timestamps; stale
target policy belongs to a future rebalance planner. This allocation metric is
distinct from analytics' actual two-way executed-notional turnover.

## Optimization boundary and forecast horizon

`PortfolioOptimizationRequest` contains the current state, constraints, one
expected return per symbol in exact universe order, a forecast horizon,
nonnegative risk aversion, caller-supplied UUID, and ordered metadata. An
expected-return value is total arithmetic return over exactly the requested
number of `Timeframe.DAY_1` periods; it is not annualized. Scenarios and
confidence levels remain deferred.

`PortfolioOptimizationResult` retains the full immutable request, solver name,
status, optional objective value, optional target, and ordered diagnostics.
Optimal and feasible results require an optimizer target with matching request
timestamp and a source name equal to the solver name. They validate the target
against request constraints but do not claim to re-prove mathematical
optimality. Their objective is optional and finite when supplied. Unsuccessful
statuses prohibit target and objective values and require a diagnostic. No
wall-clock completion timestamp is stored.

`PortfolioOptimizer` is a plain structural protocol. A deterministic CPU
implementation, optional accelerator adapter, and test fake can implement it
without exposing ledger, risk, order, backtest, broker, or mutable application
state.

## Numerical adapter boundary

The domain uses finite `Decimal` values exclusively. A future numerical adapter
must validate domain input, convert values with documented precision and
rounding, run its solver, reject NaN and infinity, and convert output through a
deterministic textual representation rather than directly from binary float.
It must normalize negative zero and validate symbol weights without clipping.

After conversion, the adapter computes:

```text
cash residual = Decimal("1") - sum(symbol weights)
```

A negative residual is rejected. Otherwise the adapter constructs a
`TargetPortfolio`, which again requires the exact total of one. There is no
silent clipping, tolerance, or normalization in the domain.

## Stage boundaries and deferred scope

Portfolio constraints guide allocation construction. They do not authorize a
trade and do not replace `RiskManager`, which remains the final deterministic
per-trade safety authority. A future rebalance planner will combine state,
target, commission assumptions, and quantity precision to produce auditable
sell and buy proposals, residual cash, and target deviations. It is also
responsible for target staleness policy.

Scenario matrices, annualization, sector/factor/tax/ESG/liquidity/cardinality
constraints, optimization algorithms, SciPy, CVXPY, NumPy, pandas, GPU tools,
AI, rebalancing, execution, backtest integration, serialization, networking,
and brokerage functionality remain deferred.
