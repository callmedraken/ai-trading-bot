# Portfolio risk orchestration

The portfolio risk orchestrator evaluates an immutable ordered proposal batch
against the existing single-proposal `RiskManager` while maintaining temporary
collective reservations. It creates no orders or fills, mutates no ledger, and
has no broker, network, optimization, backtest, GPU, or AI behavior.

## Generic request and fixed prices

`PortfolioRiskBatchRequest` contains a caller UUID, ordered proposals, a base
`RiskContext`, an exact ordered `PortfolioRiskPrice` tuple, `RiskLimits`, a
sell-proceeds policy, and ordered metadata. It is independent of rebalancing;
rebalance callers pass the proposal result's tuple directly.

For a nonempty batch, price symbols equal exactly the union of starting-position
and proposal symbols. Prices are unique, positive finite Decimals and remain
fixed throughout evaluation. The price tuple, never mapping iteration, defines
deterministic universe and final-position order. The base context's scalar
`current_price` is ignored. Proposal timestamps equal the base timestamp.

Starting exposure must equal quantities times fixed prices, and base equity
must equal cash plus exposure. An empty proposal and price tuple produces an
explicit `NO_ACTION` audit result.

## Order and provisional contexts

Caller order is preserved without sorting and duplicate proposal symbols are
rejected. Ordering establishes priority: earlier accepted decisions alter cash,
positions, and exposure before later proposals. Generic requests need not put
sells before buys; the rebalance adapter already does so.

Before each proposal, the orchestrator creates a fresh `RiskContext` with
current risk-available cash, provisional positive positions, that proposal's
fixed price, provisional exposure, the original trading flag and timestamp,
and original base equity. Fixed base equity is the percentage-risk denominator
for the complete batch and matches existing multi-symbol backtest semantics.

Starting positions retain actual average cost. A newly provisional position
uses its fixed price as temporary average cost solely because `RiskContext`
requires a `Position`; this is risk scaffolding, not ledger cost basis.

## Economic cash and risk-available cash

Two cash states are tracked:

```text
economic cash = starting cash + accepted gross sells
                - accepted buys - accepted commissions

risk-available cash = starting cash + policy-eligible accepted gross sells
                      - accepted buys - accepted commissions
```

The conservative policy default withholds sell proceeds from later buying
power, matching multi-symbol backtesting. When enabled, net sell proceeds fund
later buys. Commissions are reserved exactly once for approved or resized
decisions; rejections change no reservation. Withheld gross proceeds are
reported separately and are not treated as an economic loss.

Accepted sells cannot exceed provisional ownership and their notional must
cover commission. They reduce quantity and exposure and increase economic cash
net of commission. Exact liquidation removes the position. Accepted buys
reduce both cash states by notional plus commission and increase quantity and
exposure. Resized decisions reserve only approved quantity.

After every accepted decision, exposure is reconstructed from provisional
quantities and prices, and both cash states are reconstructed from aggregate
side notionals and commissions. Negative or nonfinite state and any mismatch
fail atomically.

## RiskManager ownership and audit

`RiskManager` remains the sole owner of risk rules, reason codes, and quantity
decisions. The orchestrator only supplies evolving contexts, validates returned
decision identity and outcome shape, applies collective side effects, and
records audit data. It does not duplicate risk formulas.

Each `PortfolioRiskEvaluation` retains ordinal, exact context and decision,
cash before and after, economic cash after, symbol quantity before and after,
reserved notional and commission, and resulting exposure. Rejected evaluations
have zero reservations and unchanged state.

The result contains ordered evaluations and final positive positions, both cash
states, exposure, economic equity, withheld proceeds, commissions, side
notionals, decision counts, status, and stable diagnostics. Economic equity
reconciles both as cash plus exposure and base equity less commissions.

Statuses are `NO_ACTION`, `ALL_APPROVED`, `ALL_REJECTED`, and
`PARTIALLY_APPROVED`; all-resized and every other nonuniform accepted batch are
partial. Structural failures raise rather than returning a failed status.
`SELL_PROCEEDS_WITHHELD` appears only when an accepted sell has positive
withheld proceeds. Risk reason codes remain nested in decisions.

## Atomicity, identity, and boundaries

The complete request is validated before a private working reservation is
created. Decisions are validated before application; evaluations are local;
final state is reconciled; and the immutable result is constructed last.
Ordinary risk rejection is a valid result. Structural, decision, or arithmetic
failure returns no partial result and mutates no input.

The UUID5 result fingerprint contains all material ordered request values,
limits, policy, metadata, decision outcomes and quantities, stable risk reason
codes, reservation effects, final totals and counts, and orchestration codes.
Messages, mapping order, clocks, hashes, and object identity are excluded.

This result is not an order or execution authorization. A later adapter may
construct orders only from approved or resized decisions in batch order.
Rejected proposals create no order. Buying power is not actually spent and
positions do not actually change until future accepted fills update accounting.
