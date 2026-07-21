# Paper fill application

The paper-fill applier atomically applies generated fill candidates to an
authoritative `OrderEngine` and `PaperLedger`. It owns live-state validation,
deterministic fill-event identity, lifecycle transition, accounting
application, cross-component reconciliation, and immutable audit output. It
does not generate or alter fill price, quantity, commission, timestamp, or fill
identity.

## Source and dual ownership

`PaperFillApplicationBatchRequest` contains a caller UUID, the complete
`PaperFillBatchResult`, and ordered metadata. A GENERATED source must contain
one unique full candidate per submitted source order in exact ordinal order. A
NO_ACTION source returns one diagnostic without copying or replacing either
component.

`PaperFillApplier` requires and owns an engine and ledger, exposed through
read-only properties. Successful application replaces both references with
validated shadows. Callers must use the applier-owned components afterward;
earlier submitter, orchestrator, and external aliases remain unchanged.

## Live validation and ordered application

Immediately before copying, the applier verifies each active order still
equals its submitted source, is SUBMITTED and unfilled, retains the exact
SUBMITTED event as its latest event, has the candidate remaining quantity, and
does not contain the candidate fill ID. Ledger cash, realized profit and loss,
positions, and existing fill identity are structurally validated. Detailed
cash, commission, position, cost-basis, and realized-P&L rules remain owned by
sequential `PaperLedger.apply_fill` calls.

Source order is preserved. For each candidate, the shadow engine applies the
fill first using a deterministic event ID, then the shadow ledger applies the
same immutable fill. Engine-first ordering ensures accounting never receives a
lifecycle-invalid candidate. A ledger rejection after engine acceptance still
changes only discarded shadow state.

## Identity, audit, and reconciliation

Fill-event UUID5 identity uses `paper-fill-application-v1`, application and
source-result IDs, source ordinal, existing fill and order IDs, source
SUBMITTED-event ID, fill timestamp, FILLED event type, and FILLED resulting
status. IDs are precomputed and collision-checked before copying.

Engine state UUID5 fingerprints include ordered material orders, events, and
per-order fill histories. Ledger fingerprints include canonical cash, realized
P&L, symbol-sorted material positions, and ordered fill history. The immutable
result retains pre- and post-state IDs. Each evaluation records the source
ordinal and fill, updated order, fill event, and cumulative post-fill ledger
cash, matching position, and realized P&L.

Per-fill reconciliation requires the engine and ledger each to contain the
exact fill once, a full FILLED order, and the exact FILLED event. Batch
reconciliation preserves order keys, unrelated orders, old event and fill
prefixes, prior ledger fill history, untouched positions, source ordering, and
final touched positions.

## Atomicity and boundaries

Both components are deep-copied after complete preflight validation. Every
application, reconciliation, state fingerprint, and immutable result is
completed before the two authoritative references are assigned consecutively
with no intervening work. Any collision, copy, engine, ledger, or
reconciliation failure discards both shadows and returns no partial result.

The applier does not calculate prices or slippage, rerun risk, create or submit
orders, access market data, contact brokers, perform backtesting or
optimization, or use networking, GPU, or AI behavior. It is not thread-safe;
callers must serialize access. Database transactions, crash recovery,
multi-process coordination, persistent runtime orchestration, and brokerage
remain deferred.
