# Walk-forward aggregate analytics

## Responsibility and boundary

`trading_bot.experiments.walk_forward_analytics` is a pure deterministic
projection of one completed immutable
`HistoricalExperimentWalkForwardResult`. Each test fold remains an independent
out-of-sample evaluation. The layer does not run experiments, comparisons,
report builders, providers, serializers, optimization, brokerage, filesystem,
network, persistence, concurrency, GPU, or AI work.

The result is a descriptive audit. It defines no continuous equity curve,
compounded return, combined capital, ranking, score, recommendation, selection,
or tuning outcome.

## Policy and metric eligibility

A caller-authored policy contains a UUID, a nonempty ordered tuple of unique
metric policies, and ordered metadata. Observation retention is unconditional,
so a metric's operation tuple may be empty. Nonempty operation tuples reject
duplicates and are stored in canonical enum order.

All 26 `HistoricalExperimentMetrics` fields support exact ordered observations.
Version one additionally permits:

- `simulation_return` and `mean_expected_portfolio_return`: minimum, maximum,
  median, equal-fold arithmetic mean, and sign counts.
- `maximum_drawdown_percentage`, both turnover metrics, and
  `maximum_allocation_drift`: minimum, maximum, and median.
- `worst_cvar`: minimum, maximum, median, and sign counts.
- minimum and maximum target cash weight: minimum, maximum, median, and
  equal-fold arithmetic mean.
- absolute and realized simulation profit/loss: sign counts only.
- order, fill, decision, applied-cycle, and no-action-cycle counts: minimum,
  maximum, median, and equal-fold arithmetic mean.

Equity, absolute money, cost, notional, and drawdown-amount values otherwise
remain observations only. Matching starting equity and initial-state
fingerprints is not enough to make them composition-safe because fold duration,
opportunity set, and activity may differ. Nothing is summed. Drawdowns are
never combined. Turnover is never added or averaged. Counts are distributions,
not totals.

## Statistic semantics

Minimum and maximum retain the exact source scalar type. Median is an exact
`Decimal`; an even integer sample may therefore produce a value ending in
`.5`. Equal-fold means give every fold one equal observation weight and are
stored as reduced integer numerator and positive denominator. Decimal values
are converted from coefficient and exponent, without Decimal division,
rounding, ambient context, or floating point.

Sign counts classify exact values as positive, zero, or negative. Both signs of
Decimal zero are zero. Variant frequencies count exact selected variant UUIDs
and remain in first-selected-appearance order. They do not imply quality.
Every source selection is rank one, so rank-one selected frequency equals
selected frequency.

The source evaluator is fail-fast and returns no partial fold collection.
Consequently `successful_test_fold_count` equals `fold_count`. Zero-fold
sources are invalid. A one-fold source produces identical extrema and median,
a denominator-one mean, and one populated sign bucket.

## Auditability and reconciliation

Caller-ordered fold summaries retain fold, test report, test run,
rolling-result, selected variant, selected rank, and policy-ordered metric
evidence. Metric summaries repeat those observations in fold order and retain
only explicitly permitted statistics.

Reconciliation verifies exact one-row unranked test reports, selected-variant
handoff, complete fold and metric coverage, direct metric projection, derived
statistics, sign coverage, first-appearance frequency order, rank-one
frequency, input immutability, and deterministic identity. Training metrics
never enter aggregate observations.

## Deterministic identity

UUID5 uses private version
`historical-experiment-walk-forward-aggregate-v1`. The result commits to source
identities, complete ordered policy and metadata, fold counts, caller-ordered
fold provenance and observations, policy-ordered summaries and derived
statistics, and first-appearance-ordered frequencies.

Material is explicitly typed. Decimal text is derived directly from the finite
Decimal tuple and is independent of ambient context; signed zeros canonicalize
to zero. Identity excludes clocks, UUID4, paths, serialized bytes, Python
hashes, locale, object identity, and mutable services.

## Deferred work

CLI and serialization, partial-success sources, continuous-capital analytics,
weighted means, annualization, dispersion, confidence intervals, inferential
statistics, correlation, ranking, search, and tuning remain deferred.
