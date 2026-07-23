# Compact historical experiment report

## Responsibility and placement

The compact historical experiment report belongs in
`trading_bot.experiments`. It is a pure, deterministic projection of one
completed `HistoricalExperimentResult`; it does not run an experiment, grid,
comparison, optimization, simulation, or analytics calculation.

The report is an audit summary, not a restart checkpoint. It deliberately
excludes historical bars, rolling-result trees, simulation and performance
trees, orders, fills, ledger histories, and the source experiment, grid, and
comparison objects. Future JSON and CSV exporters can consume this compact
domain model without making serialization part of the model or builder.

## Public API

- `HistoricalExperimentReportVariantSource`: exactly `EXPLICIT` or `GRID`.
- `HistoricalExperimentReportVariant`: one caller-order compact run row.
- `HistoricalExperimentReportRanking`: optional compact ranking provenance.
- `HistoricalExperimentReport`: immutable aggregate report.
- `HistoricalExperimentReportBuilder.build(...)`: all-or-nothing projection.

The builder accepts an exact completed experiment result and optional exact
grid and comparison results. Supplying neither, either, or both provenance
objects is supported.

## Caller-order rows

Rows always follow the experiment's caller order. Each row retains the caller
ordinal, experiment run UUID, rolling result UUID, variant UUID and name, and
the exact immutable `HistoricalExperimentMetrics` instance from its source
run. The rolling identifier is `run.rolling_result.result_id`, not the rolling
request UUID.

The row never retains its source run or rolling result. Its metrics are not
recomputed, normalized, summarized, or projected from nested performance data.
All 26 metric fields therefore remain available exactly as accepted by the
historical experiment domain.

## Grid provenance

Grid provenance exists only when a grid result is explicitly supplied. It is
never inferred from variant IDs, names, metadata, or generated-looking values.

The builder reconciles generated variants positionally. Counts and sequential
ordinals must match, and each generated variant object must be the exact
variant object held by the corresponding experiment run. UUID and name must
also agree. Ordered, typed assignments are copied onto that row. A grid report
retains only the grid specification UUID and result UUID at aggregate level.

An explicit report has null grid IDs, null row grid ordinals, and empty row
assignment tuples.

## Ranking provenance

Ranking provenance exists only when a comparison result is supplied. The
comparison must retain the exact source experiment result.

Ranked output order does not alter report row order. The builder creates a
transient identity lookup keyed by each source run object's identity, verifies
that every run occurs exactly once, then projects rank and ordered comparison
values onto caller-order rows. Object identity is used only during local
linkage and never enters report identity.

The compact ranking summary retains the policy UUID, policy fingerprint,
comparison result UUID, copied ordered criteria, and tie breaker. It does not
retain the policy or comparison object. Without ranking, the aggregate ranking
is null and every row has a null rank and empty comparison values.

## Deterministic identity

`report_id` is UUID5 material under the private
`historical-experiment-report-v1` identity version. Fixed-order material
contains:

1. experiment request/result UUIDs and shared historical, schedule, and
   initial-state fingerprints;
2. variant source and grid UUIDs or typed nulls;
3. ranking UUIDs or typed nulls, followed by criteria and tie breaker when
   present;
4. every caller-order row, including grid/ranking provenance and all 26
   explicitly ordered metric names and values; and
5. ordered report metadata.

Values use explicit `DECIMAL`, `INTEGER`, `BOOLEAN`, `NULL`, `ENUM`, `UUID`,
and `STRING` markers. Decimal material uses `canonical_decimal` under an
isolated sufficient-precision Decimal context, making identity independent of
the caller's context and treating positive and negative zero equivalently.
Identity does not use floating point, object representations, object identity,
Python hashes, clocks, paths, locale, CLI schemas, or nested rolling content.

## Metadata

Report metadata is caller-supplied and ordered. It is copied independently and
is not merged with metadata from any source object. Entries must be exact
`MetadataEntry` values with unique keys. Keys beginning with
`historical_experiment_report_` are reserved.

## Validation and reconciliation

The builder follows a pure, no-retry, all-or-nothing sequence:

1. validate the exact experiment result and local run relationships;
2. copy and validate report metadata;
3. capture source invariants;
4. reconcile optional grid rows positionally;
5. reconcile optional ranking rows by exact source-run identity;
6. build local caller-order report rows;
7. verify complete provenance coverage;
8. confirm source invariants did not change;
9. reconcile projected values against source values;
10. calculate the canonical UUID; and
11. construct the aggregate report last.

Source IDs and nested experiment reconciliation are not recalculated. The
retained models validate only their local fields and relationships, including
exact scalar types, sequential ordinals, source-mode consistency, ranking
coverage, metadata, metrics, and canonical report identity. This makes a
retained report independently valid without access to its source trees.

Failures are separated into invalid input, grid provenance, ranking
provenance, metric, builder reconciliation, and retained-report consistency
exceptions. No partial report is returned and inputs are never mutated.

## Boundaries and deferred work

The report layer performs no file or CLI operations, networking, broker
access, scheduling, persistence, concurrency, GPU work, AI analysis, analytics
recalculation, or experiment execution.

Future work may add deliberate JSON and CSV exports. Pairwise differences,
Pareto fronts, composite scores, charts, parameter tuning, and recommendations
remain explicitly deferred.
