# Optimized-simulation CLI analytics integration

## Purpose and execution boundary

The offline optimized-simulation CLI always analyzes a successful immutable
`OptimizedPaperSimulationResult` with
`OptimizedSimulationPerformanceAnalyzer`. It runs the simulator exactly once,
passes that exact result object to one analyzer invocation, and never reruns
optimization, certification, runtime, execution, accounting, or any other
simulation stage.

The successful order is configuration validation, fresh component assembly,
one simulation, one analysis, summary construction, optional complete in-memory
audit serialization, atomic output, and finally terminal output. No successful
text is printed before every requested operation succeeds. Without `--output`,
analytics and both summaries still run, but no audit tree is constructed.

## Deterministic analytics request

The CLI constructs an `OptimizedSimulationPerformanceRequest` with the exact
simulation result and the sole supported valuation basis,
`FRAME_RISK_PRICES`. Its UUID5 identity uses the private version
`optimized-simulation-cli-analytics-v1`, source simulation request and result
UUIDs, the `analytics` stage marker, valuation basis, and output audit schema
version 2. It reads no clock and creates no random UUID.

Request metadata preserves source simulation-request metadata in order, then
adds `optimized_simulation_cli_schema_version=2` and
`optimized_simulation_cli_source=offline-cli`. Metadata is not repeated in the
CLI UUID material because the source simulation result identity already commits
to it. The analytics result identity independently retains request metadata.

## Terminal reporting

The existing operational summary remains complete and labels lifetime
accounting as `final ledger realized P&L`. Separate performance, optimization,
and trading/risk sections report simulation equity and return, independently
selected drawdown maxima and their source frame/phase, simulation-relative
realized and unrealized P&L, commissions, slippage, execution cost, one- and
two-way turnover, allocation drift, optimization aggregates, order/fill counts,
risk outcomes, and rejected or reduced notional.

Financial values and ratios use canonical plain Decimal text. Percentage fields
are raw ratios and are not multiplied by 100. `--quiet` suppresses all successful
terminal output but never errors.

## Audit schema version 2

The input configuration schema remains numeric version 1. The output audit is
numeric version 2 with exactly these root members:

```text
schema_version
configuration
initial_state
simulation
analytics
```

`initial_state` retains initialization mode, bootstrap fills, and initial
component identities. `simulation` retains all version-one operational meaning:
simulation identity and counts, optimizer and certification stages, plans,
proposals, risk, orders and lifecycle events, submissions, fills, applications,
component state chains, final public ledger state, and complete fill history.

`analytics` explicitly serializes its request and result. It includes every
aggregate and frame performance field, ordered allocation drift, ordered equity
observations, diagnostics, optimization summary, and separate maximum-dollar
and maximum-percentage drawdown records. Each maximum references exactly one
retained source observation by sequence index, frame ordinal, phase, timestamp,
and equity. Missing or ambiguous exact matches fail output construction.

Decimals use canonical strings, datetimes use UTC ISO-8601, UUIDs use canonical
strings, enums use their values, symbols use normalized strings, and semantic
arrays preserve source order. JSON object keys are sorted, compact and pretty
layouts are stable, UTF-8 is used, and one trailing newline is emitted. Audit
schema version 1 is historical and is not emitted alongside version 2.

## Failure and atomicity

Known analytics request, valuation, reconciliation, and result-consistency
failures are reported as analytics errors under CLI exit code 6 and identify the
source simulation result. Their original exception remains the cause.
Unexpected programming exceptions remain uncaught.

Analytics and complete serialization finish before atomic writing begins. An
analytics or serialization failure creates no destination, preserves an
existing destination, leaves no temporary residue, and prints no successful
summary. A completed simulation exists only in fresh process memory; the CLI
persists no runtime state. The JSON report is an immutable audit, not a restart
checkpoint.

## Deferred scope

Annualization, Sharpe ratio, volatility, CAGR, benchmarks, charts, scenario or
forecast generation, historical-data acquisition, live paper operation,
scheduling, persistence, recovery, networking, brokers, GPU, and AI behavior
remain outside this integration.
