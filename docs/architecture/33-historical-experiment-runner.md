# Deterministic historical experiment runner

## Responsibility and boundary

`trading_bot.experiments` compares an explicit ordered collection of complete
rolling historical simulation variants. All variants share one exact immutable
aligned historical result, one explicit rebalance schedule, and one immutable
initial-state specification.

The package performs no provider or filesystem I/O, CLI parsing, scheduling,
persistence, checkpoint recovery, brokerage operation, networking, GPU work,
AI analysis, parameter search, or automatic tuning. It is not an optimizer and
does not select a winning configuration.

## Shared input and explicit variants

`HistoricalExperimentRequest` retains a caller UUID, exact
`MultiSymbolHistoricalDataResult`, UTC-normalized schedule, initial state,
ordered variants, and ordered caller metadata. Variants are nonempty and retain
caller order. IDs are unique, and stripped names are unique under `casefold`.

Each `HistoricalExperimentVariant` contains every rolling, scenario,
optimization, execution, rebalancing, risk, fill, and trading policy required
to construct one `RollingHistoricalSimulationRequest`. Scenario source name is
variant-specific because it participates in scenario identity. Planner, risk,
and fill commissions must agree.

Caller metadata reserves `historical_experiment_`. Arbitrary experiment and
variant metadata stays at the experiment boundary. Generated rolling metadata
contains only experiment ID, variant ID, ordinal, and stripped display name.

## Initial state and factory trust boundary

The immutable initial-state specification supports `CASH_ONLY` and
`BOOTSTRAP_FILLS`. It contains an aware UTC timestamp, nonnegative remaining
cash, ordered unique bootstrap positions, and a version-one commission fixed at
zero. Bootstrap quantities and unit costs are strictly positive finite
Decimals.

The runner accepts one callable `HistoricalExperimentSimulatorFactory`. It
passes the same initial-state specification plus experiment and variant
identity context and expects one already initialized exact
`OptimizedPaperPortfolioSimulator`. The experiment package does not import CLI
bootstrap models and does not construct engines, ledgers, runtimes, or
simulators.

The factory is a constructor, not an authority. Before execution, the runner
inspects public simulator/runtime/engine/ledger types and state. The engine must
be empty. Ledger cash, realized P&L, positions, ordered bootstrap fills, sides,
quantities, unit costs, commissions, timestamps, and ID uniqueness must match
the specification. This is structural reconciliation, not a duplicate
accounting calculation.

The canonical initial-state content fingerprint excludes incidental bootstrap
order and fill UUIDs. State IDs may therefore differ while equivalent initial
content remains required.

## Isolation and sequential execution

Each attempted variant invokes the factory exactly once. The runner keeps
strong live references to every pre-run and post-run simulator, runtime, engine,
and ledger. Post-run references are necessary because the runtime's atomic
shadow-state commit may replace its engine or ledger object.

Reuse of any component, including a final component hidden behind a fresh
wrapper, raises an isolation error. Object identity is used only for live
isolation and never enters a deterministic model or UUID.

Variants execute sequentially in caller order:

1. Validate the complete request before invoking the factory.
2. Construct and reconcile one fresh simulator.
3. Construct one rolling request from exact shared input and variant policies.
4. Construct one rolling runner and invoke it once.
5. Retain the exact rolling result.
6. Project existing performance fields into immutable metrics.
7. Construct the immutable run audit.

No variant is retried or rerun during comparison.

## Failure semantics

Version one is fail-fast. Factory, initialization, isolation, or rolling failure
stops the experiment immediately. Later variants are not attempted, and no
partial aggregate result is returned. Variant-scoped exceptions retain ordinal,
UUID, name, stage, and the known downstream cause.

Earlier private simulators may have completed, but their mutable services are
not returned or shared. The runner does not claim rollback of a failed private
simulator.

## Metrics and no ranking

`HistoricalExperimentMetrics` is a direct read-only projection of the retained
optimized-simulation performance result. It includes equity, simulation return
and P&L, drawdowns, simulation-relative realized P&L, costs, turnover,
allocation drift, order/fill/risk counts, rejected and reduced notional,
optimization aggregates, and cycle counts.

The runner performs no financial calculation. Result validation requires every
projected value to equal its exact source field.

Runs remain in caller order. Version one implements no winner, ranking,
metric-direction assumption, pairwise difference, sorting, or tie-breaking.

## Identity hierarchy

UUID5 identities use private version `historical-experiment-runner-v1`.
Canonical fingerprints cover:

- Complete ordered historical request/result and OHLCV content.
- Normalized ordered schedule.
- Initial-state specification and zero-commission semantics.
- Every complete variant policy and metadata.
- Complete experiment request.

Rolling request IDs bind experiment ID, variant ID and ordinal, and the three
shared fingerprints. Run IDs bind the variant fingerprint, rolling request and
result IDs, initial content fingerprint, and exact metric projection.
Aggregate result identity binds the complete request fingerprint, shared
fingerprints, and ordered run IDs.

No identity contains clocks, paths, Python hashes, object identity, services,
messages, or incidental mapping order.

Canonical namespace-free historical material is shared with the rolling runner.
The rolling runner continues applying its original namespace and version;
fixed regression UUIDs protect its prior identities.

## Reconciliation and immutable results

Before returning, live reconciliation verifies input immutability, isolation,
initialized content, exact historical object and schedule handoff, generated
metadata, rolling request identity, and rolling execution relationships.

`HistoricalExperimentRun` retains the exact variant, rolling request ID,
rolling result, initial content fingerprint, and projected metrics.
`HistoricalExperimentResult` retains the complete request, ordered runs, and
shared fingerprints. Neither retains factories or mutable services.

Immutable `__post_init__` validation is local: types, tuple order, ordinals,
variant alignment, rolling source relationships, metrics, fingerprints, and
deterministic IDs. It does not call factories, inspect live services, rerun
scenarios, execute simulations, or recalculate analytics.

## Growth and deferred work

Audit completeness retains one full rolling result per variant. Memory grows
approximately with variants multiplied by rolling frames, scenarios, and
analytics observations.

CLI integration, parameter-grid generation, ranking, pairwise comparisons,
mixed-success results, persistence, compact/lazy results, recovery, and
parallel execution are deferred. Experiment results are immutable audits, not
restart checkpoints.
