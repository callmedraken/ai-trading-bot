# Portfolio order orchestration

The portfolio order orchestrator converts accepted collective-risk evaluations
into managed pending orders by calling the existing `OrderEngine.create_order`
API. It does not submit orders, create fills, mutate a ledger, update cash or
positions, contact a broker, rerun risk, or perform backtesting or optimization.

## Why there is no standalone OrderRequest adapter

`OrderEngine.create_order` accepts a `RiskDecision` and
`ExecutionInstruction`, then constructs the `OrderRequest`, pending `Order`, and
initial `CREATED` event itself. A separate request factory would create an
object the engine cannot consume and would duplicate identity and validation
ownership. The orchestrator therefore passes the original accepted decision
directly to the engine with deterministic order and event IDs.

## Request, eligibility, and instruction

`PortfolioOrderBatchRequest` retains a complete `PortfolioRiskBatchResult`, one
uniform execution instruction, caller UUID, and ordered metadata. The first
version requires explicit `MARKET`, `DAY`, no limit price, and an instruction
timestamp exactly equal to the risk base timestamp, every decision evaluation
timestamp, and every proposal timestamp. Limit and GTC behavior require
per-order pricing and reservation-lifetime policies and remain deferred.

Only approved and resized decisions are eligible. Rejections are skipped
without changing the relative order of accepted evaluations. All-approved and
partially-approved sources create orders; all-rejected and no-action sources
return successful empty results without copying or replacing the engine. A
mixed result records `REJECTED_EVALUATIONS_SKIPPED`; a resized-only batch does
not. A no-action source records `NO_ACTION`.

The engine constructs request quantity from the exact approved quantity. The
orchestrator never rounds, resizes, merges, splits, recalculates buying power,
or reruns risk. Result source ordinals map each order and created event back to
the corresponding risk evaluation.

## Identity and engine pre-state

Order and created-event UUID5 fingerprints contain the adapter version,
adapter request and source result IDs, source ordinal, proposal ID, risk
outcome, approved quantity, symbol, side, instruction values, timestamp, and
limit-price marker. Distinct prefixes separate order and event identity.
Metadata affects only the aggregate result ID.

The orchestrator fingerprints public pre-batch snapshots using ordered existing
order IDs and global event IDs. Result identity contains this state ID, the
canonical request, status, source ordinals, new order and event IDs, and stable
diagnostic codes. Messages, clocks, object identity, hashes, and mapping order
are excluded. Equal requests and equal engine states produce equal results;
repeating a batch against its already advanced engine collides deliberately.

## Ownership and shadow-engine atomicity

`PortfolioOrderOrchestrator` owns the authoritative engine reference and
exposes it through a read-only property. For a nonempty accepted batch it fully
validates the source, snapshots public orders and events, precomputes and checks
all identities, then deep-copies the active engine. It calls `create_order` on
the shadow in source order.

Existing orders and events must remain exact prefixes of shadow public
snapshots. The newly appended order and event suffixes must match accepted
source order and deterministic identities. Every new order is pending and its
request fields match the decision and instruction; every new event is CREATED
and references the corresponding order.

The immutable result is constructed before the authoritative reference is
replaced. Any copy, engine, or reconciliation failure discards the shadow and
leaves the active engine object and state unchanged. Empty results neither copy
nor replace it. No private engine fields are accessed.

After success, callers must use `orchestrator.engine`; an external alias to an
initially supplied engine remains at its earlier state. The orchestrator is not
thread-safe, concurrent calls are unsupported, and callers must serialize
access. Persistent transactions remain deferred.

## Result and later execution

The result stores its deterministic ID, complete request, CREATED or NO_ACTION
status, source ordinals, newly created immutable orders and CREATED events, and
diagnostics. The pre-batch engine fingerprint participates in result identity
but is not an additional public result field. `Order` already contains its
`OrderRequest`, so requests are not duplicated.

These pending local orders are not submitted and spend no buying power. A
later submission adapter must operate on the authoritative orchestrator engine,
preserve order, create SUBMITTED events, and continue through paper or broker
fills and ledger reconciliation. Submission, fills, cancellation, ledger
updates, persistence, networking, and brokerage remain outside this milestone.
