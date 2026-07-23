# Deterministic pairwise historical experiment comparison

## Responsibility and placement

Pairwise historical experiment comparison belongs in
`trading_bot.experiments`. It is a pure descriptive analysis over one completed
immutable `HistoricalExperimentReport` and one explicit immutable policy.

The compact report is the sole source. The comparator does not rerun an
experiment, regenerate a grid, rerun ranking, rebuild the report, or inspect
historical bars, rolling results, simulations, analytics, orders, fills,
ledgers, or CLI configuration.

## Explicit metric vocabulary

Pairwise policies reuse `HistoricalExperimentRankingMetric` because its 26
members exactly cover the scalar fields on `HistoricalExperimentMetrics`.
Pairwise code owns a separate immutable explicit metric-to-field mapping; it
does not import ranking implementation details.

Policies contain a nonempty ordered tuple of unique metrics. Free-form names,
dotted paths, grid assignments, ranks, ranking comparison values, and nested
objects are unsupported. Metric direction is deliberately absent.

## Pairing modes

`ALL_UNORDERED_PAIRS` enumerates caller-order index combinations:

```text
(0,1), (0,2), ..., (0,N-1), (1,2), ...
```

It produces `N * (N - 1) // 2` records. Pair enumeration order never changes.
`CALLER_ORDER` keeps the lower caller ordinal on the left.
`VARIANT_ID` may swap sides within a record so the lower UUID integer is left.

`BASELINE_VERSUS_ALL` requires one baseline UUID present exactly once in the
report. The baseline is always left and non-baseline rows remain in caller
order. It produces `N - 1` records and requires `CALLER_ORDER`; a meaningless
variant-ID orientation is rejected.

A one-row report validly produces no records. Every existing record has one
difference for every policy metric.

## Difference semantics

For every selected metric:

```text
difference = right_value - left_value
```

This signed convention is descriptive only. Positive and negative values do
not imply good, bad, preferred, safe, or recommended behavior.

Decimal operands produce an exact Decimal. Integer operands produce an exact
Python integer, which may be negative even though source count metrics are
nonnegative. The layer calculates no absolute or percentage difference,
ratio, normalization, score, aggregate, average, significance, rank, or
Pareto relationship.

Every difference retains its metric, exact left source value, exact right
source value, and exact calculated result. Pair records do not duplicate full
metrics objects.

## Exact Decimal arithmetic

Decimal subtraction never uses the ambient Decimal context. The private exact
algorithm:

1. validates two exact finite Decimals;
2. reads signs, coefficient digits, and exponents with `as_tuple`;
3. constructs signed Python integer coefficients;
4. aligns them at the smaller exponent with exact powers of ten;
5. subtracts the aligned left coefficient from the aligned right coefficient;
6. returns canonical positive `Decimal("0")` for zero; and
7. otherwise constructs a Decimal directly from result sign, digits, and the
   common exponent.

There is no float conversion or context-sensitive rounding. UUID material
uses `canonical_decimal` inside a private context with sufficient coefficient
precision and the platform's full supported Decimal exponent range.

Extremely large exponent gaps can require correspondingly large Python
integers. Narrow construction or resource failures become
`HistoricalExperimentPairwiseArithmeticError`; values are never rounded to
continue.

## Immutable models

`HistoricalExperimentPairwisePolicy` retains its caller UUID, ordered metrics,
pairing, orientation, optional baseline UUID, and ordered metadata. Metadata
keys are unique and the `historical_experiment_pairwise_` prefix is reserved.

`HistoricalExperimentPairwiseDifference` validates exact same-type source and
result scalars plus the right-minus-left relationship.

`HistoricalExperimentPairwiseRecord` retains its sequential ordinal,
left/right caller ordinals and variant UUIDs, and ordered differences. It does
not retain names or metrics objects.

`HistoricalExperimentPairwiseResult` retains its deterministic UUID, source
report UUID, exact policy, and ordered records. It does not retain the source
report, ranking result, grid result, or any nested execution tree.

## Deterministic identity

UUID5 identity uses private version
`historical-experiment-pairwise-v1`. Fixed material contains:

1. the source report UUID;
2. policy UUID, ordered metrics, pairing, orientation, baseline UUID or typed
   null, and ordered metadata; and
3. every ordered record's ordinal, caller ordinals, variant UUIDs, and ordered
   metric/left/right/difference values.

Material uses `DECIMAL`, `INTEGER`, `NULL`, `ENUM`, `UUID`, and `STRING`
markers. It excludes object identity, Python hashes, clocks, UUID4 generation,
locale, paths, CLI schemas, serialized report bytes, and source trees.

## Pure comparator and reconciliation

The comparator:

1. validates the exact compact report and policy;
2. captures relevant input invariants;
3. resolves explicit metric fields;
4. enumerates and orients pairs;
5. projects exact metric values;
6. calculates exact differences;
7. constructs local immutable records;
8. reconciles complete coverage, order, orientation, identities, source
   values, metric order, and arithmetic;
9. verifies unchanged inputs;
10. computes the result UUID; and
11. constructs the aggregate result last.

There is no partial result, mutation, retry, file operation, external state,
or background work.

Failures distinguish invalid policy, malformed source report, invalid metric
projection, arithmetic failure, generated reconciliation failure, and
malformed retained results.

## Boundaries and deferred work

This layer performs no ranking, winner selection, scoring, Pareto analysis,
recommendation, execution, tuning, persistence, scheduling, concurrency,
networking, brokerage, GPU work, or AI analysis.

Future work may add deliberate compact JSON and CSV presentation. Arbitrary
explicit pair lists, percentage changes, ratios, statistical significance,
confidence intervals, visualization, and parameter tuning remain deferred.
