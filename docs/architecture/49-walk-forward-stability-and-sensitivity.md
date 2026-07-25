# Walk-forward stability and sensitivity analysis

## Responsibility and boundary

`trading_bot.experiments.walk_forward_stability` is a pure deterministic
projection of one completed immutable `HistoricalExperimentWalkForwardResult`.
An optional completed aggregate result is provenance and reconciliation input
only. The walk-forward result remains authoritative.

The layer does not invoke providers, experiment runners, comparison, report
construction, aggregate analysis, CLI code, serialization, persistence,
networking, optimization, or AI work. Test folds remain independent. No
continuous capital, equity curve, total, compounding, weighting, annualization,
ranking, recommendation, score, objective, or causal interpretation is defined.

## Selection evidence

Selections remain in retained fold order. Every adjacent ordered pair,
including a self-transition, is retained. Directional transition frequencies
remain in first-transition-appearance order. Variant frequencies remain in
first-selected-appearance order.

Consecutive runs partition the complete selection sequence. Persistence counts
self-transitions; changed-adjacency counts non-self transitions. Their sum is
one less than the fold count. Persistence ratio is an exact reduced rational.
A one-fold result has no transitions, a `None` ratio, and one run of length one.

These measures describe recurrence in the retained sequence only.

## Metric evidence and eligibility

Every policy-selected metric retains exact test-fold observations. Magnitude
operations are adjacent absolute change, range, and unscaled median absolute
deviation.

Dimensionless returns, percentages, turnover, drift, expected return, CVaR, and
cash weights permit magnitude operations. Activity counts permit them only
with equal test durations and equal test schedule counts. Money, equity, cost,
drawdown-amount, and notional metrics are observations-only for magnitude
purposes.

Simulation return, expected return, CVaR, and signed simulation profit/loss
permit direct nonzero sign-change counts. A transition involving zero is not a
sign change. Relative changes are not defined.

Duration-sensitive magnitude operations require equal exact UTC test
durations. Counts additionally require equal schedule counts. Drift and cash
weights may explicitly use no comparability rule. These checks are minimum
structural conditions and do not establish economic comparability.

Adjacent changes validate each adjacent pair. Range and median absolute
deviation validate the complete fold collection. Sign changes require no
duration rule. Observation-only policies require `NONE`.

## Exact arithmetic

Adjacent changes and ranges retain the source scalar type. Median and median
absolute deviation are exact finite `Decimal` values. Arithmetic converts
finite Decimal tuples to exact rational coefficients and never uses floating
point or ambient Decimal context. Signed zero canonicalizes to zero.

Median is retained only when median absolute deviation is requested. Median
absolute deviation is `median(abs(value - median(values)))` without a scaling
constant.

## Optional aggregate provenance

An optional aggregate result must identify the exact walk-forward source and
match fold, test report, test run, selected variant, and selected-rank
provenance. Overlapping aggregate observations must exactly equal authoritative
test-fold metrics. Missing aggregate metrics fall back to those retained
test-fold metrics without running aggregate analysis.

Optional aggregate identity is bound into the stability result identity, so
otherwise equal results produced with and without that provenance have distinct
result UUIDs.

## Deterministic identity and reconciliation

UUID5 uses `historical-experiment-walk-forward-stability-v1` with explicitly
typed canonical material. Identity binds source and optional aggregate
provenance, the complete policy, retained fold order, selection observations,
runs, transitions and frequencies, metric observations, comparability
evidence, and every derived measure.

Reconciliation reconstructs selection runs, transitions, frequencies, metric
changes, range, median, median absolute deviation, sign-change counts, and the
result UUID. Clocks, paths, serialized bytes, Python hashes, locale, object
identity, floating point, and mutable services are excluded.
