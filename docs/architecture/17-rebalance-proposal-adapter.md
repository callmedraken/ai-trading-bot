# Rebalance proposal adapter

The rebalance proposal adapter converts one immutable `RebalancePlan` into an
ordered immutable tuple of high-level `TradeProposal` values. It is an adapter
only: it does not evaluate risk, reserve buying power, create orders, mutate a
ledger, submit or fill trades, retrieve market data, or connect to a broker.

## Request, policy, and timestamp

`RebalanceProposalRequest` contains a caller-supplied UUID, a plan, an explicit
proposal timestamp, immutable policy, optional Decimal confidence, and ordered
metadata. It never reads the clock or generates request identity. Tuple-like
metadata is defensively copied and requires unique keys.

The timestamp must be aware, is normalized to UTC, and must equal
`plan.request.as_of` exactly. The plan is based on prices at that instant, and
no stale-price or maximum-age model exists. A future explicit age policy may
relax equality; elapsed time is never inferred from the current clock.

Confidence is either `None` or a finite Decimal from zero through one. One
request confidence is copied unchanged to every proposal. It is not derived
from optimization metrics, plan status, allocation size, or deviations.

`RebalanceProposalPolicy.allow_partial_plans` defaults to false. This makes
partial-plan acceptance an explicit workflow choice rather than hidden adapter
behavior.

## Eligibility and status

A `COMPLETE` plan must contain trades and is converted in full. A `PARTIAL`
plan is rejected by default; when explicitly allowed, every existing trade is
converted unchanged and the result contains exactly one
`PARTIAL_PLAN_ACCEPTED` diagnostic. The diagnostic records whether the
planner's estimated constraints were satisfied. The adapter does not repair a
constraint-violating partial plan.

A `NO_ACTION` plan must contain no trades and returns `NO_ACTION`, an empty
proposal tuple, and exactly one `NO_ACTION` diagnostic. An `INFEASIBLE` plan
must contain no trades and is always rejected. Trades on either status are an
inconsistent input rather than a normal eligibility failure.

`CREATED` means conversion completed for a complete or explicitly allowed
partial plan. A partial plan may legitimately produce an empty `CREATED`
result. Ineligible plans raise `RebalancePlanNotEligibleError`; there is no
rejected result status.

## Planned-trade mapping and order

Each plan trade maps index-for-index:

```text
PlannedTrade.symbol             -> TradeProposal.symbol
PlannedTradeSide.BUY            -> OrderSide.BUY
PlannedTradeSide.SELL           -> OrderSide.SELL
PlannedTrade.planned_quantity   -> desired_quantity
request.proposal_created_at     -> created_at
request.confidence              -> confidence
```

Side conversion uses an explicit fixed mapping between the distinct enums.
The planned quantity is copied exactly. The adapter does not round, resize,
merge, split, recalculate affordability, apply risk limits, or use commission
estimates.

Plan order is preserved without sorting: sells precede buys and symbol
ordinals increase within each side. The adapter defensively validates unique
trade IDs and symbols, canonical side order, ordinal order, symbol-to-position
matching, supported sides, and positive finite Decimal quantities before
constructing any proposal.

## Reasons and deterministic identity

Reasons use the fixed `rebalance-proposal-v1` format:

```text
Rebalance plan <plan_id>: <side> <symbol> toward target weight <weight>
Rebalance plan <plan_id> (PARTIAL): <side> <symbol> toward target weight <weight>
```

Decimal text normalizes negative zero, avoids exponent and locale formatting,
and strips insignificant trailing zeros. Reasons never include metadata,
prices, commissions, diagnostics, object representations, or serialized plan
state.

Proposal IDs use UUID5 under an adapter-specific namespace. Their fingerprint
contains the reason version, proposal-request and plan/trade IDs, proposal and
symbol ordinals, symbol, mapped side, exact canonical quantity, UTC timestamp,
confidence, plan status, and target weight. Reason text, current price,
commission, notional, clock values, Python hashes, mapping order, and object
identity are excluded.

Result identity contains the canonical request fingerprint, result status,
ordered proposal IDs, and ordered diagnostic codes. Request metadata affects
result identity but not individual proposal identity. Diagnostic message text
does not affect identity.

## Result invariants and failure atomicity

The immutable result checks its local status shape, proposal count, index-wise
trade mapping, diagnostic-code shape, proposal identities, and result identity.
It does not rerun planner calculations or the complete factory algorithm.

The factory validates the request, eligibility, and every trade before deriving
all candidates locally. Every `TradeProposal` is then constructed locally and
the complete tuple is validated before the result is created. An expected
proposal-domain `TypeError` or `ValueError` is wrapped as
`RebalanceProposalCreationError` with its original cause. No partial result is
returned and neither request nor plan is mutated. Unexpected exceptions are
not broadly caught.

## Downstream risk and deferred orchestration

A generated proposal is a request for risk evaluation, not approval.
`RiskManager` may reject or resize every proposal. Planner cash and commission
estimates neither reserve buying power nor replace `RiskLimits`, and multiple
buys still require collective downstream cash reservation. Even a complete
plan may therefore lead to resized or rejected decisions.

No `Order`, `OrderRequest`, execution instruction, ledger entry, or broker
state is created here. Collective risk orchestration, buying-power reservation,
orders, execution, fills, backtest integration, persistence, networking, and
broker integration remain deferred.
