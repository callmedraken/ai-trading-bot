# Backtest engine

The first `BacktestEngine` deterministically coordinates one symbol of daily
historical data through the NYSE calendar, a point-in-time strategy callback,
the risk manager, order engine, simulated next-open fills, and paper ledger. It
creates fresh run-local components and returns an immutable audit result.

For each bar, actions occur in this order: apply the prior submitted order as a
full fill at the current open; update the ledger atomically with the order;
create exactly one account snapshot valued at the current close; expose bars
only through the current bar to the strategy; evaluate any proposal with risk;
and create and submit a market order for the next available bar. A final-bar
proposal is still risk-evaluated and recorded as `END_OF_DATA`, but no order is
created. At most one pending, submitted, or partially filled order is allowed.

Strategy proposals must match the configured symbol, use the current bar
timestamp exactly, and have a run-unique proposal ID. `BacktestContext.history`
is an immutable prefix ending at the current bar. Strategies never receive the
provider, future bars, ledger, risk manager, order engine, or result.

With slippage `s = basis_points / 10000`, buy fills use
`next_open * (1 + s)` and sell fills use `next_open * (1 - s)`. A fixed
commission is recorded on each fill. Fills are full quantity only; no partial,
limit, volume-based, or same-bar fills exist.

Bars must map one-to-one to derived NYSE session dates. Missing sessions fail
unless explicitly allowed, and no bars or snapshots are synthesized. Bar
timestamps remain source identities and are never reinterpreted as market-open
times.

Cross-component fill atomicity uses a private `copy.deepcopy` helper. The fill
is applied to shadow `OrderEngine` and `PaperLedger` instances, and both active
references are replaced only after both succeed. Any price-gap, slippage,
commission, cash, position, or lifecycle failure raises `BacktestExecutionError`
and ends the run with the original components unchanged.

Each `BacktestStep.submitted_order` preserves the order snapshot as it appeared
after submission. `BacktestResult.orders` instead contains final immutable
snapshots in creation order, after any later fills. Deterministic UUID5 values
are derived from the configured run ID and step indexes for engine-generated
orders, events, and fills.

This engine does not support multiple symbols, concurrent orders, brokers,
Robinhood, AI, optimization, persistence, performance analytics, partial
fills, limit orders, market hours, or synthetic missing data.
