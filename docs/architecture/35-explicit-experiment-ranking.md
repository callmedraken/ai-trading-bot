# Explicit historical experiment ranking

## Responsibility and package boundary

`trading_bot.experiments` contains a pure comparison layer over one already
completed immutable `HistoricalExperimentResult`. A caller supplies an
explicit `HistoricalExperimentRankingPolicy`; the
`HistoricalExperimentComparator` returns an immutable ranked comparison.

The comparator does not run experiments, rolling simulations, optimization,
performance analytics, execution, risk, or accounting. It performs no file or
CLI work, networking, brokerage, scheduling, persistence, concurrency, GPU
work, AI analysis, parameter search, variant generation, or tuning.

## Explicit metrics, criteria, and directions

`HistoricalExperimentRankingMetric` enumerates every exact scalar field on
`HistoricalExperimentMetrics`: equity and profit or loss, returns, drawdowns,
costs, turnover, allocation drift, order/fill/risk counts and notionals,
optimization aggregates, cash-weight extrema, and applied/no-action cycle
counts. A fixed immutable mapping selects one exact field for each enum. No
free-form path or nested source object is accepted.

Every `HistoricalExperimentRankingCriterion` contains one exact metric and one
explicit `ASCENDING` or `DESCENDING` direction. A policy contains a nonempty
ordered tuple of unique-metric criteria. Directions are never inferred from
names: the comparator does not decide whether return, drawdown, CVaR, cost, or
another field is desirable.

Criteria are applied lexicographically in caller order. The comparator reads,
validates, compares, and retains exact source values. It performs no
normalization, annualization, weighting, averaging, scoring, utility
calculation, sign change, float conversion, or arithmetic across fields.

## Tie-breaking, ranks, and caller order

Every policy explicitly chooses `CALLER_ORDER` or `VARIANT_ID`.
Caller-order ties compare the source run ordinal. Variant-ID ties compare the
canonical UUID integer. Variant names, run IDs, hashes, locale, object identity,
and stable-sort source order do not establish tie order.

An explicit comparison function used through `functools.cmp_to_key` compares
same-field exact values and reverses the comparison outcome for descending
criteria. It returns only `-1`, `0`, or `1`, never a numeric difference. After
all metric equality, the selected tie-breaker establishes a total order.

Ranks are distinct sequential positions from one through the run count.
Metric ties therefore do not produce dense or competition ranks.
Rank one means only first under the supplied policy; it does not mean
recommended, optimal, safe, or appropriate for live trading.

The source experiment result and its caller-ordered run tuple remain unchanged.
Each `HistoricalExperimentRankedRun` retains the exact source run, its original
caller ordinal, its sequential rank, and the exact ordered comparison values.
Ranked output is a separate immutable tuple.

## Validation and value semantics

Policies require a caller UUID, a nonempty defensively copied criteria tuple,
an explicit supported tie-breaker, and defensively copied ordered metadata.
Criterion metrics are unique. Metadata keys are unique, and keys beginning
`historical_experiment_comparison_` are reserved.

Selected Decimal values must be exact finite `Decimal` instances. Selected
integer values must be exact nonnegative integers and may not be booleans.
Values are never coerced. Negative and positive Decimal zero compare equal.
Identity formatting uses the repository `canonical_decimal` convention, so
both have canonical identity text zero.

Source validation is deliberately local: the comparator requires an exact,
nonempty `HistoricalExperimentResult`, sequential run ordinals, unique run and
variant IDs, exact request-variant relationships, exact experiment metrics,
and valid selected scalars. It does not inspect historical bars, recalculate
rolling identities, project performance again, or rerun full experiment
reconciliation.

## Identity hierarchy

UUID5 identities use a private namespace and version
`historical-experiment-comparison-v1`.

The caller-owned policy UUID distinguishes policy identity. A canonical policy
fingerprint additionally binds that UUID, ordered metric/direction criteria,
explicit tie-breaker, and ordered metadata. Equal policy content with a
different caller UUID intentionally has a different fingerprint.

The comparison result UUID binds the source experiment result UUID, policy
UUID and fingerprint, and every ranked record in rank order: rank, caller
ordinal, source run and variant UUIDs, ordered metric/value pairs, and explicit
tie-break material. Values are type marked as `DECIMAL|...` or `INTEGER|...`.

Identities exclude clocks, UUID4 generation, object identity, Python hashes,
locale, paths, variant names, human messages, mapping order, and ambient
Decimal context. Ranked rows need no separate UUID because the aggregate
identity already commits to their complete ordered evidence.

## Pure execution, reconciliation, and atomicity

Comparison validates source and policy, captures canonical invariants,
extracts and validates every value, builds local sortable records, sorts,
assigns ranks, constructs immutable ranked records, reconfirms unchanged
inputs, reconciles the local output, and constructs the aggregate result last.
Failure returns no partial result and mutates no input.

Shared local reconciliation verifies complete exact source-run coverage,
absence of duplicate or foreign runs, sequential ranks, caller ordinals,
direct comparison values, canonical ordering and tie-breaking, policy
fingerprint, and result UUID. Result-model validation does not construct
another comparison result or invoke the comparator.

Focused exceptions distinguish invalid policies, invalid metrics, failure to
establish total ordering, generated-output reconciliation, and inconsistent
retained results.

## Relationships and deferred work

The experiment runner remains responsible for executing isolated variants and
projecting metrics. The neutral experiment CLI remains unchanged and performs
no ranking. A later CLI milestone may accept and serialize an optional explicit
policy.

Pairwise differences, Pareto analysis, composite scores, weighted utilities,
competition or dense ranks, CLI integration, parameter grids, automatic
direction selection, search, and tuning remain deferred.
