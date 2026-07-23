# Compact historical experiment report CLI export

## Purpose and boundary

The historical experiment command can optionally export the immutable compact
`HistoricalExperimentReport` as JSON, CSV, or both. These derived artifacts
summarize one completed execution and are audits, not restart checkpoints.

Compact export does not replace or alter the full schema-3 audit. Configuration
schema 3, experiment execution, grid generation, comparison, domain identities,
and the full-audit builder and serializer remain unchanged. Compact serializers
consume only an exact `HistoricalExperimentReport`; they do not inspect
configuration, historical bars, rolling frames, simulations, orders, fills,
ledgers, or the full audit.

## Command arguments

The command remains:

```text
python -m scripts.run_historical_experiment --config PATH
  [--output PATH] [--pretty]
  [--compact-json PATH] [--compact-json-pretty]
  [--compact-csv PATH]
  [--overwrite] [--quiet]
```

`--pretty` requires and applies only to `--output`.
`--compact-json-pretty` requires and applies only to `--compact-json`.
`--overwrite` requires at least one destination and applies to every requested
destination. No output flag implies another output. Full audit, compact JSON,
and compact CSV may be requested independently in every combination.

Every requested destination is normalized with `Path.resolve(strict=False)`.
Normalized destinations must be pairwise distinct. Dependency and duplicate
path errors are usage errors. Missing parent directories and existing
destinations without overwrite remain output errors. All path checks happen
before configuration parsing or experiment execution.

With no file destinations, the existing grid, experiment, optional comparison,
and terminal summary behavior is preserved. No audit or compact report is
built.

## One report build and exact handoff

The CLI exposes a private replaceable report-builder type for focused testing.
It builds a compact report only when JSON or CSV is requested and invokes the
builder exactly once. The exact completed experiment result, optional grid
result, and optional comparison result are passed through with independent
empty report metadata.

The exact returned report is retained on `HistoricalExperimentCliRunResult`
and reused by both serializers. Compact-only output does not collect mutable
factory records needed by the full audit.

## Execution and output sequence

The ordered flow is:

1. parse and validate arguments;
2. normalize, deduplicate, and preflight destinations;
3. parse schema-3 configuration;
4. generate an optional grid once;
5. load history once;
6. run the experiment once;
7. compare once when configured;
8. build one compact report when requested;
9. build the existing summary;
10. build and serialize all requested artifacts in memory;
11. stage every artifact in its destination directory;
12. flush and `fsync` every temporary file;
13. replace full audit, compact JSON, then compact CSV;
14. clean remaining temporary files; and
15. print successful output unless quiet.

No domain operation is retried.

## Compact JSON schema version 1

Compact JSON has its own numeric root `schema_version` of 1 and one `report`
object. It explicitly contains report and source identities, fingerprints,
variant source, optional grid IDs, optional compact ranking, caller-order
variant rows, and ordered report metadata.

Ranking contains policy ID, policy fingerprint, comparison result ID, ordered
criteria, and tie breaker. Each variant contains caller ordinal, run and
rolling-result IDs, variant ID and name, grid ordinal and assignments, rank,
criterion-named comparison values, and all 26 exact metrics.

Decimals are canonical strings, integers and booleans retain their JSON types,
null remains JSON null, UUIDs are canonical strings, and enums use their
values. Object keys are sorted. Compact JSON uses compact separators; pretty
JSON uses two-space indentation. Both end in exactly one newline.

## Stable CSV schema

CSV uses one immutable explicit 81-column header and one caller-order row per
variant. Its sections are:

1. nine report identity and provenance columns;
2. five ranking identity and policy columns;
3. report metadata evidence;
4. seven row identity and rank columns;
5. grid assignment evidence;
6. five fixed grid convenience columns;
7. comparison-value evidence;
8. 26 fixed ranking-value columns; and
9. all 26 exact metric fields.

The five grid columns cover every version-one grid parameter. The 26
`rank_value_` columns cover every ranking metric. Inactive convenience cells
are blank. Metrics are always populated and ratios are not percentage-scaled.

`report_metadata`, `grid_assignments`, `ranking_criteria`, and
`comparison_values` contain compact, sorted-key JSON arrays preserving semantic
order. These are authoritative typed evidence alongside the fixed convenience
columns. In particular, an explicit null grid assignment remains visible in
evidence while its convenience cell is blank.

CSV uses the standard Python `csv` module, UTF-8, comma delimiter,
`QUOTE_MINIMAL`, doubled quotes, and `\n` line endings. The header is always
present and output ends in exactly one newline. Commas, quotes, Unicode, and
embedded newlines follow standard CSV escaping.

## Determinism and fixtures

The serializer uses explicit mappings for all 26 metric fields, supported grid
parameters, and ranking metrics. It never relies on dataclass field order.
Decimal text uses `canonical_decimal` under an isolated sufficient-precision
context.

One grid-plus-ranking execution supplies exact compact JSON, pretty JSON, and
CSV fixtures. Exact bytes, SHA-256 digests, header width, and final newline are
regression tested. Paths, clocks, locale, object identity, mapping insertion
order, and full-audit bytes do not participate.

## Full-audit independence

Requesting compact output does not alter the full schema-3 audit. Regression
tests require byte-identical full audits and equal experiment, run, rolling,
optimized simulation, performance, grid, and comparison identities with and
without compact exports. Compact report metadata remains empty and does not
enter raw domain identity.

## Failure and atomicity semantics

All requested artifacts are completely constructed and serialized before any
temporary output is created. Serialization failure therefore preserves every
destination.

The CLI then creates same-directory temporary files, writes and flushes their
complete UTF-8 contents, and calls `fsync` on all of them before replacement
begins. Staging failure cleans all temporary files and preserves destinations.

Each `os.replace` is individually atomic. Multiple replacements are not a
filesystem transaction: if a later replacement fails, earlier replacements
may already have succeeded and are not rolled back. Remaining temporary files
are cleaned. The CLI does not claim aggregate rollback.

Known compact report construction errors map to experiment execution exit 6.
Compact serialization, staging, and replacement errors map to output exit 7.
Unexpected programming exceptions propagate.

## Terminal output and deferred work

When compact output is requested, successful non-quiet output appends the
report ID and normalized paths for only the requested compact formats. Quiet
mode suppresses both existing and compact success output while still writing
artifacts.

Pairwise differences, Pareto fronts, composite scoring, charts, tuning,
recommendations, persistence, concurrency, networking, broker operations,
GPU work, and AI remain outside this milestone.
