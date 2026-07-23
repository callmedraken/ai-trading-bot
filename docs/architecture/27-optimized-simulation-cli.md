# Offline optimized-simulation CLI

## Purpose and boundary

The optimized-simulation CLI is a local adapter over
`OptimizedPaperPortfolioSimulator`. It loads complete deterministic inputs from
JSON, constructs fresh in-memory execution and accounting components, runs the
simulator once, prints a plain-text summary, and optionally writes an immutable
JSON audit report.

The CLI does not obtain market data, generate forecasts or scenarios, contact a
broker, schedule work, resume prior state, invoke a backtest, or use GPU, AI,
database, or network functionality. It does not change optimization, target
certification, planning, risk, execution, fill, runtime, or ledger behavior.

## Command contract

From the repository root:

```text
python -m scripts.run_optimized_paper_simulation \
    --config PATH \
    [--output PATH] [--pretty] [--overwrite] [--quiet]
```

`--config` is required. `--pretty` and `--overwrite` require `--output`.
There are no prompts. Omitting `--output` prints only the summary; `--quiet`
suppresses a successful summary but never suppresses errors.

The command and version-one input schema remain unchanged. Successful runs now
always perform optimized-simulation performance analytics and emit audit schema
version 2 when output is requested, as specified in
`29-optimized-simulation-cli-analytics.md`.

The script only establishes the source-checkout import path and calls
`trading_bot.cli.optimized_simulation.main`. CLI configuration records remain
private and are not application-domain APIs.

## Version-one input schema

The root object contains exactly:

- `schema_version`, which must be the integer `1`
- `simulation_request_id`, a canonical UUID string
- `initial_ledger`
- a nonempty ordered `frames` array
- ordered `metadata`

Every frame explicitly supplies `as_of`, `submitted_at`, `filled_at`, ordered
risk and fill prices, ordered expected returns, a complete return-scenario set,
Mean-CVaR numerical parameters and risk aversion, portfolio constraints,
rebalance assumptions, proposal policy and confidence, risk limits and policy,
fill policy, the trading-enabled flag, and metadata. Price, expected-return,
scenario-symbol, state, and target universes retain exact configuration order.

Scenario-set and scenario-row UUIDs are source identities and are supplied by
configuration. Optimization, target, cycle, proposal, order, event, fill, and
result identifiers remain deterministic outputs of existing layers.

Objects reject missing and unknown fields. Ordered values use JSON arrays,
including metadata represented as `{key, value}` records. Objects are used only
for named fields whose key order has no meaning. The executable reference is
`examples/optimized-paper-simulation.example.json`.

## Strict scalar parsing

Financial Decimals must be JSON strings matching:

```text
^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$
```

They are parsed directly with `Decimal`. JSON numbers, exponent notation,
ambiguous leading zeros, NaN, and infinities are rejected. Domain constructors
then enforce positivity, ranges, scenario probabilities, portfolio constraints,
commission consistency, and other financial rules.

Timestamps must be ISO-8601 strings with an explicit timezone offset. Naive
timestamps and implicit local time are prohibited. Existing domain constructors
normalize them to UTC. UUID text must be canonical. Enum parsing uses exact,
case-sensitive `.value` text; relevant values include timeframe `1D` and
scenario sources `MANUAL`, `HISTORICAL`, `BOOTSTRAP`, `MONTE_CARLO`, and
`IMPORTED`.

Schema failures retain JSON paths such as
`$.frames[0].scenarios.rows[1].probability`. The CLI validates shapes and types;
it delegates domain formulas to existing immutable models.

## Ledger initialization

`initial_ledger` contains `initialization_mode`, an aware `as_of`, nonnegative
`available_cash`, and an ordered positions array.

`CASH_ONLY` requires no positions and constructs
`PaperLedger(available_cash)`. Because the public ledger constructor requires
positive starting cash, zero cash with no positions is rejected.

`BOOTSTRAP_FILLS` permits unique positions with symbol, positive quantity, and
positive average cost. It calculates:

```text
basis = sum(quantity * average_cost)
PaperLedger(available_cash + basis)
```

