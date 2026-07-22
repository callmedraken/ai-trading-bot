# Optimized paper portfolio simulation

## Purpose and boundary

`OptimizedPaperPortfolioSimulator` coordinates explicit optimization frames
through ledger-derived state, the existing CPU Mean-CVaR optimizer, optimizer
target certification, and the existing paper runtime. It is separate from the
manual-target `PaperPortfolioSimulator`; both share only a private pure state
derivation helper and authoritative runtime ownership principles.

Frames contain explicit prices, expected returns, scenarios, Mean-CVaR
parameters, constraints, and execution policies. They contain neither
`PortfolioState` nor `TargetPortfolio`. The simulator generates no forecasts or
scenarios and fetches no market data.

## State, universe, and request construction

Immediately before each frame, public ledger cash, quantities, and average costs
are combined with ordered risk prices. Unowned frame symbols become flat state
entries. Exposure uses risk prices only. Every holding must remain in the frame
universe. Price, expected-return, scenario, optimization-state, optimizer-target,
certified-target, and runtime universes must match in exact order.

The derived state is placed into `PortfolioOptimizationRequest` with the frame's
constraints, expected returns, scenario horizon, risk aversion, and deterministic
metadata. `MeanCvarOptimizationRequest` then combines that exact base request,
scenario set, and numerical parameters. Only `OPTIMAL` output continues.

## Certification and runtime handoff

The complete Mean-CVaR result and exact derived state are passed to
`OptimizedTargetPortfolioFactory`. The factory's exact optimizer target object is
then passed to `PaperPortfolioRuntime`; allocations, cash, timestamp, source,
and target UUID are never reconstructed or modified.

Optimization and certification must leave runtime fingerprints unchanged. A
runtime cycle's pre/post IDs must equal captured live state. Evaluation records
retain each complete stage result and identifiers without duplicating target
weights.

## Identity, atomicity, and status

UUID5 identities use `optimized-paper-simulation-v1`. Frame identity includes
complete ordered prices, forecasts, scenario contents, parameters, constraints,
policies, timestamps, and metadata. Optimization IDs include current derived
state and either initial component IDs or the prior cycle result. Certification
and cycle IDs include their immediate upstream result IDs. Aggregate identity
includes all stage results, state IDs, counts, status, and diagnostic codes.

Atomicity is per frame. Optimization and certification failures change no
runtime state; runtime failures rely on cycle atomicity. Earlier frames remain
committed, later frames are not attempted, and no complete result is returned.
Post-runtime reconciliation errors may occur after that cycle committed and do
not claim rollback.

`COMPLETED` requires at least one applied cycle. An all-no-action simulation uses
the shared `NO_ACTION` status and one stable diagnostic.

## Relationship boundaries and deferred work

This orchestrator duplicates no scenario validation, optimizer mathematics,
target cleanup, certification, rebalance, risk, execution, fill, or ledger
formula. It does not use market-data providers, brokers, networking, scheduling,
persistence, backtest engines, strategies, GPU, or AI.

SciPy/HiGHS remains optional; unavailable optimization fails the affected frame.
Cleaned domain output is deterministic for equal solver output, but cross-version
floating solver equivalence is not promised. Forecast/scenario generation,
historical adapters, analytics, persistence, scheduled trading, live brokers,
and richer fill models remain deferred.
