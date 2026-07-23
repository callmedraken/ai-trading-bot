# Historical return-scenario adapter

## Scope and package boundary

`HistoricalReturnScenarioFactory` lives beside the immutable scenario contracts
in `trading_bot.portfolio`. It converts one already-loaded
`MultiSymbolHistoricalDataResult` into a historical `ReturnScenarioSet`, its
implied ordered `ExpectedReturn` tuple, and an immutable generation audit.

The factory performs no I/O. It accepts no provider, path, mapping, or raw
matrix and does not fetch data, optimize portfolios, certify targets, invoke
runtime or simulation, parse CLI reports, persist state, contact brokers, or
use networking, GPU, or AI functionality.

## Canonical historical input

The request retains a caller UUID, exact multi-symbol historical result,
explicit generation policy, UTC scenario timestamp, one-period daily forecast
horizon, explicit cash return, source name, and ordered caller metadata.
Metadata is defensively copied, requires unique keys, and reserves the
`historical_scenario_` prefix.

The complete result may originate from either alignment policy, but every frame
must be complete. At least two frames are required. Frames must retain strictly
increasing normalized UTC timestamps, the exact historical-request symbol
order, no missing symbols, and one bar whose symbol and timestamp match each
ordered mapping entry. No sorting, filtering, filling, interpolation, or source
mutation occurs.

## Price, return, chronology, and horizon

Version one supports only canonical `Bar.close`,
`HistoricalScenarioReturnMethod.SIMPLE`, and
`HistoricalScenarioWindowPolicy.ALL_SUPPLIED`. Close values must be finite,
strictly positive `Decimal` values. The adapter does not claim adjusted-close
semantics or reinterpret the provider's adjustment behavior.

For adjacent frames:

```text
return[i, symbol] = close[i + 1, symbol] / close[i, symbol] - 1
```

With `N` observations, `N - 1` rows are produced in chronological order and
historical symbol-column order. Zero returns are valid. No value crosses
through float and returns are not quantized.

The request `as_of` must equal the final frame timestamp, and every earlier
frame must precede it. This prohibits future observations and undocumented
stale gaps. Timestamps remain source-provided daily-bar identities; they are
not inferred exchange sessions, market opens, or market closes.

The forecast horizon must be exactly one `Timeframe.DAY_1` period. Every row is
treated as one adjacent supplied daily-observation outcome. The adapter does not
use a market calendar to prove session adjacency or infer a different horizon.

## Fixed Decimal context

Return division, probability calculation, implied expected returns, and
arithmetic reconciliation execute under a private local Decimal context with
precision 28 and `ROUND_HALF_EVEN`. The global context is never modified.

Repeating divisions are therefore deterministic fixed-context Decimal values,
not exact rational numbers. Identity text uses context-independent fixed-point
formatting, normalizes numeric zero, and removes insignificant fractional
trailing zeros.

## Scenarios, probabilities, and expected returns

Each row receives a UUID5 identity, its ordered return tuple, one probability,
and empty metadata. The set uses `ScenarioSource.HISTORICAL`, the caller's
source name, explicit cash return, and generated provenance metadata.

For `M` rows:

```text
base probability = Decimal(1) / Decimal(M)
rows 0 through M - 2 = base probability
final row = Decimal(1) - sum(previous rows)
```

All calculation occurs under the fixed context. Every probability must be
positive and the total must equal one exactly. A one-row distribution receives
probability one. If a repeating division makes the final residual differ from
the base value, the result records
`UNEQUAL_FINAL_RESIDUAL_PROBABILITY`.

After set construction, the factory calls
`ReturnScenarioSet.implied_expected_returns()` under the same local context.
The exact tuple is retained and reconciled in scenario symbol order. Cash is
not an `ExpectedReturn`; the explicitly supplied finite cash return remains a
scalar set-level outcome and must be at least negative one.

## Provenance and diagnostics

Scenario-set metadata contains caller entries first, followed by:

```text
historical_scenario_observation_start
historical_scenario_observation_end
historical_scenario_observation_count
historical_scenario_return_row_count
historical_scenario_price_field
historical_scenario_return_method
historical_scenario_window_policy
```

No path or generation timestamp is included. Diagnostics are ordered as:

1. `MINIMUM_HISTORY_ONLY` for exactly two observations.
2. `UNEQUAL_FINAL_RESIDUAL_PROBABILITY` when applicable.
3. `CONSTANT_PRICE_SERIES` once per constant symbol in universe order.

Constant prices and zero returns remain valid. Diagnostic messages are
human-readable audit text and do not participate in identities.

## Deterministic identity

UUID5 identities use `historical-return-scenarios-v1` and a private namespace.
Row identity contains the request ID, ordinal, adjacent timestamps, ordered
symbols, and canonical returns. Probability is deliberately excluded.

Scenario-set identity contains the request ID, ordered row IDs, ordered
probabilities, `as_of`, horizon, cash return, historical source, source name,
and ordered generated metadata.

Generation-result identity contains a canonical complete request fingerprint,
scenario-set ID, ordered expected returns, and diagnostic code/symbol pairs.
The request fingerprint includes historical request bounds and policies,
provider name, ordered symbols, every frame and bar identity with close price,
generation policy, horizon, cash return, source name, and caller metadata.
Messages, clocks, paths, object identity, hashes, and incidental mapping order
are excluded.

## Exceptions and atomicity

Focused exceptions distinguish malformed requests, chronology, universe,
prices, probabilities, domain-output reconciliation, and inconsistent
aggregate results. Expected `ReturnScenario`, `ReturnScenarioSet`, and
`ExpectedReturn` construction failures are wrapped as reconciliation failures
with their original causes. Broad exceptions are not caught.

Generation validates all source structure and prices, calculates every return
and probability locally, constructs every row and the complete set, derives
expected returns, reconciles identities and values, and constructs the
aggregate result last. Failure returns no partial result and changes no input.
The result validates retained local relationships and deterministic identity
without recalculating source historical returns.

## Relationships and deferred work

Historical providers continue to own file access, parsing, request filtering,
and timestamp alignment. The adapter owns empirical returns, probabilities,
expected-return derivation, identities, and audit traceability. Callers may
place the returned scenario set and expected-return tuple into an explicit
optimized-simulation frame; neither that frame nor the simulator is modified.

Rolling and trailing windows, automatic rebalance-date selection, market
calendar checks, missing-data policies, adjusted-close semantics, log or
multi-period returns, probability weighting alternatives, CLI integration,
historical runners, persistence, and live operation remain deferred.
