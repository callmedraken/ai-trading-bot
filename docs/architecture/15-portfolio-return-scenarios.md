# Portfolio return scenarios

The `trading_bot.portfolio.scenarios` module defines immutable deterministic
return distributions for the existing portfolio domain. It performs no
scenario generation, random sampling, optimization, numerical conversion,
backtesting, rebalancing, serialization, networking, AI, or brokerage work.

## Returns, columns, and rows

Each `ReturnScenario` contains a caller- or generator-supplied UUID, an ordered
return tuple, an explicit probability, and ordered string metadata. A return is
a signed simple arithmetic total return over the enclosing
`ForecastHorizon`; it is neither logarithmic nor annualized. Exact negative one
is permitted, representing complete loss of initial value. Values below
negative one are rejected for the initial long-only security domain. Nonlinear
payoffs and liability structures require a different future contract.

Rows do not duplicate symbols. `ReturnScenarioSet.symbols` establishes exact
column meaning. Symbols remain in configured portfolio order, returns remain
in column order, and rows remain in producer order. Nothing is sorted by UUID,
probability, return, source, or metadata.

## Probabilities and identity

Every scenario has a finite positive `Decimal` probability no greater than one.
The complete probability total must equal `Decimal("1")` exactly. There is no
tolerance, implicit equal weighting, or model-side normalization. Scenario-set
and row UUIDs are supplied; models never generate random identity. Row IDs must
be unique within a set.

A future numerical adapter may preserve row order, validate all preceding
probabilities, require their sum below one, and set the final probability to
`Decimal("1") - sum(previous)`. The residual must be positive and must not hide
a materially invalid distribution. Construction revalidates the exact total.

## Horizon, provenance, and compatibility

Scenario-set timestamps are aware and normalized to UTC. The set covers one
exact `ForecastHorizon`. Manual provenance may omit a source name; historical,
bootstrap, Monte Carlo, and imported sources require a nonblank source name.
Metadata remains an immutable ordered tuple with unique keys.

Compatibility is independent of any optimization request type. Callers supply
an as-of timestamp, forecast horizon, and ordered symbols. All three must equal
the scenario set exactly. Symbol membership or ordering failure is distinct
from timestamp or horizon incompatibility. No clock, date-only matching, or
implicit staleness policy is used.

## Expected returns, cash, and loss

`implied_expected_returns()` derives one existing `ExpectedReturn` per symbol:

```text
sum(scenario probability * scenario return for the asset column)
```

The calculation uses exact Decimal arithmetic, preserves symbol order, and
excludes cash. Implied values are not stored or required to match forecast
expected returns. A future Mean-CVaR optimizer may use explicit forecasts for
reward and scenarios for downside risk.

The set stores a finite scalar `cash_return`, defaulting explicitly to zero. It
covers the same horizon and is identical across rows. Future portfolio loss is:

```text
portfolio return =
    sum(asset weight * scenario asset return)
    + cash weight * cash return

loss = -portfolio return
```

CVaR confidence and specialized optimizer requests remain deferred.

## Determinism and numerical boundaries

Tuple-like inputs are defensively copied. Negative Decimal zero is normalized.
All values reject NaN and infinity. A future CPU or GPU adapter must preserve
row and column order, never construct Decimal directly from binary float, use
documented text conversion and quantization, and declare any feasibility
tolerance explicitly. It may not silently clip returns or probabilities or
normalize a distribution.

Future stochastic generators must require explicit seeds, avoid global random
state, and include all randomness-affecting configuration and source-data
identity in deterministic IDs and diagnostics. Generator protocols are deferred
until a concrete historical, bootstrap, or Monte Carlo method establishes a
stable request contract.

NumPy, pandas, SciPy, CVXPY, CUDA, RAPIDS, CuPy, cuOpt, cuFOLIO, optimization,
scenario generation, backtest/rebalance integration, CLI/serialization,
networking, AI, and brokerage functionality remain outside this milestone.
