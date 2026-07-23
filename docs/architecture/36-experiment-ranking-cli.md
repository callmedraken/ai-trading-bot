# Optional historical experiment ranking CLI

## Responsibility and command

The historical experiment CLI may derive one explicit, deterministic ranked view
from a completed immutable experiment result. The command remains:

```text
python -m scripts.run_historical_experiment --config PATH
  [--output PATH] [--pretty] [--overwrite] [--quiet]
```

Ranking has no command-line flags. It is presentation and audit derivation only:
it does not alter requests, variants, simulation construction, bootstrap
identity, or any raw experiment result identity.

## Configuration schema version 2

The numeric schema version is `2`. Version 1 is rejected with migration
guidance. The exact root adds `ranking`, which may be missing, `null`, or an
exact policy object. Missing and null both become `None`; the canonical audit
always emits `"ranking": null` when ranking is absent.

A policy explicitly provides its canonical UUID, one or more ordered unique
metric/direction criteria, a tie breaker, and ordered unique metadata.
Unknown keys and invalid domain values fail at their JSON path. Comparison
reserved metadata is prohibited. There is no direction inference, weighting,
scoring, grid, or tuning behavior.

## Execution and views

History is loaded once and `HistoricalExperimentRunner.run` is called once.
When a policy exists, one comparator is constructed after the runner completes
and its `compare` method is called once with the exact result and policy
objects. A known comparison failure stops later work, is not retried, and maps
to experiment execution exit code 6.

The complete existing caller-order summary is preserved as the first view.
Ranking appends the policy and ranked rows, using only each ranked row's exact
comparison values in configured criterion order. Rank 1 is a neutral ordinal,
not a recommendation or live-selection signal.

Without `--output`, audit construction and nested serialization do not occur.
The experiment and optional comparison still run. `--quiet` suppresses all
successful summary output.

## Audit schema version 2

The fixed root is:

```text
schema_version, configuration, historical_data, initial_state,
experiment, comparison
```

`comparison` is always present and is null when ranking is absent. Otherwise it
contains the canonical policy, policy fingerprint, comparison result ID,
source experiment result ID, and ranked rows linked to raw run and variant IDs.
Rows contain only rank, caller ordinal, source IDs, and metric/value pairs; they
do not duplicate variants, rolling results, scenarios, simulations, or
analytics.

Before serialization, exact object linkage, source-result identity, complete
and unique raw-run coverage, and criterion/value counts are reconciled.
Inconsistency is reported rather than repaired. Decimal values use canonical
strings and integer values remain JSON integers. Keys are sorted, semantic
array order is retained, and output has one trailing newline.

The extracted raw sections preserve the former schema-1 historical data,
initial state, experiment, and nested rolling bytes. Ranking policy material is
excluded from raw identity construction, so changing a policy can change only
the comparison identity and ranked view.

## Output and boundaries

File output remains atomic. A comparison failure creates or replaces no
destination and leaves no temporary output. Reports are audits, not resumable
checkpoints.

Deferred work includes pairwise comparison displays, Pareto analysis,
composite scores, parameter grids, tuning, and any live-candidate selection.
Networking, broker operation, scheduling, persistence, concurrency, GPU work,
and AI remain outside this layer.