It then applies one zero-commission BUY `OrderFill` per position in input order
at `initial_ledger.as_of`. UUID5 order and fill identities use the version
`optimized-simulation-cli-bootstrap-v1` and include the simulation request UUID,
mode, ordinal, symbol, canonical quantity, canonical average cost, and timestamp.
Order and fill IDs use distinct identity suffixes.

These fills are synthetic opening-state accounting records. They are not user-
supplied history and have no matching `OrderEngine` lifecycle. No private ledger
state is accessed. `initial_ledger.as_of` must not follow the first frame.

## Assembly and simulator invocation

Each process constructs:

```text
OrderEngine
PaperLedger
PaperPortfolioRuntime(engine, ledger)
OptimizedPaperPortfolioSimulator(runtime)
```

The CLI calls `simulator.run(request)` exactly once and never retries a frame.
Only existing immutable results and final public ledger state feed reporting.

## Deterministic summary and audit

The terminal summary uses plain text and stable labels. It includes aggregate
identity, status and counts, initial and final cash, final realized P&L and
positions, followed by each frame's timestamp, optimization status, ordered
target weights and cash weight, cycle status, risk counts, order and fill counts,
ending cash, and positions. Symbols follow frame order. Scenario matrices are
not printed.

Historical audit schema version `1` explicitly contained canonical configuration, initial
mode and bootstrap fills, simulation request/result identities and counts,
initial/final component state IDs, and ordered frame audits. Frame audits retain
optimizer output and diagnostics, certification and target, runtime cycle, risk
evaluations, created orders and events, submitted orders and events, generated
fills, fill application events and ledger values, and pre/post state IDs. Final
state retains cash, realized P&L, ordered positions, and complete ledger fill
history.

Schema version 1 is no longer emitted. Its operational information is retained
under the `simulation` member of schema version 2 alongside the analytics audit.

Every final-history fill has origin `INITIAL_POSITION_BOOTSTRAP` or `SIMULATION`.
Bootstrap fills appear in initial state and never in a frame-generated fill
array.

Serialization is explicit rather than recursive dataclass conversion. Decimal
values use canonical plain strings, datetimes use UTC ISO text, UUIDs use
canonical lowercase text, enums use `.value`, Symbols use their string value,
and tuples become arrays without reordering. JSON uses UTF-8,
`ensure_ascii=False`, sorted non-semantic object keys, fixed compact separators
or two-space pretty indentation, and exactly one trailing newline. Pretty mode
changes layout only.

## Atomic output

An existing output is rejected before simulation unless `--overwrite` is set.
The complete audit tree and serialized text are built in memory first. The
destination parent must already exist. Output is written to a random temporary
file in that same directory, flushed, synchronized with `os.fsync`, closed, and
then installed with `os.replace`. No-overwrite collision is checked again before
replacement. Failures remove the temporary file and preserve any prior
destination when replacement did not occur.

The same-directory replacement is the supported local Windows behavior. Locked
files, network shares, and concurrent writers can still cause a reported output
failure.

## Errors and failure semantics

Stable exit codes are:

- `0`: success
- `2`: argparse usage
- `3`: input read, UTF-8, or JSON syntax
- `4`: schema or domain configuration
- `5`: unavailable or otherwise non-optimal optimizer output
- `6`: certification, simulation, runtime, or reconciliation
- `7`: serialization, write, or replacement

Expected errors print one concise stderr message without a traceback. Unexpected
programming errors remain uncaught. An unavailable optimizer identifies the
frame, status, stable diagnostics, and recommends
`pip install -e ".[optimization-cpu]"`.

No partial audit is written. The simulator's per-frame commits still apply in
memory, but a failed CLI invocation owns fresh components and persists no state;
process exit discards earlier progress.

## Relationship and deferred operation

The simulator and runtime remain directly usable Python APIs. CLI input is not a
runtime persistence format, and the audit report is not a restart checkpoint.
Live paper operation remains deferred and would require separate trusted market
data, forecast/scenario production, scheduling, durable state, concurrency,
recovery, and operational controls. Brokerage connectivity and real trading are
outside this architecture.
