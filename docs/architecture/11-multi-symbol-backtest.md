# Multi-symbol backtesting

The additive `multi_backtesting` package coordinates immutable complete
multi-symbol market frames through the existing `RiskManager`, `OrderEngine`,
and `PaperLedger`. It does not alter the single-symbol engine or analytics.

## Input and strategy boundary

The engine accepts a `MultiSymbolHistoricalDataResult` produced from either
union or intersection alignment, but every actual frame must contain every
requested symbol. Completeness is checked before ledger, strategy, risk,
execution, or audit state exists. No missing price is filled, skipped, carried
forward, or matched by date. Exact UTC frame chronology is retained; calendar
and timestamp-to-session normalization are deferred.

At each close, a strategy receives the ordered fixed universe, current frame
and timestamp, an immutable history prefix through that frame, the close-valued
`AccountSnapshot`, ordered positions, and active order snapshots. It receives
no provider, future frame, next open, ledger, order engine, risk manager, or
mutable state. It returns a tuple of `TradeProposal` values. Proposals must use
the current timestamp, belong to the universe, have globally unique IDs, and
contain at most one proposal per symbol per evaluation.

## Frame loop and deterministic ordering

Each frame performs: select prior submitted orders; construct and preflight a
canonical opening fill batch; atomically apply it; value all positions at
current closes; create exactly one snapshot; evaluate strategy; validate and
order proposals; evaluate risk with projected reservations; submit approved
orders atomically, or record final-frame approved decisions as end-of-data;
then append one immutable audit step.

Proposals and fills are ordered by sells first, requested-symbol ordinal, then
UUID. Strategy-return order and dictionary iteration do not establish
priority. UUID5 values derive solely from run ID, operation, step, symbol, and
canonical ordinal.

## Risk reservation and execution

The existing `RiskManager` remains the only decision logic. Each canonical
proposal receives a projected `RiskContext`. Approved and resized buys remove
current-close notional plus estimated commission from projected cash and add
notional to exposure. Sells reduce projected position quantity and exposure;
future proceeds are never credited to projected cash. Rejections reserve
nothing. This prevents collectively unaffordable approvals without introducing
an optimizer.

Approved orders fill fully at the immediately following complete frame's open,
with existing fixed commission and side-specific slippage formulas. Actual
sells execute before buys, so actual proceeds affect next-open accounting.
Price gaps cause the entire opening batch to fail; there is no resizing,
partial fill, cancellation, or partial result.

## Atomicity and valuation

`OrderEngine` and `PaperLedger` are plain value-backed objects proven safe to
`deepcopy` by focused tests. Opening batches first validate active orders,
identity, timestamp, universe, positive values, unique fill IDs, projected
sell quantities, and canonical projected cash. The whole batch then applies to
shadow components, which replace active references only after success. Order
creation and submission similarly use one shadow order engine per batch.

`PaperLedger.create_account_snapshot` already values every open position from
a complete close-price mapping, so the existing `AccountSnapshot` is reused.
Final cash and realized profit or loss are derived from the final snapshot.

## Result and deferred scope

`MultiSymbolBacktestResult` preserves frames, chronological steps, proposals,
risk decisions, submission-time order snapshots, final order snapshots,
global lifecycle events, fills, snapshots, ordered final positions, final
equity, and `UnexecutedProposal` records. Approved or resized final-frame
proposals create an `END_OF_DATA` record but no order or event. Rejected risk
decisions are not terminal-unexecuted records.

Portfolio analytics, CLI integration, calendars, incomplete-frame policies,
same-symbol batch reversals, target weights, optimization, scenario generation,
GPU tooling, AI, partial fills, limit orders, intraday data, networking, and
brokers remain deferred.
