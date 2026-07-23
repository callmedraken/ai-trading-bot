# Rolling historical simulation CLI

## Command and boundary

The offline command is:

```text
python -m scripts.run_rolling_historical_simulation --config PATH
    [--output PATH] [--pretty] [--overwrite] [--quiet]
```

It loads local CSV history, initializes fresh in-memory paper components, and
invokes one `RollingHistoricalOptimizedSimulationRunner`. It performs no
networking, directory scanning, scheduling, checkpoint restoration, broker
operation, GPU work, or AI analysis. The audit is evidence of a completed run,
not restartable runtime state.

## Strict configuration schema

The command accepts numeric rolling configuration schema version 1. Its exact
root sections are `schema_version`, `request_id`, `historical_data`,
`rebalance_schedule`, `rolling_window`, `scenario`, `execution_prices`,
`timing`, `initial_state`, `optimization`, `portfolio_constraints`,
`rebalance`, `risk`, `fills`, `trading_enabled`, and `metadata`.

Unknown and missing fields are rejected at every level. Financial values are
plain finite Decimal strings; UUIDs use canonical text; booleans are strict;
timestamps must be timezone-aware and are normalized to UTC. Forecast horizon
is fixed internally at one `DAY_1` period. Version one supports only fixed
trailing windows, simple close returns, and close risk/fill prices.

The schedule is an explicit ordered timestamp array. The CLI does not infer
weekly, monthly, calendar, or every-N-bar dates. The rolling runner remains
authoritative for alignment, sufficient history, and timing conflicts.

## CSV paths and provider

Symbols and CSV sources are parallel ordered arrays. Each source contains a
symbol and a relative path; its symbol must match the same-position universe
symbol. Paths are resolved relative to the configuration file directory for
I/O. Resolved files must be unique regular files with one common parent and
must be named exactly `<SYMBOL>.csv`.

These restrictions follow the existing `CSVHistoricalDataProvider`, which
accepts one root and derives one filename per symbol. One provider is wrapped
in one `CoordinatingHistoricalDataProvider`, and the coordinator is called
once. Arbitrary per-symbol source routing is deferred.

Canonical configuration audits preserve lexically normalized relative paths
with `/` separators. Absolute paths, drive letters, working directories,
symlink targets, and output paths are excluded from deterministic audit data.
The loaded result's actual provider name and caller source label are retained
separately.

## Initialization and runner ownership

`CASH_ONLY` constructs a fresh ledger with explicit available cash.
`BOOTSTRAP_FILLS` creates deterministic zero-commission buy fills from ordered
position specifications and applies them through the ledger. It never injects
positions directly. Available cash means cash remaining after bootstrap, and
bootstrap symbols must belong to the historical universe.

Both optimized CLIs share the same bootstrap models, UUID logic, ledger
construction, and fresh engine/runtime/simulator builder. The historical CLI
then constructs one `RollingHistoricalSimulationRequest` containing the exact
loaded result and configured policies. It does not build windows, returns,
scenarios, expected returns, optimized frames, targets, an optimized simulation
request, or a performance request.

## Summary and execution order

Successful processing is argument validation, strict configuration parsing,
path resolution, one historical load, fresh initialization, one rolling run,
summary preparation, optional complete audit construction and serialization,
atomic output, and finally successful terminal output. `--quiet` suppresses
successful stdout only.

Without `--output`, the run and integrated analytics still complete, but the
full audit builder and nested serializers are not called.

The summary reports run identities, data and schedule counts, cash and equity,
simulation-relative return and P&L, separate final-ledger realized P&L,
drawdowns, costs, turnover, drift, trading/risk counts, optimization
aggregates, and one compact line per rebalance. Decimal ratios are not
multiplied by 100. Printing every frame is a version-one convention and can
produce substantial terminal output.

## Audit schema and serializer reuse

Rolling output uses numeric audit schema version 1 with exactly:

```text
schema_version
configuration
historical_data
initial_state
rolling
```

The historical section contains its request, actual provider, caller label,
ordered full OHLCV frames, missing-symbol information, completeness, and a
CLI-only UUID5 content fingerprint under
`rolling-historical-cli-history-v1`. This fingerprint is derived from the
actual loaded content and does not replace runner identities.

Each frame-generation audit retains window indices and timestamps,
source-frame and scenario identities, the complete scenario-generation result,
expected returns, diagnostics, optimized-frame fingerprint, and optimized
frame inputs. Child-window OHLCV is not repeated.

The nested optimized simulation and performance sections reuse extracted
schema-2 domain serializers. The rolling root does not embed the optimized
CLI's configuration, initialization, or root schema. The existing optimized
CLI remains a schema-2 wrapper with unchanged bytes.

Full history, scenario rows, frame audits, simulation audit, and analytics can
make reports large. All objects are built and serialized in memory.

## Determinism and atomic output

Semantic array order is preserved for symbols, sources, schedules, frames,
bars, metadata, generations, scenarios, expected returns, diagnostics, and
downstream audit arrays. Object keys are sorted during JSON serialization.
Compact and pretty output each end with one newline.

Equal configuration, CSV contents, initial state, and supported solver behavior
produce equal bytes within the same supported environment. Cross-platform and
cross-SciPy byte identity is not promised.

Output uses the existing same-directory atomic writer: complete in-memory
serialization, temporary file, flush, `fsync`, and `os.replace`. Failures before
replacement preserve an existing destination and remove temporary residue.

## Error codes

- `0`: success
- `2`: argument usage
- `3`: configuration read, UTF-8, or JSON syntax
- `4`: schema, path, provider, or loaded-data validation
- `5`: initialization/bootstrap
- `6`: rolling preparation, optimization, simulation, analytics, or reconciliation
- `7`: audit construction, serialization, or atomic output

Expected failures print concise stderr without a traceback and preserve their
domain causes. Unexpected programming exceptions propagate.

## Deferred work

Arbitrary source routing, combined CSVs, schedule factories, exchange-calendar
schedules, variable windows, pagination, streaming reports, persistence,
checkpoint recovery, live data, brokers, and real-money execution remain
outside this command.
