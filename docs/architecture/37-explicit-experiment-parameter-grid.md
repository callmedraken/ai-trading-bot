# Explicit historical experiment parameter grids

## Responsibility and package boundary

`trading_bot.experiments` contains a pure deterministic parameter-grid layer.
It expands one exact immutable `HistoricalExperimentVariant` across finite,
ordered caller values and returns explicit generated variants plus an immutable
generation audit.

The grid layer does not run an experiment, rolling simulation, optimizer,
analytics, strategy, risk evaluation, execution, ledger, or runtime. It does
no CLI or file work, networking, brokerage, scheduling, persistence,
concurrency, GPU work, AI analysis, tuning, sampling, or adaptive search.

## Supported parameters

Version one supports exactly:

- `WINDOW_OBSERVATION_COUNT`
- `SCENARIO_CASH_RETURN`
- `RISK_AVERSION`
- `PROPOSAL_CONFIDENCE`
- `TRADING_ENABLED`

There are no arbitrary paths, caller field names, nested-path syntax, or whole
object replacement. Optimizer parameters and portfolio constraints are
deferred because their cross-field relationships deserve a separate explicit
design.

## Explicit finite axes and strict values

Every axis has one exact supported enum and a nonempty ordered tuple of
explicit values. Values are never sorted, sampled, inferred, or coerced.

Observation counts are exact non-boolean integers of at least two. Cash return
and risk aversion are exact finite `Decimal` values with lower bounds of
negative one and zero respectively. Proposal confidence is `None` or an exact
finite `Decimal` in the inclusive zero-to-one interval. Trading enabled is an
exact boolean.

Canonical typed material uses `DECIMAL|`, `INTEGER|`, `BOOLEAN|`, and `NULL|`
markers. Decimal text uses `canonical_decimal`; consequently `1` and `1.0`,
and positive and negative zero, are canonical duplicates. Axes reject
duplicates rather than silently deduplicating them.

Specifications require a caller UUID, the exact base variant, at least one
unique-parameter axis, a positive non-boolean `maximum_variant_count`, and
ordered unique metadata. The `historical_experiment_grid_` metadata prefix is
reserved. Tuple inputs are defensively copied while the exact base object is
retained.

## Cartesian expansion and size

Expansion preserves caller axis and value order. The final axis varies fastest.
For `A=[a1,a2]` and `B=[b1,b2,b3]`, order is `a1,b1`, `a1,b2`, `a1,b3`,
`a2,b1`, `a2,b2`, `a2,b3`.

The exact Cartesian product is calculated before any replacement or generated
variant construction. A product above the explicit maximum fails immediately.
There is no hidden implementation cap, and Python integer multiplication is
overflow-safe.

## Immutable replacement behavior

A fixed private enum-to-function table implements replacement. Window count
constructs a new `RollingHistoricalWindowPolicy`; the remaining parameters
replace only their corresponding scalar field. `dataclasses.replace` invokes
the existing constructors and validation. Arbitrary reflection, `setattr`,
dotted traversal, and caller-selected fields are prohibited.

The base and all unchanged nested immutable policies remain unchanged and may
retain object identity. Generated variants retain base metadata exactly. Grid
provenance exists only in `HistoricalExperimentGeneratedVariant`; the grid
does not weaken or bypass the variant's `historical_experiment_` metadata
restriction.

## Names and deterministic identity

Generated names have the canonical form:

```text
<Base name> | PARAMETER=value, PARAMETER=value
```

Assignments remain in axis order. Decimal and integer display uses canonical
numeric text, booleans use lowercase `true` or `false`, and `None` uses
`NULL`. Names must be nonblank and unique after stripping and case-folding.
No new length limit or caller template is introduced.

UUID5 identities use the private version
`historical-experiment-grid-v1`. A generated variant UUID binds the
specification UUID, complete canonical base-variant material, base UUID,
zero-based ordinal, and ordered typed assignments. Axis or value reordering
therefore changes generated identities.

The result UUID additionally binds ordered axes and values, the explicit
maximum, ordered specification metadata, ordered generated UUIDs, and ordered
assignment evidence. It excludes clocks, UUID4 values, Python hashes, locale,
paths, mapping iteration, and object identity.

The historical runner and grid share a private namespace-free canonical
variant-material helper. The runner continues applying its original namespace
and version, and fixed request, rolling-request, run, and result UUID
regressions protect compatibility.

## Generation, duplicates, and reconciliation

Generation validates all input and size before building local rows. Each
combination is applied in axis order, receives its name and UUID, and is
constructed through the authoritative variant model. Expected constructor
failures retain ordinal, ordered assignments, relevant parameter, and cause.
Generation is fail-fast, has no retries, and returns no partial result.

A combination explicitly equal to the base settings is valid and still
receives a grid-owned name and UUID. Canonical axis duplicates, generated ID
duplicates, normalized-name duplicates, and equivalent effective variants are
errors. Effective comparison excludes only generated ID and name. Nothing is
silently skipped or deduplicated.

Reconciliation verifies exact Cartesian coverage and order, sequential
ordinals, assignment order and values, explicit replacement results, canonical
names and UUIDs, uniqueness, unchanged specification/base material, exact
specification retention, and aggregate identity. The aggregate result is
constructed last.

## Relationship and deferred work

Callers may derive an ordered variant tuple from generated rows and pass it to
`HistoricalExperimentRequest.variants`. The grid result does not construct the
request or invoke `HistoricalExperimentRunner` or
`HistoricalExperimentComparator`.

Deferred work includes CLI integration, range syntax, optimizer and constraint
axes, random search, Bayesian or adaptive tuning, pruning, persistence, and
parallel execution. If a future CLI supports grids, explicit variants and a
base-plus-grid form should initially be mutually exclusive.
