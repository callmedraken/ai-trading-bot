# Optional historical experiment grid CLI

## Command and responsibility

The command remains:

```text
python -m scripts.run_historical_experiment --config PATH
  [--output PATH] [--pretty] [--overwrite] [--quiet]
```

Grid integration has no command-line flags. It resolves one explicit variant
source before the existing offline experiment and optional comparison. It
performs no range generation, sampling, tuning, pruning, adaptive search,
winner selection, direct rolling/scenario/simulation construction, networking,
brokerage, scheduling, persistence, concurrency, GPU work, or AI analysis.

## Configuration schema version 3

Version 3 requires the exact root keys `schema_version`, `request_id`,
`historical_data`, `rebalance_schedule`, `initial_state`, `variants`,
`variant_grid`, `metadata`, and `ranking`. Version 2 is rejected with migration
guidance.

Both variant-source keys are mandatory and exactly one is active:

- Explicit mode uses a nonempty `variants` array and `variant_grid: null`.
- Grid mode uses `variants: null` and one exact `variant_grid` object.

They are never merged. Ranking remains explicitly null or an exact policy.

The grid object contains a canonical UUID, one complete base variant, nonempty
ordered axes, a positive explicit maximum count, and ordered metadata. The
existing variant parser handles the base variant. Axis values use
parameter-specific JSON:

- window count: JSON integer;
- scenario cash return and risk aversion: Decimal string;
- proposal confidence: Decimal string or null;
- trading enabled: JSON boolean.

No scalar coercion or generic range/search fields are accepted. Exact grid
domain models remain authoritative for canonical duplicates, ranges, unique
parameters, metadata restrictions, and maximum validity.

## Resolution and execution

After parsing, grid mode constructs one generator and invokes `generate`
exactly once before historical data is loaded. This avoids data I/O for an
invalid or oversized grid. The final tuple is derived in Cartesian order from
the exact retained generated variant objects. Explicit mode constructs no
generator.

History is then loaded once, one experiment request is constructed, and the
experiment runner executes once. The optional comparator is constructed and
called once only after successful experiment completion. Neither grid,
experiment, nor comparison work is retried.

Grid provenance remains separate from the experiment request. Specification
metadata, maximum count, and grid result ID are not injected into experiment,
variant, rolling, or bootstrap metadata or identities.

## Summary views

Explicit mode preserves the prior raw and optional ranked summary exactly.
Grid mode prepends a compact neutral section containing specification ID,
generated count, maximum count, and ordered axis values. It does not repeat
every generated assignment. Existing raw caller-order variant metrics follow,
then the optional ranked view.

Rank is an ordinal under an explicit policy, not a recommendation. Quiet mode
suppresses grid, raw, and ranked successful output.

## Audit schema version 3

The fixed root is:

```text
schema_version, configuration, historical_data, initial_state,
variant_generation, experiment, comparison
```

`variant_generation` is always present. It is null in explicit mode. Grid mode
retains the complete specification, grid result ID, and ordered generated rows.
Each row contains only ordinal, generated variant ID/name, and ordered
parameter/value assignments. Decimal assignments serialize as strings,
integers as JSON integers, booleans as booleans, and absent confidence as null.
Generated policy graphs are not duplicated; complete generated variants remain
in the raw experiment run audit.

Serialization reconciles exact specification retention, exact generated-object
and request handoff, count/order/ordinal/ID/name agreement, and the existing
comparison source relationships. Inconsistency is reported, never repaired.
Reports use sorted keys, retain semantic array order, and end with one newline.
They are immutable audits, not restart checkpoints.

## Identity effects

Base changes, axis parameter/value/order changes, and specification UUID
changes alter generated variant IDs, grid result identity, raw experiment
identity, comparison identity, and audit bytes.

Changing only `maximum_variant_count` or grid metadata leaves generated variant
IDs, raw experiment identity, and comparison identity unchanged. Those fields
do alter grid result identity and audit bytes. This follows the existing grid
domain identity contract; the CLI adds no identity material.

Schema-2 compact and pretty fixtures remain immutable SHA-256 sentinels.
Schema-3 adds exact compact and pretty fixtures while preserving raw nested
historical, initial-state, experiment, comparison, rolling, and optimized
serialization contracts.

## Errors and atomic output

Usage, read, configuration, initialization, execution, and output retain exit
codes 2 through 7. Grid parser/model errors map to configuration code 4.
Domain errors from `generate` map to execution code 6.

A generation failure occurs before provider loading and prevents runner,
comparator, summary, audit, or destination changes. Later experiment or
comparison failure does not regenerate the grid and likewise produces no
success output or audit replacement. Atomic output leaves existing
destinations unchanged and no temporary residue.

Without `--output`, grid resolution, experiment execution, and optional
comparison still occur, but audit construction and nested serialization do
not.

Deferred work includes range syntax, random or Bayesian sampling, adaptive
tuning, pruning, persistence, and parallel execution.
