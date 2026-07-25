# Walk-forward historical experiment CLI and exports

## Command and boundary

The dedicated offline command is:

```text
python -m scripts.run_walk_forward_experiment --config PATH
  [--json PATH] [--json-pretty]
  [--csv PATH]
  [--overwrite] [--quiet]
```

It reads one strict walk-forward configuration, loads aligned local CSV history
once, constructs one walk-forward runner, and invokes that runner exactly once.
It does not directly run historical experiments, comparisons, or compact-report
builders. Those operations remain inside the walk-forward domain runner.

The command performs no networking, brokerage operation, scheduling,
persistence, concurrency, GPU work, AI analysis, parameter search, tuning, or
aggregate out-of-sample analytics.

## Separate schema-one configuration

Walk-forward configuration has independent numeric schema version 1. Exact root
members are `schema_version`, `request_id`, `historical_data`, `initial_state`,
`variants`, `folds`, `selection_policy`, and `metadata`. Unknown and missing
fields fail at every level. Historical experiment configuration schema 3 is
unchanged.

Candidates are an explicit nonempty ordered variant array. Grids are not part
of schema 1 and are rejected as unknown input. Folds retain explicit adjacent
training and test bounds, exact schedules, UUIDs, and ordered metadata. The
selection policy embeds one complete explicit ranking policy.

Decimal values are strings, booleans are strict, UUID text is canonical, enum
values are exact, and aware timestamps normalize to UTC. Historical source
paths resolve relative to the configuration document and never enter domain
identity.

## Historical load and simulator factory

One CSV provider and one coordinating provider load the complete aligned source
history exactly once. The walk-forward domain layer remains authoritative for
slice construction, schedule membership, observation sufficiency, isolation,
selection, and reconciliation.

The CLI simulator factory constructs fresh engines, ledgers, runtimes, and
simulators. Its operational uniqueness key is the child experiment request
UUID, variant UUID, and child variant ordinal. Bootstrap identity uses the same
context, ensuring repeated candidates in different folds remain distinct.

## Execution modes and summary

With no destination the complete evaluation still runs and a deterministic
summary prints. `--quiet` suppresses successful stdout only. JSON-only,
CSV-only, and combined output are supported. Pretty formatting applies only to
JSON and requires a JSON destination.

The summary prints request, result, source, policy, fold, training report,
candidate rank, selection, test report, test run, rolling-result, and exact test
metric evidence. Folds remain visibly independent. The summary explicitly
states that no aggregate out-of-sample metrics or continuous equity curve are
defined.

## JSON schema version 1

JSON contains numeric `schema_version` 1 and one `walk_forward_result` object.
It retains result and request UUIDs, the source historical fingerprint, the
complete selection policy, ordered result metadata, and ordered fold results.

Each fold contains its exact specification, ranked compact training report,
selection certificate, unranked single-row compact test report, test run UUID,
and test rolling-result UUID. Nested compact reports retain all source
fingerprints, ranking evidence, caller-order rows, and 26 exact metrics.

Decimals use canonical strings, integers and booleans retain JSON types, UUIDs
use canonical text, enums use their values, and datetimes use normalized UTC
ISO-8601 text. Object keys are sorted. Compact and two-space pretty output end
in exactly one newline.

## CSV schema

CSV is deterministic long form. For each fold it emits every
`TRAINING_VARIANT` row in training-report caller order followed by the one
`TEST_VARIANT` row. Fold, selection, policy, and report provenance repeat on
each row so every row remains attributable.

The fixed header includes walk-forward identities, ranking policy evidence,
fold bounds and schedules, selection certification, row/report provenance, 26
fixed rank-value convenience columns, and all 26 exact metric columns. Test
ranking cells are blank. Ordered schedules, criteria, comparison values, and
metadata use compact sorted-key JSON evidence.

CSV uses UTF-8, comma delimiter, `QUOTE_MINIMAL`, doubled quotes, `\n` line
endings, and exactly one final newline. It contains no aggregate cross-fold
metric.

## Immutable serialization and artifact independence

Both serializers accept only the exact immutable
`HistoricalExperimentWalkForwardResult` returned by the one runner call.
Serialization does not run experiments, ranking, report construction, or
financial calculations. JSON and CSV reuse the same result object.

The walk-forward command is separate from the historical experiment command.
Historical schema-3 audit, compact, pairwise, and Pareto artifacts and all
upstream IDs remain unchanged. Output paths, format choices, pretty mode,
overwrite state, and quiet mode do not participate in identity.

## Coordinated output

The historical and walk-forward commands share one coordinated staging
utility. Every destination is normalized, collision checked, and preflighted
before configuration parsing. All requested text is serialized before staging.
Every temporary file is created beside its destination, written completely,
flushed, and `fsync`ed before replacement begins.

Historical replacement order remains full audit, compact JSON, compact CSV,
pairwise JSON, pairwise CSV, Pareto JSON, and Pareto CSV. Walk-forward order is
JSON then CSV. Each replacement is individually atomic; multiple replacements
are not a transaction. A later failure does not roll back an earlier successful
replacement. Remaining temporary files are cleaned without rerunning domain
work.

## Errors and deferred work

Exit codes are 0 success, 2 usage, 3 read/UTF-8/JSON syntax, 4 schema/path/data
or request validation, 5 initialization, 6 walk-forward execution or
reconciliation, and 7 serialization or output. Fold failures print fold
ordinal, UUID, stage, and message. Expected failures are fail-fast and are
never retried.

Artifacts are immutable audits, not restart checkpoints. Fold generation,
grids, continuous capital, aggregation, compounding, cross-fold averages,
statistics, pairwise or Pareto selection across folds, charts, optimization,
search, and tuning remain deferred.
