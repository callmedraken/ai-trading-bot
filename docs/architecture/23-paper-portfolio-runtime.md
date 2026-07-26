# Deterministic paper portfolio runtime

## Responsibilities and boundary

`PaperPortfolioRuntime` orchestrates one in-memory paper cycle from an immutable
`PortfolioState` and `TargetPortfolio`: planning, proposal conversion, collective
risk, market/DAY order creation, paper submission, deterministic fill generation,
and atomic fill application. It does not optimize portfolios, fetch data, contact
brokers, backtest, persist state, schedule work, or use AI.

The runtime owns one `OrderEngine` and one `PaperLedger`. It is not thread-safe;
callers must serialize cycles. Crash recovery and multi-process coordination are
outside this version.

## Request and validation

`PaperPortfolioCycleInputs` supplies planning assumptions, optional constraints,
proposal and risk policies, risk limits, a trading-enabled flag, fill policy,
submission/fill timestamps, and one ordered price record per planner-universe
symbol. `risk_price` must match the portfolio state's current price;
`fill_reference_price` is independent. Prices are finite positive `Decimal`
values. Planner, risk, and fill commission assumptions must agree.

The state and target share an exact UTC timestamp and the ordered universe
required by the existing planner. State cash, holdings, quantities, average
costs, and risk-priced equity are reconciled against the authoritative ledger
before planning. Submission and fill timestamps are aware, normalized to UTC,
and satisfy `state <= submission <= fill`; equality is allowed.

Caller metadata is immutable and uniquely keyed. Keys beginning
`paper_portfolio_` are reserved. Each stage receives caller metadata plus a
runtime-owned cycle-ID entry.

## Deterministic stages and audit

Seven UUID5 stage request IDs use the dedicated namespace and version
`paper-portfolio-runtime-v1`. The planning ID includes a canonical complete
cycle-input fingerprint (including the target ID); every later ID includes the
immediate upstream result ID. No wall clock or random identity is used.

The result retains the request and every immutable stage result. Validation
reconciles object/value handoffs, request identities, metadata, timestamps,
source ordering, accepted/order/submission/fill/application counts, status, and
post-state fingerprints. Its UUID5 identity includes the canonical request,
all stage result IDs, pre/post component state IDs, status, and diagnostic codes.

## Atomicity and ownership

Validation, planning, proposal conversion, and risk evaluation run before any
outer copy. If risk accepts work, the runtime deep-copies both authoritative
components and all stateful stages operate only on cycle-local successors.
The complete chain and result are reconciled before two consecutive reference
assignments commit the final engine and ledger. No fallible work follows them.
Known component failures are wrapped in stage-specific runtime exceptions with
their original cause. Copy failures are reported separately.

When planning produces no proposals, or risk rejects every proposal, the full
downstream empty audit chain still runs. No outer copies occur, the exact runtime
objects remain installed, and pre/post state IDs are equal.

Deep copying at both the runtime and existing component boundaries is accepted
for the current in-memory scale. A future shared transaction abstraction may
reduce copy cost, but must preserve the same audit and atomicity guarantees.

Verified daily snapshot replay remains a separate market-data boundary. It does
not automatically construct cycle prices, targets, risk inputs, orders, or
fills, and the runtime continues to perform no market-data retrieval.
