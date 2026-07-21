# Paper order submission

The paper submission layer moves locally created portfolio orders from
`PENDING` to `SUBMITTED` inside an authoritative `OrderEngine`. It records the
existing engine's immutable replacement orders and append-only `SUBMITTED`
events. It does not contact a broker, acknowledge an exchange order, create a
fill, or mutate accounting state.

## Request, source eligibility, and time

`PaperSubmissionBatchRequest` contains a caller UUID, the complete
`PortfolioOrderBatchResult`, one explicit submission timestamp, and ordered
metadata. The timestamp must be aware, is normalized to UTC, and may equal or
follow request creation, the source CREATED event, and the latest active event.
Every order in a batch shares that timestamp. No clock or generated request ID
is used.

A CREATED source must contain aligned, unique pending orders and CREATED
events. Each order and exact event must be present in the active engine, the
active order must equal its source snapshot, and its fill history must be
empty. Any missing, changed, already submitted, canceled, rejected, or filled
order fails the whole request. A NO_ACTION source produces an immutable empty
result and one stable diagnostic without copying or replacing the engine.

## Ownership, ordering, and identity

`PaperOrderSubmitter` owns its authoritative engine and exposes a read-only
property. On success it replaces that reference with a validated shadow copy;
callers must then use `submitter.engine`. External aliases, including a prior
portfolio-order orchestrator, remain at their earlier state. The submitter is
not thread-safe and callers must serialize access.

Source order is preserved without sorting. Each updated order and appended
event at an output index corresponds to the source order at that index.
Submitted-event UUID5 identity uses `paper-submission-v1`, the submission and
source-result IDs, source ordinal, order and source-event IDs, timestamp, and
event type. Result UUID5 identity additionally includes metadata, stable
pre-engine order statuses, ordered event IDs, fill IDs, output IDs, status, and
diagnostic codes. Messages, clocks, hashes, and object identity are excluded.

## Shadow-engine atomicity

The submitter validates the complete source, snapshots public orders, events,
and fills, precomputes collision-free event IDs, and deep-copies the engine. It
calls `shadow.submit_order` in source order. Reconciliation requires unchanged
order keys, unchanged unrelated orders, source orders changed only to valid
SUBMITTED snapshots, old events as an exact prefix, one new ordered event per
source order, and identical fill histories. The immutable result is built
before the authoritative reference is replaced. Copy, engine, or reconciliation
failure discards the shadow and returns no partial result.

## Lifecycle and deferred work

PENDING means the local order was created. SUBMITTED means it entered the local
paper-execution lifecycle. It does not mean broker acknowledgement, exchange
acceptance, cash expenditure, fill creation, ledger entry, or position change.
A later paper-execution component may create deterministic fills and coordinate
the order engine with `PaperLedger`. Broker submission, networking,
persistence, risk reevaluation, and persistent transactions remain separate
and deferred.
