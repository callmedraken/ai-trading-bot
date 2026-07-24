# Pairwise historical experiment CLI and exports

## Responsibility

The historical experiment command may apply one explicit pairwise policy to
one completed immutable `HistoricalExperimentReport`. Pairwise analysis is an
optional derived audit view. It does not affect schema-3 experiment
configuration, execution, ranking, compact-report content, or any upstream
identity.

The policy is a separate strict UTF-8 JSON document with numeric schema version
1, supplied through `--pairwise-policy`. Its exact domain policy is passed to
`HistoricalExperimentPairwiseComparator.compare()` once.

## Command behavior

The optional arguments are:

```text
--pairwise-policy PATH
--pairwise-json PATH
--pairwise-json-pretty
--pairwise-csv PATH
```

JSON and CSV destinations require a policy. Pretty output requires a JSON
destination. Policy-only mode is valid and prints a neutral result, policy,
pairing, orientation, ordered metric, and record-count summary. It does not
write a file.

Pairwise behavior does not require compact exports. When compact or pairwise
behavior needs a compact report, the command builds it once. The same exact
object is retained in the CLI run result, supplied to the comparator, and
supplied to any requested compact serializers. The comparator is never
constructed without a policy and is called exactly once with a policy.

## Difference and export semantics

Each difference remains the domain-defined neutral value:

```text
difference = right value - left value
```

No direction, winner, score, normalization, percentage difference, ratio, or
recommendation is inferred.

Pairwise JSON has independent numeric schema version 1. It contains only result
and source-report identities, the exact policy, ordered records, and ordered
selected differences. Decimal values are canonical strings; integers remain
JSON integers.

Pairwise CSV is long format with one row per record and selected metric. Record
order is primary and policy metric order is secondary. Values are not sorted,
scaled, or augmented with names from the source report. Policy metadata is
canonical compact JSON.

Both formats are deterministic UTF-8 text with one final newline. They are
audit artifacts, not restart checkpoints.

## Output coordination and independence

Full audit, compact JSON, compact CSV, pairwise JSON, and pairwise CSV
destinations are resolved with `Path.resolve(strict=False)`, must be pairwise
distinct, and share `--overwrite`. Every destination is preflighted before
configuration parsing or execution.

All requested artifacts serialize completely before staging. The existing
coordinated writer stages, flushes, and fsyncs every file before replacement in
this order:

1. Full audit
2. Compact JSON
3. Compact CSV
4. Pairwise JSON
5. Pairwise CSV

Each replacement is individually atomic. There is no aggregate transaction or
rollback; an earlier replacement may remain if a later replacement fails.
Remaining temporary files are cleaned up.

Adding pairwise behavior cannot change full-audit or compact-report bytes, the
compact report ID, or experiment, rolling, optimization, simulation,
performance, grid, or ranking identities. Pairwise policy metadata never enters
the compact report.

## Errors and boundaries

Usage and normalized collision errors exit 2. Configuration or policy
read/UTF-8/JSON failures exit 3. Schema and policy validation exits 4.
Initialization exits 5. Grid, experiment, ranking, report, and pairwise domain
failures exit 6. Preflight, serialization, staging, and replacement failures
exit 7. Unexpected exceptions propagate.

Policy parsing completes before grid generation, historical-data loading, or
experiment execution. Report failure prevents comparison. Comparison failure
prevents serialization and writes. Serialization failure prevents staging.
Replacement failures do not trigger retries or domain reruns.

The serializers consume only an exact
`HistoricalExperimentPairwiseResult`. They do not inspect the source report,
experiment, grid, ranking tree, rolling results, simulations, orders, fills,
ledgers, providers, brokers, or networks.

Arbitrary pairs, percentage and ratio differences, statistical analysis,
charts, scoring, Pareto analysis, selection, tuning, scheduling, persistence,
concurrency, GPU work, and AI remain deferred.
