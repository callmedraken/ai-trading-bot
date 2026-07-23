# Offline historical experiment CLI

## Command and boundary

The offline command is:

```text
python -m scripts.run_historical_experiment --config PATH
    [--output PATH] [--pretty] [--overwrite] [--quiet]
```

It reads one strict local configuration, loads one aligned CSV history, and
invokes one `HistoricalExperimentRunner`. It performs no parameter-grid
generation, tuning, ranking, winner selection, networking, broker operation,
scheduling, persistence, concurrent execution, GPU work, or AI analysis.

## Configuration schema and paths

Input uses numeric schema version 1 with exact root members
`schema_version`, `request_id`, `historical_data`, `rebalance_schedule`,
`initial_state`, `variants`, and `metadata`. Unknown and missing fields fail at
every level. Decimal values are strings, UUID text is canonical, booleans are
strict, enum values are exact, and aware timestamps normalize to UTC.

Historical configuration matches the rolling CLI contract: ordered symbols
and sources, one exact `<SYMBOL>.csv` file per symbol, a common source
directory, and config-relative path resolution. One CSV provider and one
coordinator load the complete history exactly once. Canonical audit paths use
normalized `/` separators. Absolute paths, drive letters, working directories,
symlink targets, output paths, and temporary paths are operational only and
never enter identities or audit content.

The rebalance schedule is explicit, nonempty, unique, and strictly increasing.
The CLI does not derive calendar, weekly, monthly, or every-N-bar schedules.
The experiment runner remains authoritative for history membership, trailing
window sufficiency, and fill-offset compatibility.

## Initial state and factory adapter

Configuration maps directly to `HistoricalExperimentInitialState`.
`CASH_ONLY` contains nonnegative remaining cash and no positions.
`BOOTSTRAP_FILLS` contains ordered unique positive position quantities and
unit costs. Bootstrap commission is exactly zero, symbols belong to the
historical universe, and the initial timestamp cannot follow the first
rebalance.

A private CLI factory adapter creates a fresh `OrderEngine`, `PaperLedger`,
`PaperPortfolioRuntime`, and `OptimizedPaperPortfolioSimulator` for every
variant. Bootstrap fills use a CLI-private deterministic identity containing
the experiment request UUID, variant UUID, and variant ordinal. These
incidental IDs may differ while initialized accounting content remains equal.
The experiment runner independently validates public state and rejects reuse
of pre- or post-run mutable components.

Factory records remain private to the CLI and retain only variant context,
bootstrap fills, state IDs, and temporary component references required for an
optional completed audit. They are reconciled against the immutable experiment
result before serialization and never enter public experiment-domain results.

## Execution and failure semantics

Processing is argument validation, strict UTF-8 JSON parsing, path validation,
one historical load, initial-state and variant construction, one factory
adapter, one experiment request, one runner construction and invocation,
summary construction, optional complete in-memory audit serialization, atomic
output, and finally successful terminal output.

Variants execute sequentially in caller order. Domain fail-fast behavior is
authoritative: a failing variant stops later attempts, is not retried, returns
no partial aggregate, and does not imply rollback of an earlier private
simulator. Failure output identifies variant ordinal, UUID, display name, and
stage.

Exit codes are:

- `0`: success
- `2`: argument usage
- `3`: configuration read, UTF-8, or JSON syntax
- `4`: schema, path, provider, history, or request input
- `5`: valid initial-state factory or bootstrap construction
- `6`: experiment isolation, execution, or reconciliation
- `7`: audit construction, serialization, or atomic output

Unexpected programming exceptions remain uncaught.

## Summary and audit

The terminal summary retains caller variant order and prints every
`HistoricalExperimentMetrics` field using canonical Decimal text. Ratios are
not scaled. It performs no additional financial calculation, sorting,
ranking, recommendation, pairwise comparison, or winner selection.

Numeric experiment audit schema version 1 has root sections
`configuration`, `historical_data`, `initial_state`, and `experiment`.
Shared full OHLCV history and intended initial-state content appear once.
Every run retains its variant definition, run and rolling identities, exact
projected metrics, variant-specific initialization evidence, and the complete
rolling domain audit. It does not embed the rolling CLI schema, configuration,
historical root, or initial-state root.

The rolling and experiment serializers share domain-oriented historical and
rolling-result section builders. The rolling wrapper remains byte-compatible.
Semantic arrays preserve caller or domain order; nonsemantic JSON object keys
are sorted. Compact and two-space pretty output each end in exactly one
newline.

No separate audit UUID exists. Configuration request identity, experiment
result identity, shared fingerprints, ordered run identities, nested rolling
identities, and schema version already establish the audit boundary.

## Output, determinism, and operational limits

Without `--output`, the full experiment still runs and the summary prints, but
no audit tree or nested serialization is built. `--quiet` suppresses successful
stdout only.

Requested output is constructed and serialized completely before the existing
same-directory atomic writer creates a temporary file. Flush, `fsync`, and
`os.replace` preserve the prior destination until successful replacement and
clean temporary residue after expected failure.

Equal configuration, CSV content, and supported solver behavior produce equal
compact or pretty bytes in the same supported environment. Cross-platform and
cross-SciPy identity is not promised. Variant order and all identity-relevant
policy, history, schedule, initialization, and metadata changes remain
observable in identities or ordered output.

The report retains one complete rolling result per variant and therefore grows
with variants, rebalances, scenarios, simulations, and analytics. It is an
immutable audit, not a checkpoint or restart format. Ranking, parameter grids,
mixed-success results, persistence, recovery, streaming, parallel variants,
live data, and broker integration remain deferred.
