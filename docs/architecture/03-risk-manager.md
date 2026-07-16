# Risk manager

The deterministic risk manager is the boundary between high-level trading
intent and future execution. Strategies and AI analysis may create immutable
domain `TradeProposal` objects, but they do not create executable orders. A
`RiskManager` evaluates each proposal against immutable `RiskContext` account
and market data plus immutable `RiskLimits`.

Percentage limits use `Decimal` fractions: `Decimal("0.15")` means 15%.
Buy sizing calculates an independent maximum quantity for cash, minimum cash
reserve, position concentration, total exposure, and any configured order
notional or new-position limit. Estimated commission is subtracted from cash
and reserve capacity. The smallest maximum is rounded downward to the allowed
quantity increment. Limits set to `None` are skipped.

Sells are not subject to buy-oriented cash or exposure limits because they
reduce long-only exposure. They require an existing position and are capped at
the owned quantity. Exact liquidation of a fractional position remains allowed
when fractional trading is disabled, preventing an unsellable residual.

Decisions are approved, resized, or rejected and contain stable reason codes
with human-readable details only for rejection, resizing, or meaningful
binding constraints. Evaluation time comes from the UTC-normalized context, so
identical inputs produce identical results.

The risk manager does not mutate inputs, reserve cash, apply fills, submit
orders, retrieve prices, generate signals, call AI, or connect to a broker.
Future execution must revalidate price, cash, positions, commission, and limits
because these assumptions may change after a decision is produced.

Daily loss, drawdown, open-order exposure, stale-price detection, and
broker-specific precision remain deferred until the required account and
execution models exist.
