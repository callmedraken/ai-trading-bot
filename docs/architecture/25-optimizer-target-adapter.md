# Optimizer target adapter

## Responsibility and contracts

The portfolio optimizer-target adapter is a pure certification and
reconciliation gateway. A successful CPU Mean-CVaR result already contains a
complete immutable `TargetPortfolio`; the adapter does not repeat solver
cleanup, weight conversion, feasibility, objective, expected-return, CVaR,
turnover, or constraint calculations.

`OptimizedTargetRequest` combines a caller UUID, complete specialized result,
the exact intended `PortfolioState`, and immutable metadata.
`OptimizedTargetPortfolioFactory` accepts only an `OPTIMAL` nested portfolio
result with a target. It returns `OptimizedTargetResult`, retaining the request
and the exact optimizer target object. All other statuses raise.

## State, universe, and timestamps

The intended state must equal the optimizer base state exactly, including UTC
timestamp, cash, equity, ordered positions, quantities, average costs, and
current prices. Its ordered symbols must also equal expected-return symbols,
scenario symbols, and target allocation symbols. No sorting or universe repair
occurs.

Held symbols remain as target entries even at zero weight for liquidation. A
new-entry symbol must already be a valid flat entry in the optimization state.
The adapter neither adds nor drops symbols. State, optimizer inputs, scenarios,
and target must share the same normalized instant; targets are never retimed.

## Exact target preservation and provenance

Asset weights, zero weights, cash weight, source, solver source name, metadata,
timestamp, and optimizer-generated target UUID are preserved exactly. The
target requires finite `Decimal` weights in `[0, 1]` and an exact asset-plus-cash
total of one. The adapter performs no tolerance, normalization, rounding,
quantization, clamping, residual distribution, or cash inference.

CPU targets use `AllocationSource.OPTIMIZER` and a source name equal to the
nested portfolio result's solver name. The gateway validates that established
relationship.

## Identity, atomicity, and boundaries

The adapter result UUID5 uses `optimizer-target-adapter-v1` and includes the
adapter request UUID, nested optimizer result and target IDs, canonical exact
state, ordered target weights, cash, timestamp, and request metadata. Decimal
identity text is finite, exponent-free, locale-independent, and normalizes
negative zero. Messages, object identity, hashes, clocks, and incidental mapping
order are excluded.

Certification validates every input before constructing the aggregate result.
It mutates nothing and cannot return a partial result. It does not execute an
optimizer, generate scenarios, plan trades, evaluate risk, execute orders,
access ledger/runtime/simulation state, fetch market data, contact brokers, or
use networking, GPU, or AI functionality.

The planner remains responsible for detecting no-action targets and producing
trades. Runtime and simulation integration, including automatic per-frame
target generation, remains deferred.
